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
4. 当脚本长时间运行时，结合 run_command 返回的硬件心跳判断是否卡死、I/O 瓶颈、CPU/GPU 利用不足、内存风险。
5. 回复保持简洁直接，给出实际修改、发现的问题和下一步。
6. 对于“新建一个小型 Python 科研脚本”这类直接任务，最多做一次必要环境检查，然后直接写文件；不要反复查看示例文件。
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
        head = session.messages[:-keep_tail]
        tail = session.messages[-keep_tail:]
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
        for message in reversed(transcript):
            payload = message.to_llm_message()
            if payload is None:
                continue
            message_tokens = estimate_tokens(message.content) + 24
            if used_tokens + message_tokens > budget and selected:
                break
            selected.append(message)
            selected_payloads.append(payload)
            used_tokens += message_tokens
        selected.reverse()
        selected_payloads.reverse()

        messages.extend(selected_payloads)
        usage = ContextUsage(
            used_tokens=used_tokens,
            limit_tokens=self.config.context_limit,
            cached_tokens=cached_tokens,
        )
        session.meta["context"] = usage.to_dict()
        return messages, usage
