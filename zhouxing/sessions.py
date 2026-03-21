from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import uuid


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _assistant_tool_call_ids(message: "ChatMessage") -> set[str]:
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


def _sanitize_message(message: "ChatMessage", reason: str) -> None:
    original_role = message.role
    message.role = "event"
    if original_role == "tool":
        message.tool_call_id = None
    message.meta = {
        **message.meta,
        "sanitized_from_role": original_role,
        "sanitized_reason": reason,
    }


@dataclass(slots=True)
class ChatMessage:
    id: str
    role: str
    content: str
    created_at: str
    name: str | None = None
    tool_call_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        role: str,
        content: str,
        *,
        name: str | None = None,
        tool_call_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "ChatMessage":
        return cls(
            id=_new_id("msg"),
            role=role,
            content=content,
            created_at=now_iso(),
            name=name,
            tool_call_id=tool_call_id,
            meta=meta or {},
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChatMessage":
        return cls(
            id=payload["id"],
            role=payload["role"],
            content=payload.get("content", ""),
            created_at=payload["created_at"],
            name=payload.get("name"),
            tool_call_id=payload.get("tool_call_id"),
            meta=payload.get("meta", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_public_dict(self) -> dict[str, Any]:
        return self.to_dict()

    def to_llm_message(self) -> dict[str, Any] | None:
        if self.role not in {"system", "user", "assistant", "tool"}:
            return None
        if self.role == "tool" and not self.tool_call_id:
            return None
        message: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            message["name"] = self.name
        if self.tool_call_id:
            message["tool_call_id"] = self.tool_call_id
        if self.role == "assistant" and self.meta.get("tool_calls"):
            message["tool_calls"] = self.meta["tool_calls"]
        return message


@dataclass(slots=True)
class SessionRecord:
    id: str
    title: str
    created_at: str
    updated_at: str
    summary: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, title: str | None = None) -> "SessionRecord":
        timestamp = now_iso()
        return cls(
            id=_new_id("session"),
            title=title or f"新会话 {timestamp[11:16]}",
            created_at=timestamp,
            updated_at=timestamp,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionRecord":
        return cls(
            id=payload["id"],
            title=payload["title"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            summary=payload.get("summary", ""),
            messages=[ChatMessage.from_dict(item) for item in payload.get("messages", [])],
            meta=payload.get("meta", {}),
        )

    def append(self, message: ChatMessage) -> None:
        self.messages.append(message)
        self.updated_at = now_iso()

    def message_index(self, message_id: str) -> int:
        for index, message in enumerate(self.messages):
            if message.id == message_id:
                return index
        raise KeyError(message_id)

    def insert_after(self, anchor_message_id: str, message: ChatMessage) -> None:
        index = self.message_index(anchor_message_id)
        self.messages.insert(index + 1, message)
        self.updated_at = now_iso()

    def sanitize(self) -> int:
        repaired = 0
        valid_tool_indexes: set[int] = set()

        index = 0
        while index < len(self.messages):
            message = self.messages[index]
            tool_call_ids = _assistant_tool_call_ids(message)
            if not tool_call_ids:
                index += 1
                continue

            matched_tool_ids: set[str] = set()
            matched_tool_indexes: list[int] = []
            probe = index + 1
            while probe < len(self.messages):
                next_message = self.messages[probe]
                if (
                    next_message.role == "tool"
                    and next_message.tool_call_id in tool_call_ids
                    and next_message.tool_call_id not in matched_tool_ids
                ):
                    matched_tool_ids.add(next_message.tool_call_id)
                    matched_tool_indexes.append(probe)
                    probe += 1
                    continue
                if next_message.to_llm_message() is None:
                    probe += 1
                    continue
                break

            if matched_tool_ids == tool_call_ids:
                valid_tool_indexes.update(matched_tool_indexes)
            else:
                _sanitize_message(message, "incomplete_tool_call_block")
                repaired += 1
                for tool_index in matched_tool_indexes:
                    tool_message = self.messages[tool_index]
                    if tool_message.role != "tool":
                        continue
                    _sanitize_message(tool_message, "incomplete_tool_call_block")
                    repaired += 1
            index = probe

        for index, message in enumerate(self.messages):
            if message.role != "tool":
                continue
            if not message.tool_call_id:
                _sanitize_message(message, "missing_tool_call_id")
                repaired += 1
                continue
            if index not in valid_tool_indexes:
                _sanitize_message(message, "orphan_tool_message")
                repaired += 1
        return repaired

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "messages": [message.to_dict() for message in self.messages],
            "meta": self.meta,
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "messages": [message.to_public_dict() for message in self.messages],
            "meta": self.meta,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
            "summary": self.summary[:240],
            "meta": self.meta,
        }


class SessionStore:
    def __init__(self, sessions_dir: Path, logger: Any | None = None):
        self.sessions_dir = sessions_dir
        self.logger = logger
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def save(self, session: SessionRecord) -> None:
        repaired = session.sanitize()
        if repaired and self.logger:
            self.logger.log(
                "session_sanitized",
                session_id=session.id,
                repaired_messages=repaired,
                path=str(self._path_for(session.id)),
                trigger="save",
            )
        path = self._path_for(session.id)
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create(self, title: str | None = None) -> SessionRecord:
        session = SessionRecord.create(title)
        self.save(session)
        return session

    def delete(self, session_id: str) -> bool:
        path = self._path_for(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def load(self, session_id: str) -> SessionRecord:
        path = self._path_for(session_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Session file is corrupted: {path}") from exc
        session = SessionRecord.from_dict(payload)
        repaired = session.sanitize()
        if repaired:
            if self.logger:
                self.logger.log(
                    "session_sanitized",
                    session_id=session.id,
                    repaired_messages=repaired,
                    path=str(path),
                    trigger="load",
                )
            self.save(session)
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for path in self.sessions_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            snapshots.append(SessionRecord.from_dict(payload).snapshot())
        snapshots.sort(key=lambda item: item["updated_at"], reverse=True)
        return snapshots
