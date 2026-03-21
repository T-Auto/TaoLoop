from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import json
import re
import time

import httpx

from .config import Config
from .logging_utils import FileLogger


_WRITE_TOOLS = {"write_file", "insert_text", "replace_in_file"}
_PATH_RE = re.compile(r'"path"\s*:\s*"((?:[^"\\]|\\.)*)"')
_APPEND_RE = re.compile(r'"append"\s*:\s*(true|false)')


def _make_parse_error_arguments(
    tool_name: str,
    raw: str,
    exc: json.JSONDecodeError,
) -> dict:
    """从截断/格式错误的 JSON 中尽量提取可用字段，并返回带恢复指引的参数字典。"""
    path_match = _PATH_RE.search(raw)
    extracted_path = path_match.group(1) if path_match else None

    append_match = _APPEND_RE.search(raw)
    is_append = append_match and append_match.group(1) == "true"

    hint_lines = [
        f"工具参数 JSON 解析失败（内容可能被 API 截断）：{exc}",
        f"原始参数预览（前500字符）：{raw[:500]}",
        "",
    ]
    if extracted_path:
        action = "追加到" if is_append else "创建"
        hint_lines.append(f"检测到目标文件：{extracted_path}（{action}模式）")
    if tool_name in _WRITE_TOOLS:
        hint_lines += [
            "【恢复策略】内容过长导致单次调用 JSON 被截断，请严格按以下步骤重试：",
            "  1. 将要写入的内容拆分为多个片段，每段不超过 2000 字符；",
            "  2. 第一段用 write_file（append=false）写入；",
            "  3. 后续每段用 write_file（append=true）追加；",
            "  4. 每次调用只传一个片段，不要在一次调用中传入完整文件。",
        ]
    else:
        hint_lines.append("请检查参数格式并重试。")

    return {
        "_argument_parse_error": True,
        "_argument_parse_error_message": "\n".join(hint_lines),
        "_extracted_path": extracted_path,
    }


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelResponse:
    content: str
    tool_calls: list[ToolCall]
    model: str
    usage: dict[str, Any]


class DeepSeekClient:
    def __init__(self, config: Config, logger: FileLogger | None = None):
        self.config = config
        self.logger = logger

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        return await asyncio.to_thread(self._complete_sync, messages, tools)

    def _complete_sync(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        if not self.config.api_key:
            raise RuntimeError("API_KEY is missing.")
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
            "max_tokens": 8192,
            "stream": False,
        }
        attempts = max(1, self.config.request_retries + 1)
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            if self.logger:
                self.logger.log(
                    "llm_request_start",
                    model=self.config.model,
                    attempt=attempt,
                    attempts=attempts,
                    message_count=len(messages),
                    tool_count=len(tools),
                    last_role=messages[-1]["role"] if messages else None,
                )
            try:
                with httpx.Client(
                    timeout=self.config.request_timeout_sec,
                    http2=False,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                        "Connection": "close",
                    },
                ) as client:
                    response = client.post(
                        f"{self.config.api_base_url.rstrip('/')}/chat/completions",
                        json=payload,
                    )
                    response.raise_for_status()
                    if not response.content:
                        raise httpx.RemoteProtocolError("empty response body")
                    body = response.json()
                if self.logger:
                    choice = body.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    self.logger.log(
                        "llm_request_success",
                        model=self.config.model,
                        attempt=attempt,
                        attempts=attempts,
                        elapsed_sec=round(time.perf_counter() - started, 3),
                        content_preview=(message.get("content") or "")[:400],
                        tool_call_names=[
                            item.get("function", {}).get("name")
                            for item in message.get("tool_calls", [])
                        ],
                        usage=body.get("usage", {}),
                    )
                break
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                if self.logger:
                    self.logger.exception(
                        "llm_request_http_error",
                        exc,
                        model=self.config.model,
                        attempt=attempt,
                        attempts=attempts,
                        status_code=exc.response.status_code,
                        response_text=detail[:1000],
                    )
                raise RuntimeError(f"DeepSeek HTTP {exc.response.status_code}: {detail}") from exc
            except json.JSONDecodeError as exc:
                if self.logger:
                    self.logger.exception(
                        "llm_request_bad_json",
                        exc,
                        model=self.config.model,
                        attempt=attempt,
                        attempts=attempts,
                        elapsed_sec=round(time.perf_counter() - started, 3),
                    )
                if attempt >= attempts:
                    raise RuntimeError(
                        f"DeepSeek returned invalid JSON after {attempt}/{attempts} attempts: {exc}"
                    ) from exc
                time.sleep(self.config.request_retry_base_delay_sec * attempt)
            except Exception as exc:
                if self.logger:
                    self.logger.exception(
                        "llm_request_error",
                        exc,
                        model=self.config.model,
                        attempt=attempt,
                        attempts=attempts,
                        elapsed_sec=round(time.perf_counter() - started, 3),
                    )
                if not self._is_transient_error(exc) or attempt >= attempts:
                    raise RuntimeError(self._format_transient_error(exc, attempt, attempts)) from exc
                time.sleep(self.config.request_retry_base_delay_sec * attempt)
        else:  # pragma: no cover
            raise RuntimeError("DeepSeek request failed without a captured error.")

        choice = body["choices"][0]
        message = choice["message"]
        tool_calls = []
        for item in message.get("tool_calls", []):
            arguments_text = item["function"].get("arguments", "{}")
            try:
                arguments = json.loads(arguments_text)
            except json.JSONDecodeError as parse_exc:
                arguments = _make_parse_error_arguments(
                    item["function"].get("name", ""),
                    arguments_text,
                    parse_exc,
                )
            tool_calls.append(
                ToolCall(
                    id=item["id"],
                    name=item["function"]["name"],
                    arguments=arguments,
                )
            )
        return ModelResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            model=body.get("model", self.config.model),
            usage=body.get("usage", {}),
        )

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        transient_types = (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.ConnectError,
            ConnectionResetError,
            TimeoutError,
        )
        if isinstance(exc, transient_types):
            return True
        if isinstance(exc, OSError):
            return True
        return False

    @staticmethod
    def _format_transient_error(exc: Exception, attempt: int, attempts: int) -> str:
        if isinstance(exc, httpx.RemoteProtocolError):
            return (
                "DeepSeek connection closed mid-response "
                f"after {attempt}/{attempts} attempts: {exc}"
            )
        return f"DeepSeek request failed after {attempt}/{attempts} attempts: {exc}"


