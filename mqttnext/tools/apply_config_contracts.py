from __future__ import annotations

from pathlib import Path


ENGINE = Path("mqttnext/src/mqttnext/protocol/engine.py")
CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
RECONNECT = Path("mqttnext/src/mqttnext/protocol/reconnect.py")
TEST = Path("mqttnext/tests/unit/test_config_contracts.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


engine = ENGINE.read_text()
engine = replace_once(
    engine,
    """    accept_auth: bool = False


class ProtocolEngine:
""",
    """    accept_auth: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.keepalive <= 65535:
            raise ValueError("keepalive must be between 0 and 65535")
        if not 1 <= self.local_receive_maximum <= 65535:
            raise ValueError("local_receive_maximum must be between 1 and 65535")
        if self.max_outbound_inflight is not None and not (
            1 <= self.max_outbound_inflight <= 65535
        ):
            raise ValueError("max_outbound_inflight must be between 1 and 65535")
        if self.max_queued < 0:
            raise ValueError("max_queued must be non-negative")
        if self.maximum_packet_size is not None and not (
            2 <= self.maximum_packet_size <= 268_435_460
        ):
            raise ValueError("maximum_packet_size must be between 2 and 268435460")
        if not 0 <= self.topic_alias_maximum <= 65535:
            raise ValueError("topic_alias_maximum must be between 0 and 65535")


class ProtocolEngine:
""",
    "engine config validation",
)
engine = replace_once(
    engine,
    """        self._pending_connect = True
        self._topic_aliases.clear()
        self._inbound_inflight = 0
""",
    """        self._pending_connect = True
        self._topic_aliases.clear()
        # Negotiated capabilities are connection-scoped. Queued messages are
        # validated against the new values only after the next CONNACK.
        self.negotiated = NegotiatedSettings()
        self._inbound_inflight = 0
""",
    "negotiated reset",
)
ENGINE.write_text(engine)

client = CLIENT.read_text()
client = replace_once(
    client,
    """        if max_pending_messages <= 0:
            raise ValueError("max_pending_messages must be greater than 0")
        self._message_delivery = message_delivery
        self._max_pending_messages = max_pending_messages
        pwd = password.encode("utf-8") if isinstance(password, str) else password
""",
    """        if max_pending_messages <= 0:
            raise ValueError("max_pending_messages must be greater than 0")
        if max_outbound_messages <= 0:
            raise ValueError("max_outbound_messages must be greater than 0")
        if max_outbound_bytes <= 0:
            raise ValueError("max_outbound_bytes must be greater than 0")
        if ack_timeout <= 0:
            raise ValueError("ack_timeout must be greater than 0")
        if ping_timeout is not None and ping_timeout <= 0:
            raise ValueError("ping_timeout must be greater than 0")
        if not isinstance(client_id, str):
            raise ValueError("client_id must be a string")
        if username is not None and not isinstance(username, str):
            raise ValueError("username must be a string or None")
        if password is not None and not isinstance(password, (bytes, str)):
            raise ValueError("password must be bytes, str, or None")
        self._message_delivery = message_delivery
        self._max_pending_messages = max_pending_messages
        effective_max_packet_size = (
            maximum_packet_size
            if maximum_packet_size is not None
            else DEFAULT_MAX_PACKET_SIZE
        )
        pwd = password.encode("utf-8") if isinstance(password, str) else password
""",
    "async client validation",
)
client = replace_once(
    client,
    """                maximum_packet_size=maximum_packet_size,
""",
    """                maximum_packet_size=effective_max_packet_size,
""",
    "effective max engine config",
)
client = replace_once(
    client,
    """        max_pkt = maximum_packet_size or DEFAULT_MAX_PACKET_SIZE
        self._decoder = IncrementalDecoder(max_packet_size=max_pkt)
""",
    """        self._decoder = IncrementalDecoder(
            max_packet_size=effective_max_packet_size
        )
""",
    "effective max decoder",
)
CLIENT.write_text(client)

reconnect = RECONNECT.read_text()
reconnect = replace_once(
    reconnect,
    """    def __post_init__(self) -> None:
        self._attempt = 0
        self._current_delay = self.initial_delay
""",
    """    def __post_init__(self) -> None:
        if self.initial_delay < 0:
            raise ValueError("initial_delay must be non-negative")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least 1")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be greater than or equal to initial_delay")
        if self.max_retries is not None and self.max_retries < 0:
            raise ValueError("max_retries must be non-negative or None")
        if self.stable_after < 0:
            raise ValueError("stable_after must be non-negative")
        if self.connect_timeout <= 0:
            raise ValueError("connect_timeout must be greater than 0")
        self._attempt = 0
        self._current_delay = self.initial_delay
""",
    "reconnect validation",
)
RECONNECT.write_text(reconnect)

TEST.write_text(
    '''"""Constructor configuration contracts and connection-scoped negotiation."""

from __future__ import annotations

import pytest

from mqttnext.api.async_client import AsyncClient
from mqttnext.codec.buffer import DEFAULT_MAX_PACKET_SIZE, IncrementalDecoder
from mqttnext.codec.properties import CONNECT
from mqttnext.codec.vbi import decode_vbi
from mqttnext.enums import MQTTProtocolVersion
from mqttnext.packets import ConnectPacket
from mqttnext.protocol.engine import EngineConfig, ProtocolEngine
from mqttnext.protocol.reconnect import ReconnectPolicy
from mqttnext.types import Properties


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("keepalive", -1),
        ("keepalive", 65536),
        ("local_receive_maximum", 0),
        ("local_receive_maximum", 65536),
        ("max_outbound_inflight", 0),
        ("max_queued", -1),
        ("maximum_packet_size", 1),
        ("topic_alias_maximum", -1),
        ("topic_alias_maximum", 65536),
    ],
)
def test_engine_config_rejects_invalid_ranges(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        EngineConfig(**{field: value})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_outbound_messages": 0},
        {"max_outbound_bytes": 0},
        {"max_pending_messages": 0},
        {"ack_timeout": 0},
        {"ping_timeout": 0},
        {"client_id": b"bad"},
        {"username": b"bad"},
        {"password": object()},
    ],
)
def test_async_client_rejects_invalid_configuration(kwargs) -> None:
    with pytest.raises(ValueError):
        AsyncClient(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"initial_delay": -1},
        {"multiplier": 0.5},
        {"initial_delay": 2, "max_delay": 1},
        {"max_retries": -1},
        {"stable_after": -1},
        {"connect_timeout": 0},
    ],
)
def test_reconnect_policy_rejects_invalid_configuration(kwargs) -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(**kwargs)


def test_default_local_packet_limit_is_announced_in_mqtt5_connect() -> None:
    client = AsyncClient(protocol=MQTTProtocolVersion.MQTTv5)
    assert client._decoder.max_packet_size == DEFAULT_MAX_PACKET_SIZE
    assert client._engine.config.maximum_packet_size == DEFAULT_MAX_PACKET_SIZE

    wire = client._engine.begin_connect()
    remaining_length, pos = decode_vbi(wire, 1)
    body = wire[pos : pos + remaining_length]
    # Decode enough of CONNECT to inspect the properties through the packet
    # generated by the engine: the value must be present on the wire.
    assert DEFAULT_MAX_PACKET_SIZE.to_bytes(4, "big") in body


def test_negotiated_capabilities_reset_before_new_connection() -> None:
    engine = ProtocolEngine()
    engine.negotiated.maximum_qos = 0
    engine.negotiated.retain_available = False
    engine.negotiated.maximum_packet_size = 128

    engine.begin_connect()

    assert engine.negotiated.maximum_qos == 2
    assert engine.negotiated.retain_available is True
    assert engine.negotiated.maximum_packet_size is None
'''
)
