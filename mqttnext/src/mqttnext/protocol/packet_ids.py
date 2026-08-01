"""Outbound MQTT packet identifier allocator.

Receive Maximum MUST NOT shrink this space — it is enforced by FlowControl.
Inbound QoS 2 identifiers live in a separate namespace and must never be freed here.
"""

from __future__ import annotations

from mqttnext.errors import FlowControlError


class PacketIdPool:
    __slots__ = ("_used", "_last", "_size")

    def __init__(self) -> None:
        # MQTT packet identifiers are 1..65535 inclusive.
        self._used: set[int] = set()
        self._last = 0
        self._size = 65535

    def __len__(self) -> int:
        return len(self._used)

    @property
    def available(self) -> int:
        return self._size - len(self._used)

    def allocate(self) -> int:
        if len(self._used) >= self._size:
            raise FlowControlError("No free MQTT packet identifiers")
        candidate = self._last
        for _ in range(self._size):
            candidate += 1
            if candidate > self._size:
                candidate = 1
            if candidate not in self._used:
                self._used.add(candidate)
                self._last = candidate
                return candidate
        raise FlowControlError("No free MQTT packet identifiers")

    def release(self, mid: int) -> None:
        self._used.discard(mid)

    def in_use(self, mid: int) -> bool:
        return mid in self._used

    def clear(self) -> None:
        self._used.clear()
        self._last = 0
