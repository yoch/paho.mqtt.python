"""Public API models."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from mqttnext.enums import QoS
from mqttnext.errors import PublishBatchError
from mqttnext.packets import ConnAckPacket, SubAckPacket, UnsubAckPacket
from mqttnext.types import Message, Properties


@dataclass(slots=True, frozen=True)
class PublishMessage:
    """One immutable entry accepted by :meth:`AsyncClient.publish_many`."""

    topic: str
    payload: bytes | str = b""
    qos: QoS | int = QoS.AT_MOST_ONCE
    retain: bool = False
    properties: Properties | None = None


class PublishBatchReceipt:
    """Aggregate completion handle without one task/event per publication."""

    __slots__ = (
        "_mids",
        "_pending",
        "_failures",
        "_done",
        "_progress",
        "_sealed",
        "_submitted",
        "_completed",
        "_fatal",
    )

    def __init__(self) -> None:
        self._mids: list[int | None] = []
        self._pending: set[int] = set()
        self._failures: dict[int, BaseException] = {}
        self._done = asyncio.Event()
        self._progress = asyncio.Event()
        self._sealed = False
        self._submitted = 0
        self._completed = 0
        self._fatal: BaseException | None = None

    @property
    def mids(self) -> tuple[int | None, ...]:
        return tuple(self._mids)

    @property
    def submitted(self) -> int:
        return self._submitted

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def failures(self) -> Mapping[int, BaseException]:
        return MappingProxyType(self._failures)

    def is_done(self) -> bool:
        return self._done.is_set()

    async def wait(self) -> None:
        await self._done.wait()
        if self._fatal is not None:
            raise PublishBatchError(
                self._failures,
                cause=self._fatal,
                receipt=self,
            ) from self._fatal
        if self._failures:
            raise PublishBatchError(self._failures, receipt=self)

    def _register(self, mid: int | None) -> None:
        self._mids.append(mid)
        self._submitted += 1
        if mid is None:
            self._completed += 1
        else:
            self._pending.add(mid)

    def _complete(self, mid: int, error: BaseException | None = None) -> None:
        if mid not in self._pending:
            return
        self._pending.remove(mid)
        self._completed += 1
        if error is not None:
            self._failures[mid] = error
        self._progress.set()
        self._finish_if_ready()

    def _seal(self) -> None:
        self._sealed = True
        self._finish_if_ready()

    def _fail_remaining(self, error: BaseException) -> None:
        self._fatal = error
        for mid in self._pending:
            self._failures.setdefault(mid, error)
        self._completed += len(self._pending)
        self._pending.clear()
        self._sealed = True
        self._progress.set()
        self._done.set()

    async def _wait_pending_at_most(self, limit: int) -> None:
        while len(self._pending) > limit:
            self._progress.clear()
            if len(self._pending) <= limit:
                break
            await self._progress.wait()

    def _finish_if_ready(self) -> None:
        if self._sealed and not self._pending:
            self._done.set()


@dataclass(slots=True)
class PublishReceipt:
    """Handle returned by ``AsyncClient.publish``."""

    mid: int | None
    qos: QoS
    _event: asyncio.Event | None = None
    _error: BaseException | None = None

    async def wait(self) -> None:
        if self.qos == QoS.AT_MOST_ONCE or self._event is None:
            if self._error is not None:
                raise self._error
            return
        await self._event.wait()
        if self._error is not None:
            raise self._error

    def is_done(self) -> bool:
        return self.qos == QoS.AT_MOST_ONCE or self._event is None or self._event.is_set()


@dataclass(slots=True)
class SubscribeResult:
    mid: int
    reason_codes: tuple[int, ...]

    @classmethod
    def from_packet(cls, packet: SubAckPacket) -> SubscribeResult:
        return cls(mid=packet.mid, reason_codes=packet.reason_codes)


@dataclass(slots=True)
class UnsubscribeResult:
    mid: int
    reason_codes: tuple[int, ...]

    @classmethod
    def from_packet(cls, packet: UnsubAckPacket) -> UnsubscribeResult:
        return cls(mid=packet.mid, reason_codes=packet.reason_codes)


__all__ = [
    "ConnAckPacket",
    "Message",
    "PublishBatchReceipt",
    "PublishMessage",
    "PublishReceipt",
    "SubscribeResult",
    "UnsubscribeResult",
]
