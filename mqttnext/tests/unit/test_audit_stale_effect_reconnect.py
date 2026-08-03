from __future__ import annotations

import asyncio

import pytest

from mqttnext.api.async_client import AsyncClient
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.enums import ConnectionState, PacketType
from mqttnext.packets import encode_frame
from mqttnext.protocol.engine import EffectKind


async def test_cancelled_pending_send_is_not_replayed_after_clean_reconnect() -> None:
    client = AsyncClient(
        client_id="audit-stale-effect",
        max_outbound_messages=1,
        max_outbound_bytes=1,
    )
    client._engine.state = ConnectionState.CONNECTED
    await client._enqueue_outbound(b"x")

    publishing = asyncio.create_task(client.publish("audit/stale", b"payload", qos=1))
    for _ in range(100):
        if client._outbound_waiters:
            break
        await asyncio.sleep(0)
    assert client._outbound_waiters == 1

    publishing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await publishing
    assert any(effect.kind is EffectKind.SEND for effect in client._pending_effects)

    client._engine.notify_transport_closed()
    client._engine.take_effects()
    client._engine.begin_connect()

    decoder = IncrementalDecoder()
    decoder.feed(encode_frame(PacketType.CONNACK, 0, b"\x00\x00"))
    raw = decoder.next_packet()
    assert raw is not None
    client._engine.handle_raw(raw)
    client._collect_effects_locked()

    kinds = [effect.kind for effect in client._pending_effects]
    assert EffectKind.PUBLISH_FAILED in kinds
    assert EffectKind.SEND not in kinds
