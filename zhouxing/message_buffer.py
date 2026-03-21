from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import asyncio

from .sessions import ChatMessage


DeliverCallback = Callable[["BufferedSessionMessage"], Awaitable[None]]


@dataclass(slots=True)
class BufferedSessionMessage:
    session_id: str
    message: ChatMessage
    priority: int
    sequence: int
    after_message_id: str = ""
    meta: dict[str, Any] | None = None

    @property
    def is_user(self) -> bool:
        return self.priority == 0


@dataclass(slots=True)
class FlushResult:
    delivered: int = 0
    delivered_user: int = 0
    delivered_event: int = 0


class MessageBufferQueue:
    USER_PRIORITY = 0
    EVENT_PRIORITY = 1

    def __init__(self, logger: Any | None = None) -> None:
        self.logger = logger
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._items: list[BufferedSessionMessage] = []

    async def put_user(
        self,
        session_id: str,
        message: ChatMessage,
        *,
        after_message_id: str = "",
        meta: dict[str, Any] | None = None,
    ) -> BufferedSessionMessage:
        return await self._put(
            session_id,
            message,
            priority=self.USER_PRIORITY,
            after_message_id=after_message_id,
            meta=meta,
        )

    async def put_event(
        self,
        session_id: str,
        message: ChatMessage,
        *,
        after_message_id: str = "",
        meta: dict[str, Any] | None = None,
    ) -> BufferedSessionMessage:
        return await self._put(
            session_id,
            message,
            priority=self.EVENT_PRIORITY,
            after_message_id=after_message_id,
            meta=meta,
        )

    async def _put(
        self,
        session_id: str,
        message: ChatMessage,
        *,
        priority: int,
        after_message_id: str,
        meta: dict[str, Any] | None,
    ) -> BufferedSessionMessage:
        async with self._lock:
            self._sequence += 1
            item = BufferedSessionMessage(
                session_id=session_id,
                message=message,
                priority=priority,
                sequence=self._sequence,
                after_message_id=after_message_id,
                meta=meta,
            )
            self._items.append(item)
            if self.logger:
                self.logger.log(
                    "message_buffer_enqueue",
                    session_id=session_id,
                    message_id=message.id,
                    role=message.role,
                    priority=priority,
                    after_message_id=after_message_id,
                )
            return item

    async def flush(
        self,
        deliver: DeliverCallback,
        *,
        session_id: str | None = None,
        only_user: bool = False,
        max_items: int = 0,
    ) -> FlushResult:
        async with self._lock:
            selected: list[BufferedSessionMessage] = []
            remaining: list[BufferedSessionMessage] = []
            for item in self._sorted_items():
                if session_id is not None and item.session_id != session_id:
                    remaining.append(item)
                    continue
                if only_user and not item.is_user:
                    remaining.append(item)
                    continue
                if max_items > 0 and len(selected) >= max_items:
                    remaining.append(item)
                    continue
                selected.append(item)
            self._items = remaining

        result = FlushResult()
        for item in selected:
            await deliver(item)
            result.delivered += 1
            if item.is_user:
                result.delivered_user += 1
            else:
                result.delivered_event += 1
        return result

    async def has_user_messages(self, session_id: str | None = None) -> bool:
        async with self._lock:
            for item in self._items:
                if not item.is_user:
                    continue
                if session_id is None or item.session_id == session_id:
                    return True
        return False

    async def size(self, *, session_id: str | None = None) -> int:
        async with self._lock:
            if session_id is None:
                return len(self._items)
            return sum(1 for item in self._items if item.session_id == session_id)

    def _sorted_items(self) -> list[BufferedSessionMessage]:
        return sorted(self._items, key=lambda item: (item.priority, item.sequence))
