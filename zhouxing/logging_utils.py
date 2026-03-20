from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json
import threading
import traceback


def _sanitize(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item) for item in value]
    return str(value)


class FileLogger:
    def __init__(self, state_dir: Path):
        self.logs_dir = state_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = self.logs_dir / f"backend_{timestamp}.jsonl"
        self.latest_path = self.logs_dir / "backend_latest.jsonl"
        self._lock = threading.Lock()
        self.log("logger_ready", log_path=str(self.path), latest_path=str(self.latest_path))

    def log(self, event: str, **fields: Any) -> None:
        record = {
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "event": event,
        }
        record.update({key: _sanitize(value) for key, value in fields.items()})
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            for path in (self.path, self.latest_path):
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")

    def exception(self, event: str, exc: BaseException, **fields: Any) -> None:
        self.log(
            event,
            error_type=type(exc).__name__,
            error=str(exc),
            traceback=traceback.format_exc(),
            **fields,
        )
