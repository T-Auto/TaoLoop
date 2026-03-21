from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from zhouxing.config import Config
from zhouxing.context import ContextManager, _adjust_compaction_start
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


if __name__ == "__main__":
    unittest.main()
