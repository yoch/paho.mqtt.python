"""In-memory inflight persistence (ordered, injectable interface)."""

from __future__ import annotations

from typing import Iterator, Protocol

from mqttnext.types import InboundMessage, OutboundMessage


class InflightStore(Protocol):
    def put_out(self, msg: OutboundMessage) -> None: ...
    def get_out(self, mid: int) -> OutboundMessage | None: ...
    def pop_out(self, mid: int) -> OutboundMessage | None: ...
    def update_out(self, msg: OutboundMessage) -> None: ...
    def out_items(self) -> Iterator[OutboundMessage]: ...
    def clear_out(self) -> None: ...

    def put_in(self, msg: InboundMessage) -> None: ...
    def get_in(self, mid: int) -> InboundMessage | None: ...
    def pop_in(self, mid: int) -> InboundMessage | None: ...
    def update_in(self, msg: InboundMessage) -> None: ...
    def clear_in(self) -> None: ...


class MemoryInflightStore:
    """Ordered dict-backed store. Insertion order is the retransmission order."""

    __slots__ = ("_out", "_in")

    def __init__(self) -> None:
        self._out: dict[int, OutboundMessage] = {}
        self._in: dict[int, InboundMessage] = {}

    def put_out(self, msg: OutboundMessage) -> None:
        self._out[msg.mid] = msg

    def get_out(self, mid: int) -> OutboundMessage | None:
        return self._out.get(mid)

    def pop_out(self, mid: int) -> OutboundMessage | None:
        return self._out.pop(mid, None)

    def update_out(self, msg: OutboundMessage) -> None:
        if msg.mid not in self._out:
            raise KeyError(msg.mid)
        self._out[msg.mid] = msg

    def out_items(self) -> Iterator[OutboundMessage]:
        return iter(self._out.values())

    def clear_out(self) -> None:
        self._out.clear()

    def put_in(self, msg: InboundMessage) -> None:
        self._in[msg.mid] = msg

    def get_in(self, mid: int) -> InboundMessage | None:
        return self._in.get(mid)

    def pop_in(self, mid: int) -> InboundMessage | None:
        return self._in.pop(mid, None)

    def update_in(self, msg: InboundMessage) -> None:
        if msg.mid not in self._in:
            raise KeyError(msg.mid)
        self._in[msg.mid] = msg

    def clear_in(self) -> None:
        self._in.clear()
