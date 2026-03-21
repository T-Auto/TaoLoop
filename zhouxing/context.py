from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Config
from .sessions import ChatMessage, SessionRecord


SYSTEM_PROMPT = """你是“周行”科研 Agent，职责是帮助用户在 sandbox 工作区内编写、修改、运行和优化科研代码。

工作原则：
1. 默认在 sandbox 工作区行动，相对路径视为 sandbox 相对路径；只有显式使用 project: 前缀时才访问项目根目录。
2. 优先调用工具获取真实信息，不要臆测文件内容、目录结构、运行结果或硬件状态。
3. 面向科研脚本，尽量保持修改短小、可运行、可验证。
4. 对于仿真、训练、批处理、扫描等可能超过 10 秒的任务，优先使用 start_background_command，不要用 run_command 阻塞 CLI。
5. run_command 只用于短检查、短烟测、快速命令；需要持续监控的任务交给后台作业工具，并结合心跳消息判断是否卡死、I/O 瓶颈、CPU/GPU 利用不足、内存风险。
6. start_background_command 一旦成功启动后台任务，就结束当前自主轮次并进入待机，不要继续循环 inspect_background_job；等待用户新输入或后续后台事件。
7. 当用户询问当前还有哪些脚本在跑、想查看后台任务状态时，使用 list_background_jobs 或 inspect_background_job。
8. 这个项目的 Python 与依赖管理默认使用项目根目录的 `uv` 和 `.venv`；执行 Python、安装依赖、查询包状态时优先在 `cwd=project:.` 下使用 `uv run`、`uv add`、`uv remove`，不要回退到系统 Python 或裸 `pip`。
9. 在 Windows 环境优先使用 PowerShell 兼容命令；避免 `ls -la`、`grep` 这类 Unix 风格参数组合。
10. 切换目录时优先使用工具的 cwd 参数，例如 `project:.`；不要在 command 字符串里写 `cd .. && ...`。
11. 如果目标脚本位于 `sandbox/`，优先使用 `cwd=sandbox:.` 并在命令里写相对文件名，例如 `uv run python physics_simulation.py`；不要在已经明确文件位置后再反复切回 `project:.` 拼接 `sandbox/...` 路径做试探。
12. 对于计划运行超过 10 秒的 Python 脚本，写完后直接使用 start_background_command；不要用 `python script.py --help` 或其他前台方式做长时间烟测，除非脚本显式支持该参数且能快速退出。除非用户明确要求，否则不要给 start_background_command 传很小的 `timeout_sec`。
13. `run_command` 的硬件信息不要当作常规检查结果反复展示；硬件信息主要依赖后台脚本状态报告与后台任务检查工具。
14. 回复保持简洁直接，给出实际修改、发现的问题和下一步。
15. 对于“新建一个小型 Python 科研脚本”这类直接任务，最多做一次必要环境检查，然后直接写文件；不要反复查看示例文件。
"""


def estimate_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")) // 4)


def _summarize_message(message: ChatMessage) -> str:
    snippet = " ".join(message.content.split())
    snippet = snippet[:220]
    if message.role == "tool":
        prefix = f"TOOL/{message.name or 'unknown'}"
    else:
        prefix = message.role.upper()
    return f"- {prefix}: {snippet}"


def _tool_call_ids(message: ChatMessage) -> set[str]:
    if message.role != "assistant":
        return set()
    raw_tool_calls = message.meta.get("tool_calls")
    if not isinstance(raw_tool_calls, list):
        return set()
    call_ids: set[str] = set()
    for item in raw_tool_calls:
        if not isinstance(item, dict):
            continue
        call_id = item.get("id")
        if isinstance(call_id, str) and call_id:
            call_ids.add(call_id)
    return call_ids


def _message_token_cost(message: ChatMessage) -> int:
    return estimate_tokens(message.content) + 24


