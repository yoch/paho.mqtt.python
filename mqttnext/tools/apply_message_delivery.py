from __future__ import annotations

from pathlib import Path


CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
HELPER = Path("mqttnext/src/mqttnext/helpers/subscribe.py")
TEST = Path("mqttnext/tests/unit/test_message_delivery.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


text = CLIENT.read_text()
text = replace_once(
    text,
    "from typing import Any, Never\n",
    "from typing import Any, Literal, Never\n",
    "Literal import",
)
text = replace_once(
    text,
    "OnAuth = Callable[[AuthPacket], Any]\n\n_MESSAGE_SENTINEL = object()\n",
    "OnAuth = Callable[[AuthPacket], Any]\nMessageDelivery = Literal[\"auto\", \"iterator\", \"callback\", \"both\"]\n\n_MESSAGE_SENTINEL = object()\n",
    "message delivery alias",
)
text = replace_once(
    text,
    """        max_outbound_messages: int = 10_000,
        max_pending_messages: int = 65_536,
        manual_ack: bool = False,
""",
    """        max_outbound_messages: int = 10_000,
        max_pending_messages: int = 65_536,
        message_delivery: MessageDelivery = "auto",
        manual_ack: bool = False,
""",
    "message delivery parameter",
)
text = replace_once(
    text,
    """    ) -> None:
        pwd = password.encode("utf-8") if isinstance(password, str) else password
        self._engine = ProtocolEngine(
""",
    """    ) -> None:
        if message_delivery not in ("auto", "iterator", "callback", "both"):
            raise ValueError(
                "message_delivery must be 'auto', 'iterator', 'callback', or 'both'"
            )
        if max_pending_messages <= 0:
            raise ValueError("max_pending_messages must be greater than 0")
        self._message_delivery = message_delivery
        self._max_pending_messages = max_pending_messages
        pwd = password.encode("utf-8") if isinstance(password, str) else password
        self._engine = ProtocolEngine(
""",
    "delivery validation",
)
text = replace_once(
    text,
    """        self._messages: asyncio.Queue[Message | object] = asyncio.Queue(
            maxsize=max_pending_messages
        )
""",
    """        self._messages: asyncio.Queue[Message | object] = asyncio.Queue(
            maxsize=self._max_pending_messages
        )
""",
    "message queue capacity",
)

for marker, label in (
    ("        async with self._lifecycle_lock:\n            self._host = host\n", "TCP reset"),
    ("        async with self._lifecycle_lock:\n            self._unix_path = path\n", "Unix reset"),
    ("        async with self._lifecycle_lock:\n            self._ws_url = url\n", "WebSocket reset"),
):
    replacement = marker.replace(
        "        async with self._lifecycle_lock:\n",
        "        async with self._lifecycle_lock:\n            self._reset_message_stream()\n",
        1,
    )
    text = replace_once(text, marker, replacement, label)

text = replace_once(
    text,
    """        elif kind is EffectKind.MESSAGE:
            msg: Message = effect.data
            await self._messages.put(msg)
            if self.on_message is not None:
                self._spawn_callback(self.on_message, msg)
""",
    """        elif kind is EffectKind.MESSAGE:
            msg: Message = effect.data
            callback_delivery = self.on_message is not None and self._message_delivery in (
                "auto",
                "callback",
                "both",
            )
            iterator_delivery = self._message_delivery in ("iterator", "both") or (
                self._message_delivery == "auto" and self.on_message is None
            )
            if iterator_delivery:
                await self._messages.put(msg)
            if callback_delivery:
                assert self.on_message is not None
                self._spawn_callback(self.on_message, msg)
""",
    "message effect delivery",
)
text = replace_once(
    text,
    """    def _spawn_callback(self, callback: Callable[..., Any], *args: Any) -> None:
""",
    """    def _reset_message_stream(self) -> None:
        if self._closed.is_set():
            self._messages = asyncio.Queue(maxsize=self._max_pending_messages)
            self._closed.clear()

    def _spawn_callback(self, callback: Callable[..., Any], *args: Any) -> None:
""",
    "message stream reset helper",
)
CLIENT.write_text(text)

helper = HELPER.read_text()
needle = """        username=username,
        password=password,
    )
"""
replacement = """        username=username,
        password=password,
        message_delivery="callback",
    )
"""
count = helper.count(needle)
if count != 2:
    raise RuntimeError(f"helper callback construction: expected two matches, found {count}")
HELPER.write_text(helper.replace(needle, replacement))

TEST.write_text(
    '''"""Message delivery modes and explicit reconnect stream reset."""

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
'''
)
