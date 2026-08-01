"""Smoke tests for the Paho VERSION2 compat façade."""

from __future__ import annotations

import asyncio

from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.codec.primitives import pack_u16
from mqttnext.compat.paho import CallbackAPIVersion, Client
from mqttnext.enums import PacketType, QoS
from mqttnext.packets import PubAckPacket, PublishPacket, encode_frame


class FakeBrokerTransport:
    def __init__(self) -> None:
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._decoder = IncrementalDecoder()
        self._closing = False

    async def write(self, data: bytes) -> None:
        self._decoder.feed(data)
        for raw in self._decoder.drain_packets():
            if raw.packet_type is PacketType.CONNECT:
                self._rx.put_nowait(encode_frame(PacketType.CONNACK, 0, b"\x00\x00"))
            elif raw.packet_type is PacketType.PUBLISH:
                pub = PublishPacket.decode(raw.flags, raw.remaining)
                if pub.qos == QoS.AT_LEAST_ONCE and pub.mid is not None:
                    self._rx.put_nowait(PubAckPacket(mid=pub.mid).encode())
            elif raw.packet_type is PacketType.SUBSCRIBE:
                mid = int.from_bytes(raw.remaining[:2], "big")
                self._rx.put_nowait(
                    encode_frame(PacketType.SUBACK, 0, pack_u16(mid) + bytes([0]))
                )

    async def read(self, n: int = 65536) -> bytes:
        return await self._rx.get()

    async def close(self) -> None:
        self._closing = True
        self._rx.put_nowait(b"")

    def is_closing(self) -> bool:
        return self._closing


def test_compat_connect_publish_qos1() -> None:
    client = Client(CallbackAPIVersion.VERSION2, client_id="compat")
    fake = FakeBrokerTransport()

    async def factory(host: str, port: int, *, ssl: object = None) -> FakeBrokerTransport:
        return fake

    client._async._transport_factory = factory
    connected = []

    def on_connect(c, userdata, flags, reason_code, properties):
        connected.append(reason_code)

    client.on_connect = on_connect
    client.loop_start()
    try:
        assert client.connect("fake", 1883) == 0
        assert connected == [0]
        info = client.publish("t/1", b"hi", qos=1)
        assert info.wait_for_publish(timeout=2.0)
        assert info.is_published()
        rc, mid = client.subscribe("t/#")
        assert rc == 0 and mid > 0
        assert client.disconnect() == 0
    finally:
        client.loop_stop()
