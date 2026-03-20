from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable
import asyncio
import os
import re
import subprocess
import time

from .config import Config
from .logging_utils import FileLogger
from .monitor import ResourceMonitor


ToolEmitter = Callable[[dict[str, Any]], Awaitable[None] | None]


def _clip(text: str, limit: int) -> str:
    text = text.rstrip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...[truncated {len(text) - limit} chars]"


class ToolRegistry:
    def __init__(
        self,
        config: Config,
        emit: ToolEmitter | None = None,
        logger: FileLogger | None = None,
    ):
        self.config = config
        self.emit = emit
        self.logger = logger
        self.monitor = ResourceMonitor(config.sandbox_dir)

    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files or directories. Relative paths resolve inside sandbox/ by default.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "recursive": {"type": "boolean"},
                            "max_entries": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a text file with line numbers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "description": "Search text in a file or directory tree.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "pattern": {"type": "string"},
                            "ignore_case": {"type": "boolean"},
                            "max_hits": {"type": "integer"},
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file. Use append=true to append content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "append": {"type": "boolean"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "insert_text",
                    "description": "Insert text before or after a specific line.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "text": {"type": "string"},
                            "after_line": {"type": "integer"},
                            "before_line": {"type": "integer"},
                        },
                        "required": ["path", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "replace_in_file",
                    "description": "Replace exact text inside a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "old_text": {"type": "string"},
                            "new_text": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                        "required": ["path", "old_text", "new_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell command inside sandbox and stream progress. Long-running jobs automatically report hardware heartbeats.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {"type": "string"},
                            "timeout_sec": {"type": "integer"},
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if self.logger:
            self.logger.log("tool_execute_start", tool=name, arguments=arguments)
        if name == "list_directory":
            result = await self._list_directory(**arguments)
        elif name == "read_file":
            result = await self._read_file(**arguments)
        elif name == "search_text":
            result = await self._search_text(**arguments)
        elif name == "write_file":
            result = await self._write_file(**arguments)
        elif name == "insert_text":
            result = await self._insert_text(**arguments)
        elif name == "replace_in_file":
            result = await self._replace_in_file(**arguments)
        elif name == "run_command":
            result = await self._run_command(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
        if self.logger:
            self.logger.log(
                "tool_execute_finish",
                tool=name,
                result_preview=result[:800],
            )
        return result

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self.emit is None:
            return
        result = self.emit(payload)
        if asyncio.iscoroutine(result):
            await result

    def _resolve_path(self, raw_path: str | None, *, default_scope: str = "sandbox") -> Path:
        raw = (raw_path or ".").strip()
        if not raw:
            raw = "."

        if raw.startswith("project:"):
            base = self.config.root_dir
            suffix = raw.removeprefix("project:").strip().lstrip("/\\")
            candidate = (base / suffix).resolve()
        elif raw.startswith("sandbox:"):
            base = self.config.sandbox_dir
            suffix = raw.removeprefix("sandbox:").strip().lstrip("/\\")
            candidate = (base / suffix).resolve()
        else:
            base = self.config.sandbox_dir if default_scope == "sandbox" else self.config.root_dir
            candidate = (base / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()

        allowed_roots = [self.config.root_dir.resolve(), self.config.sandbox_dir.resolve()]
        if not any(self._is_within(candidate, root) for root in allowed_roots):
            raise ValueError(f"Path escapes allowed roots: {raw_path}")
        return candidate

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    async def _list_directory(
        self,
        path: str = ".",
        recursive: bool = False,
        max_entries: int = 120,
    ) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(str(target))
        iterator = target.rglob("*") if recursive else target.iterdir()
        entries = []
        for index, item in enumerate(sorted(iterator, key=lambda p: str(p).lower())):
            if index >= max_entries:
                entries.append("... truncated ...")
                break
            kind = "dir " if item.is_dir() else "file"
            if self._is_within(item, self.config.sandbox_dir):
                relative = item.relative_to(self.config.sandbox_dir)
            else:
                relative = item.relative_to(self.config.root_dir)
            size = item.stat().st_size if item.is_file() else 0
            entries.append(f"{kind} {relative} size={size}")
        if not entries:
            entries.append("(empty)")
        return f"Listing for {target}:\n" + "\n".join(entries)

    async def _read_file(self, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        target = self._resolve_path(path)
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = max(1, start_line)
        stop = min(len(lines), end_line if end_line is not None else start + 199)
        rendered = [f"{index:4}: {lines[index - 1]}" for index in range(start, stop + 1)]
        if not rendered:
            rendered.append("(no content in requested range)")
        return f"File {target} lines {start}-{stop}:\n" + "\n".join(rendered)

    async def _search_text(
        self,
        pattern: str,
        path: str = ".",
        ignore_case: bool = True,
        max_hits: int = 60,
    ) -> str:
        target = self._resolve_path(path)
        flags = re.IGNORECASE if ignore_case else 0
        regex = re.compile(pattern, flags)
        files = [target] if target.is_file() else [item for item in target.rglob("*") if item.is_file()]
        hits: list[str] = []
        for file_path in files:
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for line_no, line in enumerate(lines, start=1):
                if regex.search(line):
                    if self._is_within(file_path, self.config.sandbox_dir):
                        relative = file_path.relative_to(self.config.sandbox_dir)
                    else:
                        relative = file_path.relative_to(self.config.root_dir)
                    hits.append(f"{relative}:{line_no}: {line.strip()}")
                    if len(hits) >= max_hits:
                        return "Search hits:\n" + "\n".join(hits + ["... truncated ..."])
        if not hits:
            return "Search hits:\n(no matches)"
        return "Search hits:\n" + "\n".join(hits)

    async def _write_file(self, path: str, content: str, append: bool = False) -> str:
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8", newline="") as handle:
            handle.write(content)
        action = "appended to" if append else "wrote"
        return f"{action} {target} ({len(content)} chars)"

    async def _insert_text(
        self,
        path: str,
        text: str,
        after_line: int | None = None,
        before_line: int | None = None,
    ) -> str:
        if after_line is not None and before_line is not None:
            raise ValueError("Use either after_line or before_line, not both.")
        target = self._resolve_path(path)
        original = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if before_line is not None:
            index = max(0, before_line - 1)
        elif after_line is not None:
            index = max(0, after_line)
        else:
            index = len(original)
        insertion = text if text.endswith("\n") else f"{text}\n"
        original.insert(index, insertion)
        target.write_text("".join(original), encoding="utf-8")
        return f"inserted text into {target} at line index {index + 1}"

    async def _replace_in_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        count: int = 0,
    ) -> str:
        target = self._resolve_path(path)
        original = target.read_text(encoding="utf-8", errors="replace")
        original_count = original.count(old_text)
        if original_count == 0:
            raise ValueError("old_text not found")
        if count > 0:
            updated = original.replace(old_text, new_text, count)
            replacements = min(original_count, count)
        else:
            updated = original.replace(old_text, new_text)
            replacements = original_count
        target.write_text(updated, encoding="utf-8")
        return f"replaced {replacements} occurrence(s) in {target}"

    async def _run_command(
        self,
        command: str,
        cwd: str = ".",
        timeout_sec: int = 0,
    ) -> str:
        target_cwd = self._resolve_path(cwd)
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        sandbox_scripts = self.config.sandbox_dir / ".venv" / "Scripts"
        if sandbox_scripts.exists():
            env["VIRTUAL_ENV"] = str(self.config.sandbox_dir / ".venv")
            env["PATH"] = f"{sandbox_scripts}{os.pathsep}{env.get('PATH', '')}"

        await self._emit(
            {
                "type": "tool_event",
                "tool": "run_command",
                "phase": "start",
                "command": command,
                "cwd": str(target_cwd),
                "monitor_schedule_sec": list(self.config.monitor_intervals),
            }
        )

        process = subprocess.Popen(
            command,
            cwd=str(target_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env=env,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        start_time = time.monotonic()
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        emitted_lines = 0
        max_lines = 240

        async def pump_stream(stream: Any, channel: str, sink: list[str]) -> None:
            nonlocal emitted_lines
            if stream is None:
                return
            while True:
                line = await asyncio.to_thread(stream.readline)
                if line == "":
                    break
                text = line.rstrip("\r\n")
                sink.append(text)
                if len(sink) > max_lines:
                    del sink[0]
                if emitted_lines < max_lines:
                    emitted_lines += 1
                    await self._emit(
                        {
                            "type": "tool_event",
                            "tool": "run_command",
                            "phase": "output",
                            "channel": channel,
                            "text": _clip(text, 800),
                        }
                    )
                elif emitted_lines == max_lines:
                    emitted_lines += 1
                    await self._emit(
                        {
                            "type": "tool_event",
                            "tool": "run_command",
                            "phase": "output_truncated",
                            "channel": channel,
                            "text": "stdout/stderr UI output truncated; backend still keeps the latest tail for summary.",
                        }
                    )

        async def heartbeat_loop() -> None:
            for interval in self.config.monitor_intervals:
                wait_time = start_time + interval - time.monotonic()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                if process.poll() is not None:
                    return
                snapshot = await asyncio.to_thread(self.monitor.snapshot, process.pid)
                await self._emit(
                    {
                        "type": "tool_event",
                        "tool": "run_command",
                        "phase": "heartbeat",
                        "after_sec": interval,
                        "snapshot": snapshot,
                        "summary": self.monitor.format_snapshot(snapshot),
                    }
                )

        stdout_task = asyncio.create_task(pump_stream(process.stdout, "stdout", stdout_lines))
        stderr_task = asyncio.create_task(pump_stream(process.stderr, "stderr", stderr_lines))
        heartbeat_task = asyncio.create_task(heartbeat_loop())

        timed_out = False
        try:
            if timeout_sec and timeout_sec > 0:
                while process.poll() is None:
                    if time.monotonic() - start_time >= timeout_sec:
                        raise TimeoutError
                    await asyncio.sleep(0.2)
            else:
                await asyncio.to_thread(process.wait)
        except TimeoutError:
            timed_out = True
            await self._emit(
                {
                    "type": "tool_event",
                    "tool": "run_command",
                    "phase": "timeout",
                    "timeout_sec": timeout_sec,
                    "pid": process.pid,
                }
            )
            await self._terminate_process_tree(process.pid)
            await asyncio.to_thread(process.wait)
        finally:
            await stdout_task
            await stderr_task
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

        duration = round(time.monotonic() - start_time, 2)
        final_snapshot = await asyncio.to_thread(self.monitor.snapshot, process.pid)
        await self._emit(
            {
                "type": "tool_event",
                "tool": "run_command",
                "phase": "finish",
                "exit_code": process.returncode,
                "duration_sec": duration,
                "timed_out": timed_out,
                "snapshot": final_snapshot,
                "summary": self.monitor.format_snapshot(final_snapshot),
            }
        )

        stdout_text = _clip("\n".join(stdout_lines), self.config.max_output_chars)
        stderr_text = _clip("\n".join(stderr_lines), self.config.max_output_chars)
        summary = [
            f"command={command}",
            f"cwd={target_cwd}",
            f"exit_code={process.returncode}",
            f"duration_sec={duration}",
            f"timed_out={timed_out}",
            f"resources={self.monitor.format_snapshot(final_snapshot)}",
            "stdout_tail:",
            stdout_text or "(empty)",
            "stderr_tail:",
            stderr_text or "(empty)",
        ]
        return "\n".join(summary)

    async def _terminate_process_tree(self, pid: int) -> None:
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
