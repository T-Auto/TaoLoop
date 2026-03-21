from __future__ import annotations

from typing import Any
import asyncio
import json
import sys
import threading
import traceback

from .agent import ConversationAgent
from .background_jobs import BackgroundJobManager
from .config import Config
from .logging_utils import FileLogger
from .message_buffer import BufferedSessionMessage, MessageBufferQueue
from .sessions import ChatMessage, SessionRecord, SessionStore
from .tools import ToolRegistry


class BackendServer:
    def __init__(self) -> None:
        self.config = Config.load()
        self.logger = FileLogger(self.config.state_dir)
        self.store = SessionStore(self.config.sessions_dir, logger=self.logger)
        self.request_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.user_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.output_lock = threading.Lock()
        self.active_session: SessionRecord | None = None
        self.loaded_sessions: dict[str, SessionRecord] = {}
        self.busy = False
        self.message_buffer = MessageBufferQueue(logger=self.logger)
        self.background_jobs = BackgroundJobManager(
            self.config,
            enqueue_message=self._enqueue_background_message,
            emit_jobs_changed=self._emit_jobs_changed,
            logger=self.logger,
        )
        self.tools = ToolRegistry(
            self.config,
            emit=self.emit,
            logger=self.logger,
            background_jobs=self.background_jobs,
            current_session=self._current_session_context,
        )
        self.agent = ConversationAgent(
            self.config,
            self.emit,
            logger=self.logger,
            tools=self.tools,
            has_buffered_user_input=self._has_buffered_user_input,
            flush_buffered_messages=self._flush_message_buffer,
        )
        self.logger.log(
            "backend_init",
            root_dir=str(self.config.root_dir),
            sandbox_dir=str(self.config.sandbox_dir),
            model=self.config.model,
            offline_mode=self.config.offline_mode,
        )

    async def emit(self, payload: dict[str, Any]) -> None:
        self.logger.log("backend_emit", payload=payload)
        text = json.dumps(payload, ensure_ascii=False)
        with self.output_lock:
            sys.stdout.write(text + "\n")
            sys.stdout.flush()

    def _current_session_context(self) -> tuple[str | None, str]:
        if self.active_session is None:
            return None, ""
        return self.active_session.id, self.active_session.title

    def _remember_session(self, session: SessionRecord) -> SessionRecord:
        self.loaded_sessions[session.id] = session
        return session

    def _get_session(self, session_id: str) -> SessionRecord:
        cached = self.loaded_sessions.get(session_id)
        if cached is not None:
            return cached
        session = self.store.load(session_id)
        self.loaded_sessions[session_id] = session
        return session

    async def _has_buffered_user_input(self, session_id: str) -> bool:
        return await self.message_buffer.has_user_messages(session_id)

    async def _enqueue_user_message(self, session_id: str, message: ChatMessage) -> None:
        await self.message_buffer.put_user(session_id, message)
        if not self.busy:
            await self._flush_message_buffer()

    async def _enqueue_background_message(self, session_id: str, message: ChatMessage) -> None:
        await self.message_buffer.put_event(
            session_id,
            message,
            meta=self._background_buffer_meta(message),
        )
        if not self.busy:
            await self._flush_message_buffer()

    @staticmethod
    def _background_buffer_meta(message: ChatMessage) -> dict[str, Any] | None:
        phase = message.meta.get("background_job_phase")
        job_id = message.meta.get("background_job_id")
        if phase == "heartbeat" and isinstance(job_id, str) and job_id:
            return {"coalesce_key": f"background-heartbeat:{job_id}"}
        return None

    async def _flush_message_buffer(self) -> None:
        result = await self.message_buffer.flush(self._deliver_buffered_message)
        if result.delivered > 0:
            await self._emit_session_list()

    async def _deliver_buffered_message(self, item: BufferedSessionMessage) -> None:
        session = self._get_session(item.session_id)
        if item.after_message_id:
            try:
                session.insert_after(item.after_message_id, item.message)
            except KeyError:
                session.append(item.message)
        else:
            session.append(item.message)
        self.store.save(session)
        if self.active_session is not None and self.active_session.id == item.session_id:
            self.active_session = session
        await self.emit(
            {
                "type": "message",
                "session_id": item.session_id,
                "message": item.message.to_public_dict(),
                "after_message_id": item.after_message_id,
            }
        )
        if self._should_schedule_background_followup(session, item.message):
            await self._queue_background_followup(session, item.message)

    def _should_schedule_background_followup(self, session: SessionRecord, message: ChatMessage) -> bool:
        if message.role != "event":
            return False
        phase = message.meta.get("background_job_phase")
        runtime_state = session.meta.get("runtime_state", {})
        if runtime_state.get("phase") != "sleeping":
            return False
        if runtime_state.get("reason") not in {"background_job_started", "background_job_heartbeat"}:
            return False
        if self.active_session is not None and self.active_session.id != session.id:
            return False
        if phase == "finish":
            return True
        if phase != "heartbeat":
            return False
        if message.meta.get("background_job_status") != "running":
            return False
        return int(message.meta.get("background_job_after_sec") or 0) >= 60

    async def _queue_background_followup(self, session: SessionRecord, message: ChatMessage) -> None:
        phase = str(message.meta.get("background_job_phase") or "")
        reason = "background_job_finish" if phase == "finish" else "background_job_heartbeat"
        session.meta["runtime_state"] = {
            "phase": "wakeup_pending",
            "reason": reason,
            "trigger_message_id": message.id,
            "trigger_phase": phase,
            "background_job_id": message.meta.get("background_job_id"),
            "background_job_status": message.meta.get("background_job_status"),
            "background_job_after_sec": message.meta.get("background_job_after_sec"),
        }
        self.store.save(session)
        if self.active_session is not None and self.active_session.id == session.id:
            self.active_session = session
        await self.user_queue.put(
            {
                "session_id": session.id,
                "message_id": message.id,
                "source": "background_event",
                "background_job_phase": phase,
                "background_job_id": message.meta.get("background_job_id"),
                "background_job_after_sec": message.meta.get("background_job_after_sec"),
            }
        )
        if self.logger:
            self.logger.log(
                "backend_background_followup_queued",
                session_id=session.id,
                message_id=message.id,
                background_job_id=message.meta.get("background_job_id"),
                background_job_status=message.meta.get("background_job_status"),
            )
        if not self.busy:
            await self._emit_status("wakeup_pending")

    async def _emit_jobs_changed(self, jobs: list[dict[str, Any]]) -> None:
        await self.emit({"type": "jobs", "jobs": jobs})

    def _stdin_reader(self, loop: asyncio.AbstractEventLoop) -> None:
        while True:
            line = sys.stdin.readline()
            if line == "":
                self.logger.log("backend_stdin_eof")
                loop.call_soon_threadsafe(self.request_queue.put_nowait, {"type": "shutdown"})
                return
            line = line.strip()
            if not line:
                continue
            self.logger.log("backend_request_raw", raw=line[:2000])
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self.logger.log("backend_request_invalid_json", raw=line[:2000])
                loop.call_soon_threadsafe(
                    self.request_queue.put_nowait,
                    {"type": "invalid", "raw": line},
                )
                continue
            loop.call_soon_threadsafe(self.request_queue.put_nowait, payload)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        threading.Thread(target=self._stdin_reader, args=(loop,), daemon=True).start()

        await self.emit(
            {
                "type": "ready",
                "model": self.config.model,
                "offline_mode": self.config.offline_mode,
                "root_dir": str(self.config.root_dir),
                "sandbox_dir": str(self.config.sandbox_dir),
                "log_path": str(self.logger.path),
            }
        )
        await self._emit_session_list()
        await self._emit_jobs_changed(await self.background_jobs.list_jobs(include_finished=True, max_jobs=200))

        worker = asyncio.create_task(self._user_worker())

        async def _watch_worker() -> None:
            """监视 worker，如果意外退出则自动重启。"""
            nonlocal worker
            while True:
                await asyncio.sleep(1)
                if worker.done():
                    exc = worker.exception() if not worker.cancelled() else None
                    self.logger.log(
                        "backend_worker_restarting",
                        cancelled=worker.cancelled(),
                        error=str(exc) if exc else None,
                    )
                    if exc:
                        await self._emit_error(f"Agent worker crashed and restarted: {exc}")
                    self.busy = False
                    worker = asyncio.create_task(self._user_worker())

        watcher = asyncio.create_task(_watch_worker())
        try:
            while True:
                request = await self.request_queue.get()
                self.logger.log("backend_request_dequeued", request=request)
                if request.get("type") == "shutdown":
                    break
                await self._handle_request(request)
        finally:
            watcher.cancel()
            worker.cancel()
            for task in (watcher, worker):
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            await self.background_jobs.shutdown()

    async def _handle_request(self, request: dict[str, Any]) -> None:
        request_type = request.get("type")
        self.logger.log("backend_handle_request", request_type=request_type, request=request)
        if request_type == "hello":
            await self.emit(
                {
                    "type": "ready",
                    "model": self.config.model,
                    "offline_mode": self.config.offline_mode,
                    "root_dir": str(self.config.root_dir),
                    "sandbox_dir": str(self.config.sandbox_dir),
                    "log_path": str(self.logger.path),
                }
            )
            await self._emit_session_list()
            await self._emit_jobs_changed(await self.background_jobs.list_jobs(include_finished=True, max_jobs=200))
            return

        if request_type == "list_sessions":
            await self._emit_session_list()
            return

        if request_type == "create_session":
            if self.busy:
                await self._emit_error("Agent is busy; cannot create a new session yet.")
                return
            self.active_session = self._remember_session(self.store.create(request.get("title")))
            self.logger.log("backend_session_created", session_id=self.active_session.id, title=self.active_session.title)
            await self.emit({"type": "session_loaded", "session": self.active_session.to_public_dict()})
            await self._emit_session_list()
            await self._emit_status("idle")
            return

        if request_type == "load_session":
            if self.busy:
                await self._emit_error("Agent is busy; cannot switch sessions yet.")
                return
            session_id = request.get("session_id")
            if not session_id:
                await self._emit_error("session_id is required.")
                return
            self.active_session = self._get_session(session_id)
            self.logger.log("backend_session_loaded", session_id=self.active_session.id, title=self.active_session.title)
            await self.emit({"type": "session_loaded", "session": self.active_session.to_public_dict()})
            await self._emit_status("idle")
            return

        if request_type == "delete_session":
            if self.busy:
                await self._emit_error("Agent is busy; cannot delete a session yet.")
                return
            session_id = request.get("session_id")
            if not session_id:
                await self._emit_error("session_id is required.")
                return
            running_jobs = await self.background_jobs.list_jobs(session_id=session_id, include_finished=False, max_jobs=1)
            if running_jobs:
                await self._emit_error("Session still has running background jobs; stop or wait for them before deleting.")
                return
            deleted = self.store.delete(session_id)
            if not deleted:
                await self._emit_error(f"Session not found: {session_id}")
                return
            was_active = self.active_session is not None and self.active_session.id == session_id
            if was_active:
                self.active_session = None
            self.loaded_sessions.pop(session_id, None)
            self.logger.log("backend_session_deleted", session_id=session_id, was_active=was_active)
            await self._emit_session_list()
            if was_active:
                await self._emit_status("idle")
            return

        if request_type == "user_message":
            if self.active_session is None:
                self.active_session = self._remember_session(self.store.create())
                await self.emit({"type": "session_loaded", "session": self.active_session.to_public_dict()})
                await self._emit_session_list()
            content = (request.get("content") or "").strip()
            if not content:
                await self._emit_error("Empty user message.")
                return
            message = ChatMessage.create("user", content)
            await self._enqueue_user_message(self.active_session.id, message)
            self.logger.log(
                "backend_user_message_queued",
                session_id=self.active_session.id,
                message_id=message.id,
                content_preview=content[:400],
            )
            await self.user_queue.put(
                {
                    "session_id": self.active_session.id,
                    "message_id": message.id,
                }
            )
            # 如果 agent 已在运行，保持 "running" 显示，避免覆盖成 "queued" 让用户误以为卡死
            await self._emit_status("running" if self.busy else "queued")
            return

        if request_type == "invalid":
            await self._emit_error(f"Invalid JSON received: {request.get('raw', '')[:300]}")
            return

        await self._emit_error(f"Unknown request type: {request_type}")

    async def _user_worker(self) -> None:
        while True:
            task = await self.user_queue.get()
            session_id: str | None = None
            message_id: str | None = None
            try:
                session_id = task["session_id"]
                message_id = task["message_id"]
                self.logger.log("backend_worker_start", session_id=session_id, message_id=message_id)
                self.busy = True
                await self._emit_status("running")
                try:
                    await self._flush_message_buffer()
                    session = self._get_session(session_id)
                    self.active_session = session
                    usage = await self.agent.run_turn(session, message_id)
                    await self._resume_background_monitoring_if_needed(session, task)
                    session.meta["context"] = usage
                    self.store.save(session)
                    self.active_session = session
                    await self._flush_message_buffer()
                    self.logger.log("backend_worker_finish", session_id=session_id, message_id=message_id, usage=usage)
                except Exception as exc:
                    self.logger.exception(
                        "backend_worker_exception",
                        exc,
                        session_id=session_id,
                        message_id=message_id,
                    )
                    await self._emit_error(str(exc))
                finally:
                    self.busy = False
                    await self._flush_message_buffer()
                    await self._emit_status("idle")
                    await self._emit_session_list()
            except Exception as outer_exc:
                self.logger.exception(
                    "backend_worker_task_error",
                    outer_exc,
                    session_id=session_id,
                    message_id=message_id,
                    task=str(task)[:400],
                )
                await self._emit_error(f"Worker task error (session={session_id}): {outer_exc}")
                self.busy = False
            finally:
                self.user_queue.task_done()

    async def _resume_background_monitoring_if_needed(
        self,
        session: SessionRecord,
        task: dict[str, Any],
    ) -> None:
        if task.get("source") != "background_event":
            return
        if task.get("background_job_phase") != "heartbeat":
            return
        running_jobs = await self.background_jobs.list_jobs(
            session_id=session.id,
            include_finished=False,
            max_jobs=1,
        )
        if not running_jobs:
            return
        session.meta["runtime_state"] = {
            "phase": "sleeping",
            "reason": "background_job_heartbeat",
            "reply_to_message_id": task.get("message_id"),
            "background_job_id": task.get("background_job_id"),
            "background_job_after_sec": task.get("background_job_after_sec"),
        }

    async def _emit_session_list(self) -> None:
        await self.emit({"type": "session_list", "sessions": self.store.list_sessions()})

    async def _emit_error(self, message: str) -> None:
        self.logger.log("backend_error", message=message)
        await self.emit({"type": "error", "message": message})

    async def _emit_status(self, phase: str) -> None:
        context = {}
        if self.active_session:
            context = self.active_session.meta.get("context", {})
        running_jobs = await self.background_jobs.list_jobs(include_finished=False, max_jobs=200)
        buffered_messages = await self.message_buffer.size()
        if phase == "idle" and running_jobs:
            phase = "sleeping"
        await self.emit(
            {
                "type": "status",
                "phase": phase,
                "busy": self.busy,
                "queue_length": self.user_queue.qsize() + buffered_messages,
                "running_jobs": len(running_jobs),
                "model": self.config.model,
                "offline_mode": self.config.offline_mode,
                "session_id": self.active_session.id if self.active_session else None,
                "context": context,
            }
        )


def main() -> None:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        asyncio.run(BackendServer().run())
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
