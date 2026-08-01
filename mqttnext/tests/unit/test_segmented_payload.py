"""Segmented large-payload encode tests."""

from __future__ import annotations

from mqttnext.enums import QoS
from mqttnext.packets import PublishPacket
from mqttnext.transport.writes import SEGMENT_THRESHOLD


def test_large_payload_is_segmented() -> None:
    payload = b"x" * SEGMENT_THRESHOLD
    pkt = PublishPacket(
        topic="big",
        payload=payload,
        qos=QoS.AT_MOST_ONCE,
        retain=False,
        dup=False,
    )
    item = pkt.encode_write_item()
    assert isinstance(item, tuple)
    header, body = item
    assert body is payload or body == payload
    assert header + body == pkt.encode()


def test_small_payload_contiguous() -> None:
    pkt = PublishPacket(
        topic="small",
        payload=b"hi",
        qos=QoS.AT_MOST_ONCE,
        retain=False,
        dup=False,
    )
    assert isinstance(pkt.encode_write_item(), bytes)
