"""Atomic effect transfer and callback task lifecycle."""

from __future__ import annotations

import asyncio

import pytest

from mqttnext.api.async_client import AsyncClient
from mqttnext.enums import ConnectionState
from mqttnext.protocol.engine import EffectKind
from mqttnext.types import Message


async def test_cancelled_backpressure_keeps_send_effect_for_retry() -> None:
    client = AsyncClient(
        client_id="effect-cancel",
        max_outbound_messages=1,
        max_outbound_bytes=1,
    )
    client._engine.state = ConnectionState.CONNECTED
    await client._enqueue_outbound(b"x")

    publishing = asyncio.create_task(client.publish("effect/t", b"payload", qos=0))
    for _ in range(100):
        if client._outbound_waiters:
            break
        await asyncio.sleep(0)
    assert client._outbound_waiters == 1

    publishing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await publishing
    assert any(
        effect.kind is EffectKind.SEND for effect in client._pending_effects
    )

    blocked = client._outbound.get_nowait()
    client._outbound.task_done()
    client._outbound_bytes -= len(blocked)
    async with client._outbound_space:
        client._outbound_space.notify_all()

    await client._drain_effects()
    assert not client._pending_effects
    assert client._outbound.qsize() == 1


async def test_callback_exception_is_collected() -> None:
    client = AsyncClient(client_id="callback-error")
    loop = asyncio.get_running_loop()
    contexts: list[dict[str, object]] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: contexts.append(context))

    def fail(_message: Message) -> None:
        raise RuntimeError("callback failed")

    try:
        client._spawn_callback(fail, Message(topic="t", payload=b"x"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not client._callback_tasks
        assert contexts == []
    finally:
        loop.set_exception_handler(previous)


async def test_force_close_cancels_callback_tasks() -> None:
    client = AsyncClient(client_id="callback-close")
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_message: Message) -> None:
        started.set()
        await release.wait()

    client._spawn_callback(slow, Message(topic="t", payload=b"x"))
    await started.wait()
    assert len(client._callback_tasks) == 1

    await client._force_close()
    assert not client._callback_tasks
