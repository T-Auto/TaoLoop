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
SANDBOX = ROOT / "sandbox"
SMOKE_SCRIPT = SANDBOX / "smoke_long_sim.py"

SMOKE_LONG_SIM = """from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=22)
    args = parser.parse_args()

    started = time.perf_counter()
    rounds = 0
    while True:
        elapsed = time.perf_counter() - started
        if elapsed >= args.seconds:
            break
        value = sum(math.sin(i * 0.001) * math.cos(i * 0.002) for i in range(20000))
        rounds += 1
        print(f"tick elapsed={elapsed:5.1f}s rounds={rounds:03d} value={value:.6f}", flush=True)
        time.sleep(1.0)

    result = {
        "target_seconds": args.seconds,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "rounds": rounds,
    }
    Path("smoke_long_sim_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("done", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def send(handle, payload: dict) -> None:
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    handle.flush()


def pump_lines(handle, queue: Queue[str | None]) -> None:
    for line in handle:
        queue.put(line)
    queue.put(None)


def main() -> int:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    SMOKE_SCRIPT.write_text(SMOKE_LONG_SIM, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["ZHOUXING_OFFLINE"] = env.get("ZHOUXING_OFFLINE", "1")

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

    command = "python smoke_long_sim.py --seconds 11"
    lines: Queue[str | None] = Queue()
    Thread(target=pump_lines, args=(process.stdout, lines), daemon=True).start()

    send(process.stdin, {"type": "hello"})
    send(process.stdin, {"type": "create_session", "title": "smoke-backend"})
    send(
        process.stdin,
        {
            "type": "user_message",
            "content": f"请列出目录并运行 `{command}`",
        },
    )

    deadline = time.time() + 60
    saw_finish = False
    saw_heartbeat = False
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
        event_type = payload.get("type")
        if event_type == "tool_event":
            print(f"[tool_event] {payload.get('phase')} {payload.get('summary') or payload.get('text') or ''}")
            if payload.get("phase") == "heartbeat" and payload.get("after_sec") == 20:
                saw_heartbeat = True
            if payload.get("phase") == "finish":
                saw_finish = True
        elif event_type == "message":
            message = payload.get("message", {})
            role = message.get("role")
            content = (message.get("content") or "").replace("\n", " ")[:220]
            print(f"[message] {role}: {content}")
            if role == "assistant":
                process.terminate()
                process.wait(timeout=5)
                return 0 if (saw_finish and saw_heartbeat) else 1
        elif event_type == "error":
            print(f"[error] {payload.get('message')}")
            process.terminate()
            process.wait(timeout=5)
            return 1
        else:
            print(f"[{event_type}]")

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    stderr = process.stderr.read() if process.stderr else ""
    if stderr.strip():
        print(stderr.strip())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
