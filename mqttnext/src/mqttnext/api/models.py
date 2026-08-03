"""Public API models."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mqttnext.enums import QoS
from mqttnext.packets import ConnAckPacket, SubAckPacket, UnsubAckPacket
from mqttnext.types import Message


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
    "PublishReceipt",
    "SubscribeResult",
    "UnsubscribeResult",
]
