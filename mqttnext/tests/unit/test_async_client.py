"""AsyncClient integration tests over an in-memory transport.

Covers the planning-audit findings: receipt registration must precede wire
emission (no PUBACK race) and the single-writer pipeline must complete a full
connect/publish/subscribe/disconnect cycle.
"""

from __future__ import annotations

import asyncio

from mqttnext.api.async_client import AsyncClient
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.codec.primitives import pack_u16
from mqttnext.enums import PacketType, QoS
from mqttnext.packets import PubAckPacket, PublishPacket, encode_frame


class FakeBrokerTransport:
    """In-memory transport that acks CONNECT/PUBLISH/SUBSCRIBE instantly."""

    def __init__(self) -> None:
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._decoder = IncrementalDecoder()
        self._closing = False
        self.written: list[bytes] = []

    async def write(self, data: bytes) -> None:
        self.written.append(data)
        self._decoder.feed(data)
        for raw in self._decoder.drain_packets():
            if raw.packet_type is PacketType.CONNECT:
                self._rx.put_nowait(encode_frame(PacketType.CONNACK, 0, b"\x00\x00"))
            elif raw.packet_type is PacketType.PUBLISH:
                pub = PublishPacket.decode(raw.flags, raw.remaining)
                if pub.qos == QoS.AT_LEAST_ONCE:
                    assert pub.mid is not None
                    self._rx.put_nowait(PubAckPacket(mid=pub.mid).encode())
            elif raw.packet_type is PacketType.SUBSCRIBE:
                mid = int.from_bytes(raw.remaining[:2], "big")
                self._rx.put_nowait(
                    encode_frame(PacketType.SUBACK, 0, pack_u16(mid) + bytes([1]))
                )

    async def read(self, n: int = 65536) -> bytes:
        return await self._rx.get()

    async def close(self) -> None:
        self._closing = True
        self._rx.put_nowait(b"")

    def is_closing(self) -> bool:
        return self._closing


def _client_with_fake() -> tuple[AsyncClient, FakeBrokerTransport]:
    client = AsyncClient(client_id="test")
    fake = FakeBrokerTransport()

    async def factory(host: str, port: int, *, ssl: object = None) -> FakeBrokerTransport:
        return fake

    client._transport_factory = factory
    return client, fake


async def test_connect_publish_qos1_wait_disconnect() -> None:
    client, fake = _client_with_fake()
    connack = await client.connect("fake", 1883, timeout=2.0)
    assert connack.reason_code == 0
    assert client.is_connected

    receipt = await client.publish("t/1", b"hello", qos=1)
    # The fake broker acks synchronously on write: this only completes if the
    # receipt was registered before the packet hit the wire (audit finding B1).
    await asyncio.wait_for(receipt.wait(), timeout=2.0)
    assert receipt.is_done()

    mid = await client.subscribe("t/#", qos=1)
    assert mid > 0
    await client.disconnect()
    assert not client.is_connected


async def test_many_concurrent_publishes_complete() -> None:
    client, fake = _client_with_fake()
    await client.connect("fake", 1883, timeout=2.0)

    receipts = await asyncio.gather(
        *(client.publish(f"t/{i}", str(i), qos=1) for i in range(50))
    )
    await asyncio.wait_for(
        asyncio.gather(*(r.wait() for r in receipts)), timeout=5.0
    )
    assert all(r.is_done() for r in receipts)
    await client.disconnect()


async def test_qos0_receipt_immediate() -> None:
    client, fake = _client_with_fake()
    await client.connect("fake", 1883, timeout=2.0)
    receipt = await client.publish("t/0", b"fire-and-forget", qos=0)
    assert receipt.is_done()
    await asyncio.wait_for(receipt.wait(), timeout=1.0)
    await client.disconnect()