class MockClient:
    def __init__(self, config: Config):
        self.config = config

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        del tools
        last_user_index = max(
            (index for index, message in enumerate(messages) if message["role"] == "user"),
            default=-1,
        )
        if last_user_index < 0:
            return ModelResponse(
                content="离线模式已就绪。",
                tool_calls=[],
                model="mock-offline",
                usage={},
            )

        trailing = messages[last_user_index + 1 :]
        tool_messages = [item for item in trailing if item["role"] == "tool"]
        if tool_messages:
            summary_lines = ["离线模式执行完成。"]
            for item in tool_messages[-4:]:
                name = item.get("name", "tool")
                text = item.get("content", "").strip()
                summary_lines.append(f"[{name}] {text[:900]}")
            return ModelResponse(
                content="\n\n".join(summary_lines),
                tool_calls=[],
                model="mock-offline",
                usage={},
            )

        user_text = messages[last_user_index]["content"]
        return ModelResponse(
            content="",
            tool_calls=self._plan_calls(user_text),
            model="mock-offline",
            usage={},
        )

    def _plan_calls(self, text: str) -> list[ToolCall]:
        calls: list[ToolCall] = []
        lowered = text.lower()

        if (
            "测试阶段" in text
            and "40秒" in text
            and "python" in lowered
            and ("物理实验" in text or "仿真" in text)
        ):
            calls.append(
                ToolCall(
                    id="mock_write_async_test_script",
                    name="write_file",
                    arguments={
                        "path": "physics_sim_test.py",
                        "content": self._build_async_test_script(),
                    },
                )
            )
            calls.append(
                ToolCall(
                    id="mock_start_async_test_script",
                    name="start_background_command",
                    arguments={
                        "command": "python physics_sim_test.py",
                        "cwd": ".",
                        "timeout_sec": 0,
                    },
                )
            )
            return calls

        if any(keyword in text for keyword in ("后台脚本", "后台任务", "正在运行的脚本", "running scripts")):
            calls.append(
                ToolCall(
                    id="mock_list_background_jobs",
                    name="list_background_jobs",
                    arguments={"include_finished": True, "max_jobs": 10},
                )
            )
            return calls

        if any(keyword in text for keyword in ("目录", "列出", "list", "files")):
            calls.append(
                ToolCall(
                    id="mock_list_directory",
                    name="list_directory",
                    arguments={"path": ".", "recursive": False, "max_entries": 80},
                )
            )

        if any(keyword in text for keyword in ("搜索", "查找", "search")):
            pattern_match = re.search(r"(?:搜索|查找|search)\s+(.+)", text, re.IGNORECASE)
            pattern = pattern_match.group(1).strip() if pattern_match else "TODO|FIXME"
            calls.append(
                ToolCall(
                    id="mock_search_text",
                    name="search_text",
                    arguments={"path": ".", "pattern": pattern, "ignore_case": True, "max_hits": 40},
                )
            )

        command = None
        fenced = re.search(r"`([^`]+)`", text)
        if fenced:
            command = fenced.group(1).strip()
        elif "run" in lowered or "运行" in text:
            command_match = re.search(r"(?:运行|run)\s+(.+)", text, re.IGNORECASE)
            if command_match:
                command = command_match.group(1).strip()
        if command:
            calls.append(
                ToolCall(
                    id="mock_run_command",
                    name="run_command",
                    arguments={"command": command, "cwd": ".", "timeout_sec": 0},
                )
            )

        if not calls:
            calls.append(
                ToolCall(
                    id="mock_list_directory",
                    name="list_directory",
                    arguments={"path": ".", "recursive": False, "max_entries": 40},
                )
            )
        return calls

    @staticmethod
    def _build_async_test_script() -> str:
        return """from __future__ import annotations

import json
import time
from pathlib import Path


def main() -> int:
    started = time.perf_counter()
    checkpoints = [10, 20, 30, 40]
    for checkpoint in checkpoints:
        while time.perf_counter() - started < checkpoint:
            time.sleep(0.2)
        elapsed = time.perf_counter() - started
        print(
            f"[physics-sim] elapsed={elapsed:4.1f}s checkpoint={checkpoint}s energy={(checkpoint * 1.618):.3f}",
            flush=True,
        )
    result = {
        "target_seconds": 40,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": "completed",
    }
    Path("physics_sim_test_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("simulation complete", flush=True)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def build_client(config: Config, logger: FileLogger | None = None) -> DeepSeekClient | MockClient:
    if config.offline_mode:
        return MockClient(config)
    return DeepSeekClient(config, logger=logger)
