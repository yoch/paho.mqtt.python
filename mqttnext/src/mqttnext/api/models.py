"""Public API models."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mqttnext.enums import QoS
from mqttnext.packets import ConnAckPacket
from mqttnext.types import Message


@dataclass(slots=True)
class PublishReceipt:
    """Handle returned by ``AsyncClient.publish``."""

    mid: int | None
    qos: QoS
    _event: asyncio.Event
    _error: BaseException | None = None

    async def wait(self) -> None:
        if self.qos == QoS.AT_MOST_ONCE:
            return
        await self._event.wait()
        if self._error is not None:
            raise self._error

    def is_done(self) -> bool:
        return self.qos == QoS.AT_MOST_ONCE or self._event.is_set()


__all__ = ["ConnAckPacket", "Message", "PublishReceipt"]
