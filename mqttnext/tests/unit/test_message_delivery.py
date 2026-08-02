"""Message delivery modes and explicit reconnect stream reset."""

from __future__ import annotations

import asyncio

import pytest

from mqttnext.api.async_client import AsyncClient, _MESSAGE_SENTINEL
from mqttnext.protocol.engine import EffectKind, EngineEffect
from mqttnext.types import Message


async def _deliver(client: AsyncClient, payload: bytes = b"x") -> None:
    await client._apply_effect(
        EngineEffect(
            kind=EffectKind.MESSAGE,
            data=Message(topic="delivery/test", payload=payload),
        ),
        nowait=False,
    )


async def test_auto_callback_does_not_fill_iterator_queue() -> None:
    client = AsyncClient(
        client_id="delivery-auto",
        max_pending_messages=1,
        message_delivery="auto",
    )
    received: list[bytes] = []
    client.on_message = lambda message: received.append(message.payload)

    for index in range(5):
        await _deliver(client, str(index).encode())
    await asyncio.sleep(0)

    assert received == [b"0", b"1", b"2", b"3", b"4"]
    assert client._messages.empty()


async def test_iterator_mode_ignores_callback() -> None:
    client = AsyncClient(client_id="delivery-iterator", message_delivery="iterator")
    received: list[bytes] = []
    client.on_message = lambda message: received.append(message.payload)

    await _deliver(client)
    assert received == []
    message = client._messages.get_nowait()
    assert isinstance(message, Message)
    assert message.payload == b"x"


async def test_both_mode_delivers_to_callback_and_iterator() -> None:
    client = AsyncClient(client_id="delivery-both", message_delivery="both")
    received: list[bytes] = []
    client.on_message = lambda message: received.append(message.payload)

    await _deliver(client)
    await asyncio.sleep(0)
    assert received == [b"x"]
    message = client._messages.get_nowait()
    assert isinstance(message, Message)
    assert message.payload == b"x"


async def test_explicit_reconnect_resets_closed_message_stream() -> None:
    client = AsyncClient(client_id="delivery-reset", max_pending_messages=2)
    original = client._messages
    original.put_nowait(_MESSAGE_SENTINEL)
    client._closed.set()

    client._reset_message_stream()

    assert client._messages is not original
    assert client._messages.maxsize == 2
    assert client._messages.empty()
    assert not client._closed.is_set()


def test_invalid_message_delivery_rejected() -> None:
    with pytest.raises(ValueError, match="message_delivery"):
        AsyncClient(message_delivery="invalid")  # type: ignore[arg-type]