def _group_llm_messages(transcript: list[ChatMessage]) -> list[list[ChatMessage]]:
    groups: list[list[ChatMessage]] = []
    index = 0
    while index < len(transcript):
        message = transcript[index]
        tool_call_ids = _tool_call_ids(message)
        if tool_call_ids:
            group = [message]
            matched_tool_call_ids: set[str] = set()
            index += 1
            while index < len(transcript):
                next_message = transcript[index]
                if (
                    next_message.role == "tool"
                    and next_message.tool_call_id in tool_call_ids
                    and next_message.tool_call_id not in matched_tool_call_ids
                ):
                    group.append(next_message)
                    matched_tool_call_ids.add(next_message.tool_call_id)
                    index += 1
                    continue
                if next_message.to_llm_message() is None:
                    index += 1
                    continue
                break
            if matched_tool_call_ids == tool_call_ids:
                groups.append(group)
            continue
        if message.role == "tool":
            index += 1
            continue
        if message.to_llm_message() is None:
            index += 1
            continue
        groups.append([message])
        index += 1
    return groups


def _adjust_compaction_start(messages: list[ChatMessage], start: int) -> int:
    if start <= 0 or start >= len(messages):
        return max(0, start)

    probe = start
    saw_tool_block = False
    while probe >= 0:
        message = messages[probe]
        if message.role == "tool":
            saw_tool_block = True
            probe -= 1
            continue
        if message.to_llm_message() is None:
            saw_tool_block = True
            probe -= 1
            continue
        if saw_tool_block and _tool_call_ids(message):
            return probe
        break
    return start


@dataclass(slots=True)
class ContextUsage:
    used_tokens: int
    limit_tokens: int
    cached_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "used_tokens": self.used_tokens,
            "limit_tokens": self.limit_tokens,
            "cached_tokens": self.cached_tokens,
            "usage_ratio": round(self.used_tokens / max(1, self.limit_tokens), 4),
        }


class ContextManager:
    def __init__(self, config: Config):
        self.config = config

    def compact(self, session: SessionRecord) -> None:
        if len(session.messages) <= 14:
            return

        total_tokens = estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(session.summary)
        total_tokens += sum(estimate_tokens(message.content) for message in session.messages)
        if total_tokens <= int(self.config.context_limit * 0.72):
            return

        keep_tail = max(10, min(16, len(session.messages)))
        tail_start = max(0, len(session.messages) - keep_tail)
        tail_start = _adjust_compaction_start(session.messages, tail_start)
        head = session.messages[:tail_start]
        tail = session.messages[tail_start:]
        if not head:
            return

        summary_lines = []
        if session.summary:
            summary_lines.append(session.summary.strip())
        summary_lines.append("压缩历史记录：")
        for message in head[-24:]:
            summary_lines.append(_summarize_message(message))

        session.summary = "\n".join(summary_lines)[-6000:]
        session.messages = tail
        session.meta["compacted_at"] = tail[-1].created_at if tail else session.updated_at

    def build(
        self,
        session: SessionRecord,
        *,
        upto_message_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], ContextUsage]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        cached_tokens = estimate_tokens(SYSTEM_PROMPT)

        if session.summary:
            summary_text = f"历史摘要：\n{session.summary}"
            messages.append({"role": "system", "content": summary_text})
            cached_tokens += estimate_tokens(summary_text)

        used_tokens = cached_tokens
        selected: list[ChatMessage] = []
        budget = max(1200, self.config.context_limit - 2000)
        transcript = session.messages
        if upto_message_id is not None:
            cutoff = session.message_index(upto_message_id)
            transcript = session.messages[: cutoff + 1]
        selected_payloads: list[dict[str, Any]] = []
        groups = _group_llm_messages(transcript)
        selected_groups: list[list[ChatMessage]] = []
        for group in reversed(groups):
            group_tokens = sum(_message_token_cost(message) for message in group)
            if used_tokens + group_tokens > budget and selected_groups:
                break
            selected_groups.append(group)
            used_tokens += group_tokens

        selected_groups.reverse()
        for group in selected_groups:
            for message in group:
                payload = message.to_llm_message()
                if payload is None:
                    continue
                selected.append(message)
                selected_payloads.append(payload)

        messages.extend(selected_payloads)
        usage = ContextUsage(
            used_tokens=used_tokens,
            limit_tokens=self.config.context_limit,
            cached_tokens=cached_tokens,
        )
        session.meta["context"] = usage.to_dict()
        return messages, usage
