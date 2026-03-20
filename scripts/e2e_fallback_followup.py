from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from threading import Thread


ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def send(handle, payload: dict) -> None:
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    handle.flush()


def pump_lines(handle, queue: Queue[str | None]) -> None:
    for line in handle:
        queue.put(line)
    queue.put(None)


def start_backend(env: dict[str, str]) -> tuple[subprocess.Popen[str], Queue[str | None]]:
    process = subprocess.Popen(
        [str(PYTHON), "-X", "utf8", "-m", "zhouxing.backend"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    lines: Queue[str | None] = Queue()
    Thread(target=pump_lines, args=(process.stdout, lines), daemon=True).start()
    return process, lines


def wait_for_event(
    process: subprocess.Popen[str],
    lines: Queue[str | None],
    predicate,
    *,
    timeout_sec: int,
) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            line = lines.get(timeout=1)
        except Empty:
            if process.poll() is not None:
                break
            continue
        if line is None:
            break
        payload = json.loads(line)
        if predicate(payload):
            return payload
    stderr = process.stderr.read() if process.stderr else ""
    raise RuntimeError(f"timed out waiting for event; stderr={stderr.strip()[:2000]}")


def stop_process(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    base_env = os.environ.copy()
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    base_env["PYTHONUTF8"] = "1"
    base_env.pop("ZHOUXING_OFFLINE", None)

    fallback_env = dict(base_env)
    fallback_env["DEEPSEEK_BASE_URL"] = "http://127.0.0.1:9/v1"

    fallback_process, fallback_lines = start_backend(fallback_env)
    try:
        send(fallback_process.stdin, {"type": "hello"})
        send(fallback_process.stdin, {"type": "create_session", "title": "e2e-fallback-followup"})
        loaded = wait_for_event(
            fallback_process,
            fallback_lines,
            lambda payload: payload.get("type") == "session_loaded",
            timeout_sec=10,
        )
        session_id = loaded["session"]["id"]
        send(
            fallback_process.stdin,
            {
                "type": "user_message",
                "content": "帮我写一个大约需要5分钟的python科学计算代码",
            },
        )
        wait_for_event(
            fallback_process,
            fallback_lines,
            lambda payload: payload.get("type") == "message"
            and payload.get("message", {}).get("role") == "assistant"
            and "已生成 `generated_science_compute_5min.py`" in payload.get("message", {}).get("content", ""),
            timeout_sec=180,
        )
    finally:
        stop_process(fallback_process)

    live_process, live_lines = start_backend(base_env)
    try:
        send(live_process.stdin, {"type": "hello"})
        send(live_process.stdin, {"type": "load_session", "session_id": session_id})
        wait_for_event(
            live_process,
            live_lines,
            lambda payload: payload.get("type") == "session_loaded",
            timeout_sec=10,
        )
        send(
            live_process.stdin,
            {
                "type": "user_message",
                "content": "搞定了？请用一句话确认",
            },
        )
        reply = wait_for_event(
            live_process,
            live_lines,
            lambda payload: payload.get("type") == "message"
            and payload.get("message", {}).get("role") == "assistant"
            and "已生成 `generated_science_compute_5min.py`" not in payload.get("message", {}).get("content", ""),
            timeout_sec=180,
        )
        print(reply["message"]["content"])
    finally:
        stop_process(live_process)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
