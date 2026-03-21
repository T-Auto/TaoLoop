from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
import asyncio
import os
import re
import subprocess
import time
import uuid

from .config import Config
from .monitor import ResourceMonitor
from .sessions import ChatMessage, now_iso


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
JobMessageCallback = Callable[[str, ChatMessage], Awaitable[None]]
JobsChangedCallback = Callable[[list[dict[str, Any]]], Awaitable[None]]


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


@dataclass(slots=True)
class BackgroundJob:
    id: str
    session_id: str
    session_title: str
    command: str
    cwd: Path
    pid: int
    started_at: str
    started_monotonic: float
    timeout_sec: int
    monitor_schedule: tuple[int, ...]
    process: subprocess.Popen[str] = field(repr=False)
    status: str = "running"
    exit_code: int | None = None
    timed_out: bool = False
    finished_at: str = ""
    finished_runtime_sec: float = 0.0
    last_heartbeat_sec: int = 0
    last_snapshot: dict[str, Any] = field(default_factory=dict)
    log_tail: deque[str] = field(default_factory=lambda: deque(maxlen=24), repr=False)
    stdout_tail: deque[str] = field(default_factory=lambda: deque(maxlen=24), repr=False)
    stderr_tail: deque[str] = field(default_factory=lambda: deque(maxlen=24), repr=False)
    task: asyncio.Task[Any] | None = field(default=None, repr=False)

    def runtime_sec(self) -> float:
        if self.finished_at:
            return round(self.finished_runtime_sec, 1)
        return round(max(0.0, time.monotonic() - self.started_monotonic), 1)

    def last_runtime_sec(self) -> float:
        return max(0.0, time.monotonic() - self.started_monotonic)

    def tail_lines(self, limit: int = 8) -> list[str]:
        return list(self.log_tail)[-limit:]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "session_title": self.session_title,
            "command": self.command,
            "cwd": str(self.cwd),
            "pid": self.pid,
            "status": self.status,
            "started_at": self.started_at,
            "runtime_sec": self.runtime_sec(),
            "timeout_sec": self.timeout_sec,
            "timed_out": self.timed_out,
            "exit_code": self.exit_code,
            "last_heartbeat_sec": self.last_heartbeat_sec,
            "last_log_line": self.tail_lines(1)[0] if self.log_tail else "",
        }


