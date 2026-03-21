from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

from zhouxing.agent import ConversationAgent
from zhouxing.background_jobs import BackgroundJobManager
from zhouxing.backend import BackendServer
from zhouxing.config import Config
from zhouxing.context import ContextManager, SYSTEM_PROMPT, _adjust_compaction_start
from zhouxing.llm import MockClient, ModelResponse, ToolCall
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
    def test_system_prompt_requires_project_uv_environment(self) -> None:
        self.assertIn("项目根目录的 `uv` 和 `.venv`", SYSTEM_PROMPT)
        self.assertIn("不要回退到系统 Python 或裸 `pip`", SYSTEM_PROMPT)
        self.assertIn("cwd=sandbox:.", SYSTEM_PROMPT)

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

    def test_build_command_env_unsets_virtual_env_for_uv_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = Config.load(root)
            config.backend_python.parent.mkdir(parents=True, exist_ok=True)
            registry = ToolRegistry(config)

            env = registry._build_command_env("uv run python --version", cwd=config.root_dir)

        self.assertNotIn("VIRTUAL_ENV", env)
        self.assertTrue(env["PATH"].startswith(str(config.backend_python.parent)))

    def test_infer_run_timeout_for_python_help_script(self) -> None:
        self.assertEqual(
            ToolRegistry._infer_run_timeout_sec("uv run python sandbox/physics_simulation.py --help", 0),
            15,
        )
        self.assertEqual(
            ToolRegistry._infer_run_timeout_sec("uv run python sandbox/physics_simulation.py --help", 3),
            3,
        )
        self.assertEqual(
            ToolRegistry._infer_run_timeout_sec("uv run python -c \"print('ok')\"", 0),
            0,
        )

    def test_normalize_background_timeout_ignores_tiny_python_timeouts(self) -> None:
        self.assertEqual(
            ToolRegistry._normalize_background_timeout_sec("uv run python sandbox/physics_simulation.py", 10),
            0,
        )
        self.assertEqual(
            ToolRegistry._normalize_background_timeout_sec("uv run python sandbox/physics_simulation.py", 120),
            120,
        )
        self.assertEqual(
            ToolRegistry._normalize_background_timeout_sec("uv run echo hello", 10),
            10,
        )

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

    def test_message_buffer_coalesces_background_heartbeats(self) -> None:
        delivered: list[str] = []

        async def run() -> None:
            queue = MessageBufferQueue()
            await queue.put_event(
                "session_1",
                ChatMessage.create("event", "heartbeat-1"),
                meta={"coalesce_key": "background-heartbeat:job_1"},
            )
            await queue.put_event(
                "session_1",
                ChatMessage.create("event", "heartbeat-2"),
                meta={"coalesce_key": "background-heartbeat:job_1"},
            )

            async def deliver(item) -> None:
                delivered.append(item.message.content)

            await queue.flush(deliver)

        asyncio.run(run())

        self.assertEqual(delivered, ["heartbeat-2"])

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

    def test_agent_enters_standby_after_background_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config.load(Path(tmpdir))
            config.autonomous_run_limit_sec = 3600
            emitted: list[dict] = []
            session = SessionRecord.create("agent-standby")
            user_message = ChatMessage.create("user", "启动一个长任务")
            session.append(user_message)
            agent = ConversationAgent(
                config,
                emit=capture_emit(emitted),
                tools=StubTools(
                    {
                        "start_background_command": "job_id=job_1\nstarted_in_background=true",
                    }
                ),
            )
            agent.client = SequenceClient(
                [
                    ModelResponse(
                        content="",
                        tool_calls=[
                            ToolCall(
                                id="call_background",
                                name="start_background_command",
                                arguments={"command": "python long_job.py"},
                            )
                        ],
                        model="test-model",
                        usage={},
                    ),
                    ModelResponse(
                        content="这条不应该出现",
                        tool_calls=[],
                        model="test-model",
                        usage={},
                    ),
                ]
            )

            usage = asyncio.run(agent.run_turn(session, user_message.id))

        self.assertEqual(agent.client.calls, 1)
        self.assertEqual(agent.tools.calls, ["start_background_command"])
        self.assertEqual(session.meta["runtime_state"]["phase"], "sleeping")
        self.assertEqual(session.meta["runtime_state"]["reason"], "background_job_started")
        self.assertEqual(session.messages[-1].role, "tool")
        self.assertEqual(session.messages[-1].name, "start_background_command")
        self.assertIsInstance(usage, dict)
        self.assertTrue(any(payload.get("type") == "message" for payload in emitted))

    def test_agent_pauses_when_autonomous_window_elapses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config.load(Path(tmpdir))
            config.autonomous_run_limit_sec = 1
            emitted: list[dict] = []
            session = SessionRecord.create("agent-window")
            user_message = ChatMessage.create("user", "读取一个文件")
            session.append(user_message)
            agent = ConversationAgent(
                config,
                emit=capture_emit(emitted),
                tools=StubTools(
                    {"read_file": "File sandbox/test.txt lines 1-1:\n   1: ok"},
                    delays={"read_file": 1.1},
                ),
            )
            agent.client = SequenceClient(
                [
                    ModelResponse(
                        content="",
                        tool_calls=[
                            ToolCall(
                                id="call_read",
                                name="read_file",
                                arguments={"path": "test.txt"},
                            )
                        ],
                        model="test-model",
                        usage={},
                    ),
                    ModelResponse(
                        content="这条也不应该出现",
                        tool_calls=[],
                        model="test-model",
                        usage={},
                    ),
                ]
            )

            asyncio.run(agent.run_turn(session, user_message.id))

        self.assertEqual(agent.client.calls, 1)
        self.assertEqual(agent.tools.calls, ["read_file"])
        self.assertEqual(session.meta["runtime_state"]["phase"], "sleeping")
        self.assertEqual(session.meta["runtime_state"]["reason"], "autonomous_window_elapsed")
        self.assertEqual(session.messages[-1].role, "assistant")
        self.assertIn("已达到本轮自主运行时间上限", session.messages[-1].content)
        self.assertTrue(any(payload.get("type") == "progress" for payload in emitted))

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


