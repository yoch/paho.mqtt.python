from __future__ import annotations

from pathlib import Path


ENGINE = Path("mqttnext/src/mqttnext/protocol/engine.py")
CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
AUTH_TEST = Path("mqttnext/tests/unit/test_auth.py")
TEST = Path("mqttnext/tests/unit/test_auth_contracts.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


engine = ENGINE.read_text()
engine = replace_once(
    engine,
    """        self._inbound_inflight = 0
        self._recovered_inbound_mids = {
""",
    """        self._inbound_inflight = 0
        self._auth_method: str | None = None
        self._recovered_inbound_mids = {
""",
    "auth method state",
)
engine = replace_once(
    engine,
    """    def begin_connect(self) -> bytes:
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            raise ProtocolError("Already connected or connecting")
        self.state = ConnectionState.CONNECTING
""",
    """    def begin_connect(self) -> bytes:
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            raise ProtocolError("Already connected or connecting")
        configured_auth_method = None
        if self.config.connect_properties is not None:
            configured_auth_method = self.config.connect_properties.get(
                "authentication_method"
            )
        if self.config.accept_auth:
            if self.config.protocol != MQTTProtocolVersion.MQTTv5:
                raise ProtocolError("Enhanced authentication requires MQTT 5")
            if not configured_auth_method:
                raise ProtocolError(
                    "auth_handler requires authentication_method in CONNECT properties"
                )
        self._auth_method = (
            str(configured_auth_method) if configured_auth_method is not None else None
        )
        self.state = ConnectionState.CONNECTING
""",
    "connect auth method validation",
)
engine = replace_once(
    engine,
    """        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        if connack.reason_code != 0:
""",
    """        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        if self.config.protocol == MQTTProtocolVersion.MQTTv5:
            connack_method = (
                connack.properties.get("authentication_method")
                if connack.properties is not None
                else None
            )
            if connack_method is not None and connack_method != self._auth_method:
                raise ProtocolError("CONNACK authentication_method does not match CONNECT")
            if (
                connack.properties is not None
                and connack.properties.get("authentication_data") is not None
                and self._auth_method is None
            ):
                raise ProtocolError(
                    "CONNACK authentication_data requires authentication_method"
                )
        if connack.reason_code != 0:
""",
    "connack auth validation",
)
engine = replace_once(
    engine,
    """        packet = AuthPacket.decode(raw.remaining, self.config.protocol)
        if not self.config.accept_auth:
""",
    """        packet = AuthPacket.decode(raw.remaining, self.config.protocol)
        if self._auth_method is None:
            self._reject_auth_method()
            return
        packet_method = (
            packet.properties.get("authentication_method")
            if packet.properties is not None
            else None
        )
        if packet_method is not None and packet_method != self._auth_method:
            self._reject_auth_method()
            return
        if packet.reason_code == 0x19 and self.state is ConnectionState.CONNECTING:
            raise ProtocolError("Re-authenticate AUTH is invalid before CONNACK")
        if not self.config.accept_auth:
""",
    "inbound auth validation",
)
engine = replace_once(
    engine,
    """        self._emit(EffectKind.AUTH, packet)

    def queue_auth(
""",
    """        self._emit(EffectKind.AUTH, packet)

    def _reject_auth_method(self) -> None:
        self._send(encode_disconnect(0x8C, self.config.protocol))
        self.state = ConnectionState.DISCONNECTED
        self._emit(
            EffectKind.DISCONNECTED,
            DisconnectInfo(reason_code=0x8C, from_broker=False),
        )

    def queue_auth(
""",
    "auth rejection helper",
)
engine = replace_once(
    engine,
    """        if self.state not in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            raise NotConnectedError("AUTH requires an active or pending connection")
        self._send(AuthPacket(reason_code=reason_code, properties=properties).encode())
""",
    """        if self.state not in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            raise NotConnectedError("AUTH requires an active or pending connection")
        if self._auth_method is None:
            raise ProtocolError("AUTH requires authentication_method in CONNECT")
        if reason_code == 0x19 and self.state is not ConnectionState.CONNECTED:
            raise ProtocolError("Re-authenticate AUTH requires a connected session")
        auth_properties = Properties(
            values=dict(properties.values) if properties is not None else {}
        )
        method = auth_properties.get("authentication_method")
        if method is not None and method != self._auth_method:
            raise ProtocolError("AUTH authentication_method does not match CONNECT")
        if method is None:
            auth_properties.set("authentication_method", self._auth_method)
        self._send(
            AuthPacket(
                reason_code=reason_code,
                properties=auth_properties,
            ).encode(self.config.protocol)
        )
""",
    "outbound auth validation",
)
ENGINE.write_text(engine)

client = CLIENT.read_text()
client = replace_once(
    client,
    """            if isinstance(response, AuthPacket):
                await self._enqueue_outbound(
                    response.encode(self._engine.config.protocol),
                    nowait=nowait,
                )
""",
    """            if isinstance(response, AuthPacket):
                async with self._engine_lock:
                    self._engine.queue_auth(
                        reason_code=response.reason_code,
                        properties=response.properties,
                    )
                    self._collect_effects_locked()
""",
    "handler response through engine",
)
CLIENT.write_text(client)

auth_test = AUTH_TEST.read_text()
auth_test = replace_once(
    auth_test,
    """    engine = ProtocolEngine(
        EngineConfig(client_id="c", protocol=MQTTProtocolVersion.MQTTv5, accept_auth=True)
    )
""",
    """    connect_props = Properties()
    connect_props.set("authentication_method", "demo")
    engine = ProtocolEngine(
        EngineConfig(
            client_id="c",
            protocol=MQTTProtocolVersion.MQTTv5,
            accept_auth=True,
            connect_properties=connect_props,
        )
    )
""",
    "existing engine auth test",
)
auth_test = replace_once(
    auth_test,
    """    client = AsyncClient(
        client_id="auth-c",
        protocol=MQTTProtocolVersion.MQTTv5,
        auth_handler=handler,
    )
""",
    """    connect_props = Properties()
    connect_props.set("authentication_method", "demo")
    client = AsyncClient(
        client_id="auth-c",
        protocol=MQTTProtocolVersion.MQTTv5,
        connect_properties=connect_props,
        auth_handler=handler,
    )
""",
    "existing async auth test",
)
AUTH_TEST.write_text(auth_test)

TEST.write_text(
    '''"""Enhanced authentication method and state contracts."""

from __future__ import annotations

import pytest

from mqttnext.codec.buffer import IncrementalDecoder, RawPacket
from mqttnext.enums import ConnectionState, MQTTProtocolVersion, PacketType
from mqttnext.errors import ProtocolError
from mqttnext.packets import AuthPacket
from mqttnext.protocol.engine import EffectKind, EngineConfig, ProtocolEngine
from mqttnext.types import Properties


def _props(method: str = "demo") -> Properties:
    properties = Properties()
    properties.set("authentication_method", method)
    return properties


def _raw_auth(reason: int, method: str | None = None) -> RawPacket:
    properties = _props(method) if method is not None else Properties()
    wire = AuthPacket(reason_code=reason, properties=properties).encode()
    decoder = IncrementalDecoder()
    decoder.feed(wire)
    packet = decoder.next_packet()
    assert packet is not None
    return packet


def test_auth_handler_requires_method_in_connect() -> None:
    engine = ProtocolEngine(
        EngineConfig(
            protocol=MQTTProtocolVersion.MQTTv5,
            accept_auth=True,
        )
    )
    with pytest.raises(ProtocolError, match="authentication_method"):
        engine.begin_connect()
    assert engine.state is ConnectionState.NEW


def test_inbound_auth_method_mismatch_disconnects_with_bad_method() -> None:
    engine = ProtocolEngine(
        EngineConfig(
            protocol=MQTTProtocolVersion.MQTTv5,
            accept_auth=True,
            connect_properties=_props("expected"),
        )
    )
    engine.begin_connect()
    engine.handle_raw(_raw_auth(0x18, "other"))
    effects = engine.take_effects()

    assert engine.state is ConnectionState.DISCONNECTED
    assert any(effect.kind is EffectKind.SEND for effect in effects)
    disconnected = next(
        effect.data for effect in effects if effect.kind is EffectKind.DISCONNECTED
    )
    assert disconnected.reason_code == 0x8C


def test_outbound_auth_injects_configured_method() -> None:
    engine = ProtocolEngine(
        EngineConfig(
            protocol=MQTTProtocolVersion.MQTTv5,
            accept_auth=True,
            connect_properties=_props("expected"),
        )
    )
    engine.begin_connect()
    engine.take_effects()

    engine.queue_auth(reason_code=0x18, properties=Properties())
    wire = next(
        effect.data
        for effect in engine.take_effects()
        if effect.kind is EffectKind.SEND
    )
    decoder = IncrementalDecoder()
    decoder.feed(wire)
    raw = decoder.next_packet()
    assert raw is not None and raw.packet_type is PacketType.AUTH
    packet = AuthPacket.decode(raw.remaining)
    assert packet.properties is not None
    assert packet.properties.get("authentication_method") == "expected"


def test_outbound_auth_rejects_method_change() -> None:
    engine = ProtocolEngine(
        EngineConfig(
            protocol=MQTTProtocolVersion.MQTTv5,
            accept_auth=True,
            connect_properties=_props("expected"),
        )
    )
    engine.begin_connect()
    with pytest.raises(ProtocolError, match="does not match"):
        engine.queue_auth(reason_code=0x18, properties=_props("other"))


def test_reauthenticate_requires_connected_state() -> None:
    engine = ProtocolEngine(
        EngineConfig(
            protocol=MQTTProtocolVersion.MQTTv5,
            accept_auth=True,
            connect_properties=_props(),
        )
    )
    engine.begin_connect()
    with pytest.raises(ProtocolError, match="connected session"):
        engine.queue_auth(reason_code=0x19)
'''
)