class BackgroundJobManager:
    def __init__(
        self,
        config: Config,
        *,
        enqueue_message: JobMessageCallback,
        emit_jobs_changed: JobsChangedCallback,
        logger: Any | None = None,
    ) -> None:
        self.config = config
        self.enqueue_message = enqueue_message
        self.emit_jobs_changed = emit_jobs_changed
        self.logger = logger
        self.monitor = ResourceMonitor(config.sandbox_dir)
        self.jobs: dict[str, BackgroundJob] = {}
        self._lock = asyncio.Lock()

    async def start_process(
        self,
        *,
        session_id: str,
        session_title: str,
        command: str,
        cwd: Path,
        env: dict[str, str],
        popen_command: list[str] | str,
        use_shell: bool,
        encoding: str,
        timeout_sec: int = 0,
    ) -> BackgroundJob:
        process = subprocess.Popen(
            popen_command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env=env,
            shell=use_shell,
            text=True,
            encoding=encoding,
            errors="replace",
            bufsize=1,
        )
        job = BackgroundJob(
            id=f"job_{uuid.uuid4().hex[:10]}",
            session_id=session_id,
            session_title=session_title,
            command=command,
            cwd=cwd,
            pid=process.pid,
            started_at=now_iso(),
            started_monotonic=time.monotonic(),
            timeout_sec=timeout_sec,
            monitor_schedule=tuple(self.config.monitor_intervals),
            process=process,
        )
        async with self._lock:
            self.jobs[job.id] = job
        if self.logger:
            self.logger.log(
                "background_job_start",
                job_id=job.id,
                session_id=session_id,
                command=command,
                cwd=str(cwd),
                pid=process.pid,
                timeout_sec=timeout_sec,
            )
        job.task = asyncio.create_task(self._run_job(job))
        await self._emit_jobs_changed()
        return job

    async def shutdown(self) -> None:
        async with self._lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            if job.status != "running":
                continue
            await self._terminate_process_tree(job.pid)
        for job in jobs:
            if job.task is None:
                continue
            try:
                await job.task
            except Exception as exc:
                if self.logger:
                    self.logger.log(
                        "background_job_shutdown_error",
                        job_id=job.id,
                        error=str(exc),
                    )
                continue

    async def list_jobs(
        self,
        *,
        session_id: str | None = None,
        include_finished: bool = False,
        max_jobs: int = 20,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            jobs = list(self.jobs.values())
        jobs.sort(key=lambda item: item.started_monotonic, reverse=True)
        rendered: list[dict[str, Any]] = []
        for job in jobs:
            if session_id and job.session_id != session_id:
                continue
            if not include_finished and job.status != "running":
                continue
            rendered.append(job.to_public_dict())
            if len(rendered) >= max_jobs:
                break
        return rendered

    async def get_job(self, job_id: str) -> BackgroundJob | None:
        async with self._lock:
            return self.jobs.get(job_id)

    async def stop_job(self, job_id: str) -> BackgroundJob:
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"background job not found: {job_id}")
        if job.status == "running":
            await self._terminate_process_tree(job.pid)
            if job.task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(job.task), timeout=15)
                except asyncio.TimeoutError:
                    job.status = "stop_timeout"
                    job.finished_at = now_iso()
                    job.finished_runtime_sec = job.last_runtime_sec()
                    if self.logger:
                        self.logger.log(
                            "background_job_stop_timeout",
                            job_id=job.id,
                            pid=job.pid,
                            runtime_sec=job.runtime_sec(),
                        )
        return job

    async def _run_job(self, job: BackgroundJob) -> None:
        stdout_task = asyncio.create_task(self._pump_stream(job, job.process.stdout, "stdout"))
        stderr_task = asyncio.create_task(self._pump_stream(job, job.process.stderr, "stderr"))
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(job))

        try:
            while job.process.poll() is None:
                if job.timeout_sec > 0 and time.monotonic() - job.started_monotonic >= job.timeout_sec:
                    job.timed_out = True
                    job.status = "timed_out"
                    await self._terminate_process_tree(job.pid)
                    break
                await asyncio.sleep(0.5)
            await asyncio.to_thread(job.process.wait)
        finally:
            await stdout_task
            await stderr_task
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            if job.process.stdout is not None:
                job.process.stdout.close()
            if job.process.stderr is not None:
                job.process.stderr.close()

        if job.status == "running":
            job.status = "succeeded" if job.process.returncode == 0 else "failed"
        job.exit_code = job.process.returncode
        job.finished_runtime_sec = max(0.0, time.monotonic() - job.started_monotonic)
        job.finished_at = now_iso()
        if not job.last_snapshot:
            job.last_snapshot = self.monitor.snapshot(None)

        await self.enqueue_message(
            job.session_id,
            ChatMessage.create(
                "event",
                self._build_job_message(job, phase="finish", snapshot=job.last_snapshot),
                meta={
                    "source_tool": "start_background_command",
                    "background_job_id": job.id,
                    "background_job_phase": "finish",
                    "background_job_status": job.status,
                },
            ),
        )
        await self._emit_jobs_changed()
        if self.logger:
            self.logger.log(
                "background_job_finish",
                job_id=job.id,
                status=job.status,
                exit_code=job.exit_code,
                timed_out=job.timed_out,
                runtime_sec=job.runtime_sec(),
            )

    async def _pump_stream(
        self,
        job: BackgroundJob,
        stream: Any,
        channel: str,
    ) -> None:
        if stream is None:
            return
        while True:
            line = await asyncio.to_thread(stream.readline)
            if line == "":
                break
            text = _strip_ansi(line).rstrip("\r\n")
            if not text:
                continue
            prefixed = f"{channel} | {text}" if channel == "stderr" else text
            job.log_tail.append(prefixed)
            if channel == "stderr":
                job.stderr_tail.append(text)
            else:
                job.stdout_tail.append(text)

    async def _heartbeat_loop(self, job: BackgroundJob) -> None:
        for interval in self._monitor_schedule():
            wait_time = job.started_monotonic + interval - time.monotonic()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            if job.process.poll() is not None:
                return
            snapshot = await asyncio.to_thread(self.monitor.snapshot, job.pid)
            job.last_snapshot = snapshot
            job.last_heartbeat_sec = interval
            await self.enqueue_message(
                job.session_id,
                ChatMessage.create(
                    "event",
                    self._build_job_message(job, phase="heartbeat", snapshot=snapshot, after_sec=interval),
                    meta={
                        "source_tool": "start_background_command",
                        "background_job_id": job.id,
                        "background_job_phase": "heartbeat",
                        "background_job_status": job.status,
                        "background_job_after_sec": interval,
                    },
                ),
            )
            await self._emit_jobs_changed()

    def _monitor_schedule(self) -> list[int]:
        schedule = list(self.config.monitor_intervals)
        if not schedule:
            return []
        repeat_interval = max(60, self.config.monitor_repeat_interval_sec)
        last = schedule[-1]
        while last < 7 * 24 * 3600:
            last += repeat_interval
            schedule.append(last)
        return schedule

    def _build_job_message(
        self,
        job: BackgroundJob,
        *,
        phase: str,
        snapshot: dict[str, Any],
        after_sec: int = 0,
    ) -> str:
        lines = []
        tail_limit = 6 if phase == "heartbeat" else 8
        if phase == "heartbeat":
            lines.append("后台脚本心跳")
        else:
            lines.append("后台脚本运行结束")
        lines.extend(
            [
                f"job_id={job.id}",
                f"command={job.command}",
                f"cwd={job.cwd}",
                f"status={job.status}",
                f"pid={job.pid}",
                f"elapsed_sec={job.runtime_sec():.1f}",
            ]
        )
        if after_sec > 0:
            lines.append(f"heartbeat_after_sec={after_sec}")
        if job.exit_code is not None:
            lines.append(f"exit_code={job.exit_code}")
        lines.append(f"timed_out={job.timed_out}")
        lines.append("recent_logs:")
        tail_lines = job.tail_lines(limit=tail_limit)
        if tail_lines:
            lines.extend(tail_lines)
        else:
            lines.append("(empty)")
        lines.append("hardware:")
        lines.extend(self.monitor.format_snapshot_lines(snapshot))
        return "\n".join(lines)

    async def _emit_jobs_changed(self) -> None:
        jobs = await self.list_jobs(include_finished=True, max_jobs=200)
        await self.emit_jobs_changed(jobs)

    async def _terminate_process_tree(self, pid: int) -> None:
        if pid <= 0:
            return
        if self.logger:
            self.logger.log("background_job_terminate", pid=pid)
        if os.name == "nt":
            await asyncio.to_thread(
                lambda: subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                )
            )
            return
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            return
