from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from queue import Empty, Queue
from threading import Thread


ROOT = Path(__file__).resolve().parent.parent
PROMPT = (
    "目前你的CLI在测试阶段，请写一个运行40秒的python程序并运行，这个python程序本身会每隔10秒输出一次日志，"
    "模拟仿真物理实验，来验证你的tools工具是否正常"
)


def resolve_backend_python() -> Path:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
        ROOT / ".venv" / "bin" / "python3",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"backend python not found in {candidates}")


PYTHON = resolve_backend_python()


def send(handle, payload: dict) -> None:
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    handle.flush()


def pump_lines(handle, queue: Queue[str | None]) -> None:
    for line in handle:
        queue.put(line)
    queue.put(None)


def main() -> int:
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

    lines: Queue[str | None] = Queue()
    Thread(target=pump_lines, args=(process.stdout, lines), daemon=True).start()

    send(process.stdin, {"type": "hello"})
    send(process.stdin, {"type": "create_session", "title": "smoke-async-prompt"})
    send(process.stdin, {"type": "user_message", "content": PROMPT})

    deadline = time.time() + 80
    saw_background_start = False
    saw_heartbeat = False
    saw_finish = False
    saw_running_job = False
    saw_result_file = False

    try:
        while time.time() < deadline:
            try:
                raw = lines.get(timeout=1)
            except Empty:
                if process.poll() is not None:
                    break
                continue
            if raw is None:
                break
            payload = json.loads(raw)
            event_type = payload.get("type")
            if event_type == "jobs":
                jobs = payload.get("jobs", [])
                running = [job for job in jobs if job.get("status") == "running"]
                if running:
                    saw_running_job = True
                    print(f"[jobs] running={len(running)} command={running[0].get('command')}")
                else:
                    print(f"[jobs] total={len(jobs)} running=0")
            elif event_type == "message":
                message = payload.get("message", {})
                role = message.get("role")
                name = message.get("name")
                meta = message.get("meta", {})
                content = message.get("content", "")
                if role == "tool" and name == "start_background_command":
                    saw_background_start = True
                    print("[message] background tool started")
                elif role == "event" and meta.get("background_job_phase") == "heartbeat":
                    saw_heartbeat = True
                    print("[message] heartbeat")
                elif role == "event" and meta.get("background_job_phase") == "finish":
                    saw_finish = True
                    print("[message] finish")
                    result_path = ROOT / "sandbox" / "physics_sim_test_result.json"
                    saw_result_file = result_path.exists()
                    if saw_result_file:
                        print(f"[result] {result_path}")
                        break
                elif role == "assistant":
                    snippet = content.replace("\n", " ")[:180]
                    print(f"[assistant] {snippet}")
            elif event_type == "error":
                print(f"[error] {payload.get('message')}")
                return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    success = saw_background_start and saw_running_job and saw_heartbeat and saw_finish and saw_result_file
    print(
        f"background_start={saw_background_start} running_job={saw_running_job} "
        f"heartbeat={saw_heartbeat} finish={saw_finish} result_file={saw_result_file}"
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
