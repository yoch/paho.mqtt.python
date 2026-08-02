from __future__ import annotations

from pathlib import Path


CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
TEST = Path("mqttnext/tests/unit/test_nonreplayable_failures.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


text = CLIENT.read_text()
text = replace_once(
    text,
    """            if self._disconnect_exc is None:
                self._disconnect_exc = MQTTError("Connection closed")
            will_reconnect = self._will_reconnect()
""",
    """            if self._disconnect_exc is None:
                self._disconnect_exc = MQTTError("Connection closed")
            self._fail_non_replayable(self._disconnect_exc)
            will_reconnect = self._will_reconnect()
""",
    "reader non-replayable failure",
)
text = replace_once(
    text,
    """    def _fail_pending(self, exc: BaseException) -> None:
        for receipt in self._receipts.values():
            receipt._error = exc
            if receipt._event is not None:
                receipt._event.set()
        self._receipts.clear()
        for fut in self._sub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._sub_futs.clear()
        for fut in self._unsub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._unsub_futs.clear()
""",
    """    def _fail_non_replayable(self, exc: BaseException) -> None:
        for fut in self._sub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._sub_futs.clear()
        for fut in self._unsub_futs.values():
            if not fut.done():
                fut.set_exception(exc)
        self._unsub_futs.clear()

    def _fail_pending(self, exc: BaseException) -> None:
        for receipt in self._receipts.values():
            receipt._error = exc
            if receipt._event is not None:
                receipt._event.set()
        self._receipts.clear()
        self._fail_non_replayable(exc)
""",
    "pending failure split",
)
CLIENT.write_text(text)

TEST.write_text(
    '''"""Non-replayable requests fail immediately when a transport is lost."""

from __future__ import annotations

import asyncio

import pytest

from mqttnext.api.async_client import AsyncClient
from mqttnext.api.models import PublishReceipt
from mqttnext.enums import ConnectionState, QoS
from mqttnext.errors import MQTTError
from mqttnext.protocol.reconnect import ReconnectPolicy


class _ClosedTransport:
    def __init__(self) -> None:
        self.closed = False

    async def read(self, n: int = 65536) -> bytes:
        return b""

    async def write(self, data: bytes) -> None:
        return None

    async def close(self) -> None:
        self.closed = True

    def is_closing(self) -> bool:
        return self.closed


async def test_transport_loss_fails_subscriptions_but_preserves_publish_receipt() -> None:
    reconnect = ReconnectPolicy(
        enabled=True,
        initial_delay=60.0,
        max_delay=60.0,
        stable_after=60.0,
    )
    client = AsyncClient(client_id="nonreplayable", reconnect=reconnect)
    client._host = "fake"
    client._port = 1883
    client._engine.state = ConnectionState.CONNECTED
    client._transport = _ClosedTransport()

    loop = asyncio.get_running_loop()
    sub = loop.create_future()
    unsub = loop.create_future()
    client._sub_futs[11] = sub
    client._unsub_futs[12] = unsub

    publish_event = asyncio.Event()
    receipt = PublishReceipt(
        mid=13,
        qos=QoS.AT_LEAST_ONCE,
        _event=publish_event,
    )
    client._receipts[13] = receipt

    await client._read_loop()

    with pytest.raises(MQTTError, match="Connection closed"):
        await sub
    with pytest.raises(MQTTError, match="Connection closed"):
        await unsub
    assert client._sub_futs == {}
    assert client._unsub_futs == {}
    assert client._receipts[13] is receipt
    assert not publish_event.is_set()

    if client._reconnect_task is not None:
        client._reconnect_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await client._reconnect_task
        client._reconnect_task = None


def test_fail_pending_still_fails_all_operation_types() -> None:
    async def scenario() -> None:
        client = AsyncClient(client_id="fail-all")
        loop = asyncio.get_running_loop()
        sub = loop.create_future()
        unsub = loop.create_future()
        client._sub_futs[1] = sub
        client._unsub_futs[2] = unsub
        event = asyncio.Event()
        client._receipts[3] = PublishReceipt(
            mid=3,
            qos=QoS.AT_LEAST_ONCE,
            _event=event,
        )
        error = MQTTError("terminal")

        client._fail_pending(error)

        with pytest.raises(MQTTError, match="terminal"):
            await sub
        with pytest.raises(MQTTError, match="terminal"):
            await unsub
        assert event.is_set()
        assert client._receipts == {}

    asyncio.run(scenario())
'''
)
