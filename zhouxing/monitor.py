from __future__ import annotations

from pathlib import Path
from typing import Any
import shutil
import subprocess
import time

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None


def _human_bytes(value: int) -> str:
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for suffix in suffixes:
        if size < 1024 or suffix == suffixes[-1]:
            return f"{size:.1f}{suffix}"
        size /= 1024
    return f"{value}B"


class ResourceMonitor:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self._gpu_checked = False
        self._has_nvidia_smi = False
        if psutil:
            psutil.cpu_percent(interval=None)

    def snapshot(self, pid: int | None = None) -> dict[str, Any]:
        if psutil:
            return self._snapshot_psutil(pid)
        return self._snapshot_basic(pid)

    def format_snapshot(self, payload: dict[str, Any]) -> str:
        return "; ".join(self.format_snapshot_lines(payload))

    def format_snapshot_lines(self, payload: dict[str, Any]) -> list[str]:
        system = payload.get("system", {})
        process = payload.get("process", {})
        disk = payload.get("disk", {})
        lines = [
            f"backend={payload.get('backend', 'unknown')}",
            f"system_cpu={system.get('cpu_percent', 'n/a')}%",
            f"system_mem={system.get('memory_used_human', 'n/a')}/{system.get('memory_total_human', 'n/a')} ({system.get('memory_percent', 'n/a')}%)",
            f"process_pid={process.get('pid', 'n/a')}",
            f"process_status={process.get('status', 'n/a')}",
            f"process_cpu={process.get('cpu_percent', 'n/a')}%",
            f"process_rss={process.get('rss_human', 'n/a')}",
            f"process_io={process.get('io_read_human', 'n/a')} read / {process.get('io_write_human', 'n/a')} write",
            f"process_threads={process.get('threads', 'n/a')}",
            f"process_children={process.get('children_count', 'n/a')}",
            f"disk_free={disk.get('free_human', 'n/a')}",
        ]
        top_threads = process.get("top_threads", [])
        if top_threads:
            parts = []
            for item in top_threads[:3]:
                parts.append(f"tid={item.get('id', 'n/a')} cpu={item.get('cpu_time_sec', 'n/a')}s")
            lines.append("thread_top=" + ", ".join(parts))
        if payload.get("gpu"):
            gpu = payload["gpu"]
            lines.append(
                f"gpu={gpu.get('name', 'n/a')} util={gpu.get('utilization_percent', 'n/a')}% mem={gpu.get('memory_used_human', 'n/a')}/{gpu.get('memory_total_human', 'n/a')} temp={gpu.get('temperature_c', 'n/a')}C"
            )
        return lines

    def _snapshot_psutil(self, pid: int | None = None) -> dict[str, Any]:
        assert psutil is not None
        system_memory = psutil.virtual_memory()
        disk_usage = shutil.disk_usage(self.root_dir)
        net = psutil.net_io_counters()
        system = {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
            "memory_percent": round(system_memory.percent, 1),
            "memory_used": system_memory.used,
            "memory_used_human": _human_bytes(system_memory.used),
            "memory_total": system_memory.total,
            "memory_total_human": _human_bytes(system_memory.total),
            "network_sent_human": _human_bytes(getattr(net, "bytes_sent", 0)),
            "network_recv_human": _human_bytes(getattr(net, "bytes_recv", 0)),
        }

        process_payload: dict[str, Any] = {"pid": pid}
        if pid:
            try:
                process = psutil.Process(pid)
                processes = [process, *process.children(recursive=True)]
                cpu_percent = sum(item.cpu_percent(interval=None) for item in processes)
                rss = 0
                vms = 0
                read_bytes = 0
                write_bytes = 0
                open_files = 0
                threads = 0
                top_threads: list[dict[str, Any]] = []
                for item in processes:
                    with item.oneshot():
                        mem = item.memory_info()
                        rss += getattr(mem, "rss", 0)
                        vms += getattr(mem, "vms", 0)
                        try:
                            io_counters = item.io_counters()
                            read_bytes += getattr(io_counters, "read_bytes", 0)
                            write_bytes += getattr(io_counters, "write_bytes", 0)
                        except Exception:
                            pass
                        try:
                            open_files += len(item.open_files())
                        except Exception:
                            pass
                        threads += item.num_threads()
                        try:
                            for thread_info in item.threads():
                                top_threads.append(
                                    {
                                        "process_pid": item.pid,
                                        "id": thread_info.id,
                                        "cpu_time_sec": round(thread_info.user_time + thread_info.system_time, 3),
                                    }
                                )
                        except Exception:
                            pass
                top_threads.sort(key=lambda item: item["cpu_time_sec"], reverse=True)
                process_payload = {
                    "pid": pid,
                    "status": process.status(),
                    "cpu_percent": round(cpu_percent, 1),
                    "rss": rss,
                    "rss_human": _human_bytes(rss),
                    "vms": vms,
                    "vms_human": _human_bytes(vms),
                    "io_read_bytes": read_bytes,
                    "io_read_human": _human_bytes(read_bytes),
                    "io_write_bytes": write_bytes,
                    "io_write_human": _human_bytes(write_bytes),
                    "open_files": open_files,
                    "threads": threads,
                    "children_count": max(0, len(processes) - 1),
                    "top_threads": top_threads[:5],
                }
            except Exception as exc:
                process_payload = {"pid": pid, "error": str(exc)}

        payload: dict[str, Any] = {
            "backend": "psutil",
            "captured_at_epoch": round(time.time(), 3),
            "system": system,
            "process": process_payload,
            "disk": {
                "free": disk_usage.free,
                "free_human": _human_bytes(disk_usage.free),
                "used": disk_usage.used,
                "used_human": _human_bytes(disk_usage.used),
                "total": disk_usage.total,
                "total_human": _human_bytes(disk_usage.total),
            },
        }
        gpu = self._snapshot_gpu()
        if gpu:
            payload["gpu"] = gpu
        return payload

    def _snapshot_basic(self, pid: int | None = None) -> dict[str, Any]:
        disk_usage = shutil.disk_usage(self.root_dir)
        return {
            "backend": "basic",
            "captured_at_epoch": round(time.time(), 3),
            "system": {
                "cpu_percent": "n/a",
                "memory_percent": "n/a",
                "memory_used_human": "n/a",
                "memory_total_human": "n/a",
            },
            "process": {
                "pid": pid,
                "status": "n/a",
                "cpu_percent": "n/a",
                "rss_human": "n/a",
                "io_read_human": "n/a",
                "io_write_human": "n/a",
                "threads": "n/a",
                "children_count": "n/a",
            },
            "disk": {
                "free_human": _human_bytes(disk_usage.free),
                "used_human": _human_bytes(disk_usage.used),
                "total_human": _human_bytes(disk_usage.total),
            },
        }

    def _snapshot_gpu(self) -> dict[str, Any] | None:
        if not self._gpu_checked:
            self._gpu_checked = True
            self._has_nvidia_smi = shutil.which("nvidia-smi") is not None
        if not self._has_nvidia_smi:
            return None

        command = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        except Exception:
            return None

        line = completed.stdout.strip().splitlines()[:1]
        if not line:
            return None
        parts = [item.strip() for item in line[0].split(",")]
        if len(parts) < 5:
            return None
        used_bytes = int(float(parts[2]) * 1024 * 1024)
        total_bytes = int(float(parts[3]) * 1024 * 1024)
        return {
            "name": parts[0],
            "utilization_percent": float(parts[1]),
            "memory_used_human": _human_bytes(used_bytes),
            "memory_total_human": _human_bytes(total_bytes),
            "temperature_c": float(parts[4]),
        }
