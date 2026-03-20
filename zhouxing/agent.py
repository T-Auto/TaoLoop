from __future__ import annotations

from typing import Any, Awaitable, Callable
import asyncio
import json

from .config import Config
from .context import ContextManager
from .fallbacks import maybe_build_scientific_script_fallback
from .llm import build_client
from .logging_utils import FileLogger
from .sessions import ChatMessage, SessionRecord
from .tools import ToolRegistry


EmitCallback = Callable[[dict[str, Any]], Awaitable[None]]


class ConversationAgent:
    def __init__(self, config: Config, emit: EmitCallback, logger: FileLogger | None = None):
        self.config = config
        self.emit = emit
        self.logger = logger
        self.context_manager = ContextManager(config)
        self.client = build_client(config, logger=logger)
        self.tools = ToolRegistry(config, emit=self.emit, logger=logger)

    async def run_turn(self, session: SessionRecord, reply_to_message_id: str) -> dict[str, Any]:
        if self.logger:
            self.logger.log(
                "agent_turn_start",
                session_id=session.id,
                reply_to_message_id=reply_to_message_id,
                message_count=len(session.messages),
            )
        self.context_manager.compact(session)
        usage_info: dict[str, Any] = {}
        anchor_id = reply_to_message_id

        for step in range(self.config.max_tool_rounds):
            prompt_messages, usage = self.context_manager.build(
                session,
                upto_message_id=anchor_id,
            )
            usage_info = usage.to_dict()
            if self.logger:
                self.logger.log(
                    "agent_step",
                    session_id=session.id,
                    step=step + 1,
                    used_tokens=usage.used_tokens,
                    cached_tokens=usage.cached_tokens,
                    prompt_message_count=len(prompt_messages),
                    anchor_id=anchor_id,
                )
            try:
                response = await self._complete_with_progress(
                    prompt_messages,
                    self.tools.definitions(),
                    usage_info,
                    step + 1,
                )
            except Exception as exc:
                if self.logger:
                    self.logger.exception(
                        "agent_model_failure",
                        exc,
                        session_id=session.id,
                        step=step + 1,
                        reply_to_message_id=reply_to_message_id,
                    )
                if await self._recover_from_model_failure(
                    session,
                    reply_to_message_id,
                    anchor_id,
                    exc,
                ):
                    return usage_info
                raise
            if self.logger:
                self.logger.log(
                    "agent_model_response",
                    session_id=session.id,
                    step=step + 1,
                    content_preview=response.content[:400],
                    tool_call_names=[call.name for call in response.tool_calls],
                )
            if response.tool_calls:
                previous_anchor = anchor_id
                assistant_tool_call = ChatMessage.create(
                    "assistant",
                    response.content or "",
                    meta={
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                                },
                            }
                            for call in response.tool_calls
                        ]
                    },
                )
                session.insert_after(anchor_id, assistant_tool_call)
                anchor_id = assistant_tool_call.id
                if assistant_tool_call.content.strip():
                    await self.emit(
                        {
                            "type": "message",
                            "message": assistant_tool_call.to_public_dict(),
                            "after_message_id": previous_anchor,
                        }
                    )
                for call in response.tool_calls:
                    await self.emit(
                        {
                            "type": "tool_event",
                            "tool": call.name,
                            "phase": "call",
                            "arguments": call.arguments,
                            "step": step + 1,
                        }
                    )
                    try:
                        result = await self.tools.execute(call.name, call.arguments)
                    except Exception as exc:
                        result = f"Tool {call.name} failed: {exc}"
                    tool_message = ChatMessage.create(
                        "tool",
                        result,
                        name=call.name,
                        tool_call_id=call.id,
                    )
                    previous_anchor = anchor_id
                    session.insert_after(anchor_id, tool_message)
                    anchor_id = tool_message.id
                    await self.emit(
                        {
                            "type": "message",
                            "message": tool_message.to_public_dict(),
                            "after_message_id": previous_anchor,
                        }
                    )
                continue

            assistant_message = ChatMessage.create(
                "assistant",
                response.content.strip() or "(空响应)",
                meta={"model": response.model, "usage": response.usage},
            )
            previous_anchor = anchor_id
            session.insert_after(anchor_id, assistant_message)
            await self.emit(
                {
                    "type": "message",
                    "message": assistant_message.to_public_dict(),
                    "after_message_id": previous_anchor,
                }
            )
            if self.logger:
                self.logger.log(
                    "agent_turn_finish",
                    session_id=session.id,
                    assistant_message_id=assistant_message.id,
                    mode="normal",
                )
            return usage_info

        assistant_message = ChatMessage.create(
            "assistant",
            "已达到最大工具调用轮数，请把目标拆小后继续。",
        )
        previous_anchor = anchor_id
        session.insert_after(anchor_id, assistant_message)
        await self.emit(
            {
                "type": "message",
                "message": assistant_message.to_public_dict(),
                "after_message_id": previous_anchor,
            }
        )
        if self.logger:
            self.logger.log(
                "agent_turn_finish",
                session_id=session.id,
                assistant_message_id=assistant_message.id,
                mode="max_tool_rounds",
            )
        return usage_info

    async def _complete_with_progress(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        usage_info: dict[str, Any],
        step: int,
    ) -> Any:
        task = asyncio.create_task(self.client.complete(messages, tools))
        await self.emit(
            {
                "type": "progress",
                "phase": "thinking",
                "model": self.config.model,
                "offline_mode": self.config.offline_mode,
                "context": usage_info,
                "step": step,
            }
        )

        elapsed = 0
        while True:
            try:
                return await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except asyncio.TimeoutError:
                elapsed += 5
                await self.emit(
                    {
                        "type": "progress",
                        "phase": f"thinking {elapsed}s",
                        "model": self.config.model,
                        "offline_mode": self.config.offline_mode,
                        "context": usage_info,
                        "step": step,
                    }
                )

    async def _recover_from_model_failure(
        self,
        session: SessionRecord,
        reply_to_message_id: str,
        anchor_id: str,
        exc: Exception,
    ) -> bool:
        user_message = session.messages[session.message_index(reply_to_message_id)]
        fallback = maybe_build_scientific_script_fallback(user_message.content)
        if fallback is None:
            return False
        if self.logger:
            self.logger.log(
                "agent_fallback_start",
                session_id=session.id,
                reply_to_message_id=reply_to_message_id,
                anchor_id=anchor_id,
                fallback_path=fallback.path,
                smoke_test_command=fallback.smoke_test_command,
                original_error=str(exc),
            )

        notice = ChatMessage.create(
            "assistant",
            (
                "远端模型连接不稳定，我已切换到本地保底流程。"
                "我会直接为你生成一个可运行的科研计算脚本，并做一个短烟测。"
            ),
            meta={"fallback": True, "error": str(exc)},
        )
        session.insert_after(anchor_id, notice)
        await self.emit(
            {
                "type": "message",
                "message": notice.to_public_dict(),
                "after_message_id": anchor_id,
            }
        )
        anchor_id = notice.id

        write_result = await self.tools.execute(
            "write_file",
            {"path": fallback.path, "content": fallback.content},
        )
        write_message = ChatMessage.create(
            "event",
            f"本地保底写入完成\n{write_result}",
            meta={"fallback": True, "source_tool": "write_file"},
        )
        session.insert_after(anchor_id, write_message)
        await self.emit(
            {
                "type": "message",
                "message": write_message.to_public_dict(),
                "after_message_id": anchor_id,
            }
        )
        anchor_id = write_message.id

        smoke_result = await self.tools.execute(
            "run_command",
            {
                "command": fallback.smoke_test_command,
                "cwd": ".",
                "timeout_sec": 120,
            },
        )
        smoke_message = ChatMessage.create(
            "event",
            f"本地保底烟测完成\n{smoke_result}",
            meta={"fallback": True, "source_tool": "run_command"},
        )
        session.insert_after(anchor_id, smoke_message)
        await self.emit(
            {
                "type": "message",
                "message": smoke_message.to_public_dict(),
                "after_message_id": anchor_id,
            }
        )
        anchor_id = smoke_message.id

        summary = ChatMessage.create(
            "assistant",
            (
                f"已生成 `{fallback.path}`，默认运行时长约 {fallback.default_seconds} 秒。"
                f"我还执行了短烟测：`{fallback.smoke_test_command}`，脚本可以正常启动和运行。"
            ),
            meta={"fallback": True},
        )
        session.insert_after(anchor_id, summary)
        await self.emit(
            {
                "type": "message",
                "message": summary.to_public_dict(),
                "after_message_id": anchor_id,
            }
        )
        if self.logger:
            self.logger.log(
                "agent_fallback_finish",
                session_id=session.id,
                generated_path=fallback.path,
                smoke_test_command=fallback.smoke_test_command,
            )
        return True
