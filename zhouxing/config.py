from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re


DEFAULT_MONITOR_INTERVALS = (20, 60, 180, 600, 1800, 7200, 18000, 36000, 72000, 108000)
DEFAULT_MONITOR_REPEAT_INTERVAL_SEC = 36000
DEFAULT_AUTONOMOUS_RUN_LIMIT_SEC = 1800


def _venv_bin_dir(venv_root: Path) -> Path:
    return venv_root / ("Scripts" if os.name == "nt" else "bin")


def _venv_python_path(venv_root: Path) -> Path:
    return _venv_bin_dir(venv_root) / ("python.exe" if os.name == "nt" else "python")


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


def _parse_autonomous_run_limit(raw_value: str | None) -> int:
    value = (raw_value or "30min").strip().lower()
    if not value:
        return DEFAULT_AUTONOMOUS_RUN_LIMIT_SEC
    if value in {"0", "none", "unlimited", "infinite", "inf"}:
        return 0
    if value.isdigit():
        return max(0, int(value))

    match = re.fullmatch(r"(\d+)\s*(s|sec|secs|m|min|mins|h|hr|hrs|d|day|days)", value)
    if match is None:
        raise ValueError(
            "ZHOUXING_AUTONOMOUS_RUN_LIMIT must be an integer second count or one of "
            "10min/30min/1h/24h/unlimited."
        )

    amount = int(match.group(1))
    unit = match.group(2)
    multiplier = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }[unit]
    return max(0, amount * multiplier)


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
    autonomous_run_limit_sec: int
    monitor_intervals: tuple[int, ...]
    monitor_repeat_interval_sec: int
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

        sandbox_python = _venv_python_path(sandbox_dir / ".venv")
        backend_python = _venv_python_path(root / ".venv")

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
            autonomous_run_limit_sec=_parse_autonomous_run_limit(os.getenv("ZHOUXING_AUTONOMOUS_RUN_LIMIT")),
            monitor_intervals=DEFAULT_MONITOR_INTERVALS,
            monitor_repeat_interval_sec=int(
                os.getenv("ZHOUXING_MONITOR_REPEAT_INTERVAL_SEC", str(DEFAULT_MONITOR_REPEAT_INTERVAL_SEC))
            ),
            sandbox_python=sandbox_python,
            backend_python=backend_python,
        )
