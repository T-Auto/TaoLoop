from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


DEFAULT_MONITOR_INTERVALS = (20, 60, 180, 600, 1800, 7200, 18000, 36000)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Config:
    root_dir: Path
    sandbox_dir: Path
    state_dir: Path
    sessions_dir: Path
    api_key: str | None
    api_base_url: str
    model: str
    offline_mode: bool
    context_limit: int
    max_output_chars: int
    request_timeout_sec: int
    request_retries: int
    request_retry_base_delay_sec: float
    max_tool_rounds: int
    monitor_intervals: tuple[int, ...]
    sandbox_python: Path
    backend_python: Path

    @classmethod
    def load(cls, root_dir: Path | None = None) -> "Config":
        root = (root_dir or Path(__file__).resolve().parent.parent).resolve()
        _load_dotenv(root / ".env")

        sandbox_dir = root / "sandbox"
        state_dir = root / ".zhouxing"
        sessions_dir = state_dir / "sessions"

        sandbox_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        sandbox_python = sandbox_dir / ".venv" / "Scripts" / "python.exe"
        backend_python = root / ".venv" / "Scripts" / "python.exe"

        return cls(
            root_dir=root,
            sandbox_dir=sandbox_dir,
            state_dir=state_dir,
            sessions_dir=sessions_dir,
            api_key=os.getenv("API_KEY"),
            api_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            offline_mode=_env_bool("ZHOUXING_OFFLINE", False),
            context_limit=int(os.getenv("ZHOUXING_CONTEXT_LIMIT", "64000")),
            max_output_chars=int(os.getenv("ZHOUXING_MAX_OUTPUT_CHARS", "12000")),
            request_timeout_sec=int(os.getenv("ZHOUXING_REQUEST_TIMEOUT_SEC", "180")),
            request_retries=int(os.getenv("ZHOUXING_REQUEST_RETRIES", "3")),
            request_retry_base_delay_sec=float(os.getenv("ZHOUXING_REQUEST_RETRY_BASE_DELAY_SEC", "1.5")),
            max_tool_rounds=int(os.getenv("ZHOUXING_MAX_TOOL_ROUNDS", "12")),
            monitor_intervals=DEFAULT_MONITOR_INTERVALS,
            sandbox_python=sandbox_python,
            backend_python=backend_python,
        )
