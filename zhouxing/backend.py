from __future__ import annotations

from typing import Any
import asyncio
import json
import sys
import threading
import traceback

from .agent import ConversationAgent
from .config import Config
from .logging_utils import FileLogger
from .sessions import ChatMessage, SessionRecord, SessionStore


class BackendServer:
    def __init__(self) -> None:
        self.config = Config.load()
        self.logger = FileLogger(self.config.state_dir)
        self.store = SessionStore(self.config.sessions_dir, logger=self.logger)
        self.request_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.user_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.output_lock = threading.Lock()
        self.active_session: SessionRecord | None = None
        self.busy = False
        self.agent = ConversationAgent(self.config, self.emit, logger=self.logger)
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

        worker = asyncio.create_task(self._user_worker())
        try:
            while True:
                request = await self.request_queue.get()
                self.logger.log("backend_request_dequeued", request=request)
                if request.get("type") == "shutdown":
                    break
                await self._handle_request(request)
        finally:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass

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
            return

        if request_type == "list_sessions":
            await self._emit_session_list()
            return

        if request_type == "create_session":
            if self.busy:
                await self._emit_error("Agent is busy; cannot create a new session yet.")
                return
            self.active_session = self.store.create(request.get("title"))
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
            self.active_session = self.store.load(session_id)
            self.logger.log("backend_session_loaded", session_id=self.active_session.id, title=self.active_session.title)
            await self.emit({"type": "session_loaded", "session": self.active_session.to_public_dict()})
            await self._emit_status("idle")
            return

        if request_type == "user_message":
            if self.active_session is None:
                self.active_session = self.store.create()
                await self.emit({"type": "session_loaded", "session": self.active_session.to_public_dict()})
                await self._emit_session_list()
            content = (request.get("content") or "").strip()
            if not content:
                await self._emit_error("Empty user message.")
                return
            message = ChatMessage.create("user", content)
            self.active_session.append(message)
            self.store.save(self.active_session)
            self.logger.log(
                "backend_user_message_queued",
                session_id=self.active_session.id,
                message_id=message.id,
                content_preview=content[:400],
            )
            await self.emit({"type": "message", "message": message.to_public_dict()})
            await self.user_queue.put(
                {
                    "session_id": self.active_session.id,
                    "message_id": message.id,
                }
            )
            await self._emit_status("queued")
            return

        if request_type == "invalid":
            await self._emit_error(f"Invalid JSON received: {request.get('raw', '')[:300]}")
            return

        await self._emit_error(f"Unknown request type: {request_type}")

    async def _user_worker(self) -> None:
        while True:
            task = await self.user_queue.get()
            session_id = task["session_id"]
            message_id = task["message_id"]
            self.logger.log("backend_worker_start", session_id=session_id, message_id=message_id)
            self.busy = True
            await self._emit_status("running")
            try:
                session = self.store.load(session_id)
                self.active_session = session
                usage = await self.agent.run_turn(session, message_id)
                session.meta["context"] = usage
                self.store.save(session)
                self.active_session = session
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
                await self._emit_status("idle")
                self.user_queue.task_done()
                await self._emit_session_list()

    async def _emit_session_list(self) -> None:
        await self.emit({"type": "session_list", "sessions": self.store.list_sessions()})

    async def _emit_error(self, message: str) -> None:
        self.logger.log("backend_error", message=message)
        await self.emit({"type": "error", "message": message})

    async def _emit_status(self, phase: str) -> None:
        context = {}
        if self.active_session:
            context = self.active_session.meta.get("context", {})
        await self.emit(
            {
                "type": "status",
                "phase": phase,
                "busy": self.busy,
                "queue_length": self.user_queue.qsize(),
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