class BackendRegressionTests(unittest.TestCase):
    def test_should_schedule_background_followup_only_for_sleeping_finish_event(self) -> None:
        backend = BackendServer.__new__(BackendServer)
        backend.active_session = SessionRecord.create("backend-followup")
        session = backend.active_session
        session.meta["runtime_state"] = {
            "phase": "sleeping",
            "reason": "background_job_started",
        }
        finish_message = ChatMessage.create(
            "event",
            "后台脚本运行结束",
            meta={
                "background_job_phase": "finish",
                "background_job_id": "job_1",
                "background_job_status": "failed",
            },
        )
        heartbeat_message = ChatMessage.create(
            "event",
            "后台脚本心跳",
            meta={
                "background_job_phase": "heartbeat",
                "background_job_id": "job_1",
                "background_job_status": "running",
            },
        )

        self.assertTrue(backend._should_schedule_background_followup(session, finish_message))
        self.assertFalse(backend._should_schedule_background_followup(session, heartbeat_message))

        session.meta["runtime_state"] = {"phase": "idle"}
        self.assertFalse(backend._should_schedule_background_followup(session, finish_message))


def capture_emit(sink: list[dict]):
    async def emit(payload: dict) -> None:
        sink.append(payload)

    return emit


class SequenceClient:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls = 0

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        del messages, tools
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


class StubTools:
    def __init__(self, results: dict[str, str], delays: dict[str, float] | None = None) -> None:
        self.results = results
        self.delays = delays or {}
        self.calls: list[str] = []

    def definitions(self) -> list[dict]:
        return []

    async def execute(self, name: str, arguments: dict, *, event_cursor=None) -> str:
        del arguments, event_cursor
        self.calls.append(name)
        delay = self.delays.get(name, 0.0)
        if delay > 0:
            await asyncio.sleep(delay)
        return self.results[name]


if __name__ == "__main__":
    unittest.main()
