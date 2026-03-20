from __future__ import annotations

from dataclasses import dataclass
import re


_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(slots=True)
class ScientificScriptFallback:
    path: str
    smoke_test_command: str
    content: str
    default_seconds: int


def maybe_build_scientific_script_fallback(user_text: str) -> ScientificScriptFallback | None:
    lowered = user_text.lower()
    if "python" not in lowered and "py" not in lowered:
        return None
    if not any(keyword in user_text for keyword in ("科学计算", "科研", "仿真", "计算代码")):
        return None

    seconds = _extract_duration_seconds(user_text)
    if seconds is None:
        return None

    minutes = max(1, seconds // 60)
    file_name = f"generated_science_compute_{minutes}min.py"
    return ScientificScriptFallback(
        path=file_name,
        smoke_test_command=f"python {file_name} --seconds 5",
        content=_build_script_content(default_seconds=seconds),
        default_seconds=seconds,
    )


def _extract_duration_seconds(text: str) -> int | None:
    minute_match = re.search(r"([0-9]+)\s*分钟", text)
    if minute_match:
        return int(minute_match.group(1)) * 60

    chinese_match = re.search(r"([一二两三四五六七八九十])\s*分钟", text)
    if chinese_match:
        return _CHINESE_NUMBERS[chinese_match.group(1)] * 60

    if "5分钟" in text or "五分钟" in text:
        return 300
    return None


def _build_script_content(default_seconds: int) -> str:
    return f"""from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path


def monte_carlo_pi(samples: int, rng: random.Random) -> float:
    inside = 0
    for _ in range(samples):
        x = rng.random()
        y = rng.random()
        if x * x + y * y <= 1.0:
            inside += 1
    return 4.0 * inside / samples


def integrate_signal(steps: int) -> float:
    total = 0.0
    for index in range(steps):
        x = (index + 0.5) / steps
        total += math.exp(-x * x) * math.cos(6.0 * x) + math.sin(15.0 * x) ** 2
    return total / steps


def advance_logistic(state: float, steps: int) -> float:
    value = state
    for _ in range(steps):
        value = 3.91 * value * (1.0 - value)
    return value


def run_workload(seconds: int, samples: int, steps: int) -> dict[str, float]:
    started = time.perf_counter()
    rng = random.Random(42)
    logistic_state = 0.314159
    rounds = 0
    pi_acc = 0.0
    integral_acc = 0.0

    while True:
        elapsed = time.perf_counter() - started
        if elapsed >= seconds:
            break

        loop_started = time.perf_counter()
        pi_estimate = monte_carlo_pi(samples, rng)
        integral_estimate = integrate_signal(steps)
        logistic_state = advance_logistic(logistic_state, steps)

        rounds += 1
        pi_acc += pi_estimate
        integral_acc += integral_estimate

        loop_elapsed = time.perf_counter() - loop_started
        print(
            f"progress={{elapsed:6.1f}}s/{{seconds}}s "
            f"round={{rounds:04d}} loop={{loop_elapsed:.3f}}s "
            f"pi={{pi_estimate:.6f}} integral={{integral_estimate:.6f}} logistic={{logistic_state:.6f}}",
            flush=True,
        )

    finished = time.perf_counter() - started
    return {{
        "target_seconds": seconds,
        "elapsed_seconds": round(finished, 3),
        "rounds": rounds,
        "mean_pi": pi_acc / max(1, rounds),
        "mean_integral": integral_acc / max(1, rounds),
        "final_logistic_state": logistic_state,
    }}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default={default_seconds})
    parser.add_argument("--samples", type=int, default=180000)
    parser.add_argument("--steps", type=int, default=120000)
    args = parser.parse_args()

    result = run_workload(args.seconds, args.samples, args.steps)
    output_path = Path("science_compute_result.json")
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("done", flush=True)
    print(output_path.read_text(encoding="utf-8"), flush=True)


if __name__ == "__main__":
    main()
"""
