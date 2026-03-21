from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

from zhouxing.background_jobs import BackgroundJobManager
from zhouxing.config import Config
from zhouxing.context import ContextManager, _adjust_compaction_start
from zhouxing.llm import MockClient
from zhouxing.message_buffer import MessageBufferQueue
from zhouxing.sessions import ChatMessage, SessionRecord, now_iso
from zhouxing.tools import ToolRegistry


def make_message(
    message_id: str,
    role: str,
    content: str,
    *,
    name: str | None = None,
    tool_call_id: str | None = None,
    meta: dict | None = None,
) -> ChatMessage:
    return ChatMessage(
        id=message_id,
        role=role,
        content=content,
        created_at=now_iso(),
        name=name,
        tool_call_id=tool_call_id,
        meta=meta or {},
    )


class ContextRegressionTests(unittest.TestCase):
    def test_adjust_compaction_start_rewinds_to_assistant_tool_call(self) -> None:
        messages = [
            make_message(
                "msg_assistant",
                "assistant",
                "",
                meta={
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search_text", "arguments": "{}"},
                        }
                    ]
                },
            ),
            make_message("msg_tool", "tool", "x" * 32, name="search_text", tool_call_id="call_1"),
        ]

        self.assertEqual(_adjust_compaction_start(messages, 1), 0)

    def test_build_drops_tool_result_when_whole_tool_block_does_not_fit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config.load(Path(tmpdir))
            config.context_limit = 3200
            manager = ContextManager(config)
            session = SessionRecord.create("context-regression")
            session.messages = [
                make_message("msg_user_1", "user", "earlier question"),
                make_message(
                    "msg_assistant_tool",
                    "assistant",
                    "",
                    meta={
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search_text", "arguments": "{}"},
                            }
                        ]
                    },
                ),
                make_message("msg_tool", "tool", "x" * 4600, name="search_text", tool_call_id="call_1"),
                make_message("msg_user_2", "user", "follow-up"),
            ]

            payloads, _usage = manager.build(session)

        roles = [payload["role"] for payload in payloads]
        self.assertEqual(roles, ["system", "user"])
        self.assertEqual(payloads[1]["content"], "follow-up")


class SessionRegressionTests(unittest.TestCase):
    def test_sanitize_demotes_orphan_and_incomplete_tool_messages(self) -> None:
        session = SessionRecord.create("sanitize-regression")
        session.messages = [
            make_message(
                "msg_assistant_tool",
                "assistant",
                "",
                meta={
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search_text", "arguments": "{}"},
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": "{}"},
                        }
                    ]
                },
            ),
            make_message("msg_tool_partial", "tool", "partial result", name="search_text", tool_call_id="call_1"),
            make_message("msg_user", "user", "next question"),
            make_message("msg_tool_orphan", "tool", "orphan result", name="search_text", tool_call_id="call_3"),
        ]

        repaired = session.sanitize()

        self.assertEqual(repaired, 3)
        self.assertEqual(session.messages[0].role, "event")
        self.assertEqual(session.messages[0].meta["sanitized_reason"], "incomplete_tool_call_block")
        self.assertEqual(session.messages[1].role, "event")
        self.assertEqual(session.messages[1].meta["sanitized_reason"], "incomplete_tool_call_block")
        self.assertEqual(session.messages[3].role, "event")
        self.assertEqual(session.messages[3].meta["sanitized_reason"], "orphan_tool_message")


class ToolRegressionTests(unittest.TestCase):
    def test_search_text_skips_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = Config.load(root)
            (root / "notes.txt").write_text("comment should match\n", encoding="utf-8")
            (root / "zhouxing.exe").write_bytes(b"comment should not match\x00\x01")
            registry = ToolRegistry(config)

            result = asyncio.run(
                registry._search_text(
                    pattern="comment",
                    path="project:.",
                    ignore_case=True,
                    max_hits=10,
                )
            )

        self.assertIn("notes.txt:1: comment should match", result)
        self.assertNotIn("zhouxing.exe", result)

    def test_message_buffer_prioritizes_user_messages(self) -> None:
        delivered: list[str] = []

        async def run() -> None:
            queue = MessageBufferQueue()
            await queue.put_event("session_1", ChatMessage.create("event", "heartbeat"))
            await queue.put_user("session_1", ChatMessage.create("user", "latest question"))

            async def deliver(item) -> None:
                delivered.append(item.message.role + ":" + item.message.content)

            await queue.flush(deliver)

        asyncio.run(run())

        self.assertEqual(
            delivered,
            ["user:latest question", "event:heartbeat"],
        )

    def test_background_job_manager_emits_finish_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = Config.load(root)
            captured_messages: list[tuple[str, ChatMessage]] = []
            emitted_job_snapshots: list[list[dict]] = []

            async def enqueue_message(session_id: str, message: ChatMessage) -> None:
                captured_messages.append((session_id, message))

            async def emit_jobs_changed(jobs: list[dict]) -> None:
                emitted_job_snapshots.append(jobs)

            manager = BackgroundJobManager(
                config,
                enqueue_message=enqueue_message,
                emit_jobs_changed=emit_jobs_changed,
            )

            async def run() -> None:
                job = await manager.start_process(
                    session_id="session_async",
                    session_title="async-test",
                    command="unit-test-background",
                    cwd=config.sandbox_dir,
                    env=os.environ.copy(),
                    popen_command=[
                        sys.executable,
                        "-c",
                        (
                            "import time; "
                            "print('tick', flush=True); "
                            "time.sleep(0.4); "
                            "print('done', flush=True)"
                        ),
                    ],
                    use_shell=False,
                    encoding="utf-8",
                    timeout_sec=0,
                )
                running = await manager.list_jobs(include_finished=False, max_jobs=10)
                self.assertEqual(len(running), 1)
                self.assertEqual(running[0]["id"], job.id)
                assert job.task is not None
                await job.task

            asyncio.run(run())

        self.assertTrue(emitted_job_snapshots)
        self.assertTrue(captured_messages)
        session_id, finish_message = captured_messages[-1]
        self.assertEqual(session_id, "session_async")
        self.assertEqual(finish_message.meta["background_job_phase"], "finish")
        self.assertIn("后台脚本运行结束", finish_message.content)
        self.assertIn("recent_logs:", finish_message.content)
        self.assertIn("done", finish_message.content)

    def test_mock_client_plans_async_test_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config.load(Path(tmpdir))
            client = MockClient(config)

            response = asyncio.run(
                client.complete(
                    [{"role": "user", "content": "目前你的CLI在测试阶段，请写一个运行40秒的python程序并运行，这个python程序本身会每隔10秒输出一次日志，模拟仿真物理实验，来验证你的tools工具是否正常"}],
                    [],
                )
            )

        self.assertEqual([call.name for call in response.tool_calls], ["write_file", "start_background_command"])


if __name__ == "__main__":
    unittest.main()
