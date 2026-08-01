"""Synchronous MQTT protocol engine.

No asyncio, no sockets, no user callbacks. Feed packets / commands in, collect
effects out. This is the correctness core that AsyncClient adapts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from mqttnext.codec.buffer import RawPacket
from mqttnext.enums import (
    ConnectionState,
    InboundQoSState,
    MQTTProtocolVersion,
    OutboundQoSState,
    PacketType,
    QoS,
)
from mqttnext.errors import FlowControlError, NotConnectedError, ProtocolError
from mqttnext.packets import (
    ConnAckPacket,
    ConnectPacket,
    PubAckPacket,
    PubCompPacket,
    PublishPacket,
    PubRecPacket,
    PubRelPacket,
    SubAckPacket,
    SubscribePacket,
    UnsubAckPacket,
    UnsubscribePacket,
    encode_disconnect,
    encode_pingreq,
    encode_pingresp,
)
from mqttnext.persistence.memory import InflightStore, MemoryInflightStore
from mqttnext.protocol.flow_control import FlowControl
from mqttnext.protocol.packet_ids import PacketIdPool
from mqttnext.types import InboundMessage, Message, OutboundMessage, Properties


class EffectKind(Enum):
    SEND = auto()
    MESSAGE = auto()
    CONNACK = auto()
    PUBLISH_COMPLETE = auto()
    SUBACK = auto()
    UNSUBACK = auto()
    DISCONNECTED = auto()
    PROTOCOL_ERROR = auto()


@dataclass(slots=True)
class EngineEffect:
    kind: EffectKind
    data: Any = None


@dataclass(slots=True)
class PublishHandle:
    mid: int | None
    qos: QoS


@dataclass
class EngineConfig:
    client_id: str = ""
    protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311
    clean_start: bool = True
    keepalive: int = 60
    username: str | None = None
    password: bytes | None = None
    local_receive_maximum: int = 65535
    max_queued: int = 0  # 0 = unlimited queued (not yet inflight)


class ProtocolEngine:
    """Pure MQTT session/QoS state machine."""

    def __init__(
        self,
        config: EngineConfig | None = None,
        store: InflightStore | None = None,
    ) -> None:
        self.config = config or EngineConfig()
        self.store = store or MemoryInflightStore()
        self.packet_ids = PacketIdPool()
        self.flow = FlowControl(self.config.local_receive_maximum)
        self.state = ConnectionState.NEW
        self.session_present = False
        self._pending_connect = False
        self._effects: list[EngineEffect] = []
        # Queued outbound publishes waiting for inflight slots.
        self._queued: list[OutboundMessage] = []

    # ------------------------------------------------------------------ #
    # Effect channel
    # ------------------------------------------------------------------ #
    def take_effects(self) -> list[EngineEffect]:
        effects = self._effects
        self._effects = []
        return effects

    def _emit(self, kind: EffectKind, data: Any = None) -> None:
        self._effects.append(EngineEffect(kind=kind, data=data))

    def _send(self, packet: bytes) -> None:
        self._emit(EffectKind.SEND, packet)

    # ------------------------------------------------------------------ #
    # Commands (from API layer)
    # ------------------------------------------------------------------ #
    def begin_connect(self) -> bytes:
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            raise ProtocolError("Already connected or connecting")
        self.state = ConnectionState.CONNECTING
        self._pending_connect = True
        packet = ConnectPacket(
            client_id=self.config.client_id,
            clean_start=self.config.clean_start,
            keepalive=self.config.keepalive,
            username=self.config.username,
            password=self.config.password,
            protocol=self.config.protocol,
        )
        return packet.encode()

    def queue_publish(
        self,
        topic: str,
        payload: bytes = b"",
        *,
        qos: QoS | int = QoS.AT_MOST_ONCE,
        retain: bool = False,
        properties: Properties | None = None,
    ) -> PublishHandle:
        qos = QoS(qos)
        if self.state != ConnectionState.CONNECTED and qos == QoS.AT_MOST_ONCE:
            # Allow offline queue for durable QoS later; QoS0 requires live link.
            raise NotConnectedError("Cannot publish QoS 0 while disconnected")

        if qos == QoS.AT_MOST_ONCE:
            packet = PublishPacket(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain,
                dup=False,
                mid=None,
                properties=properties,
            )
            wire = packet.encode(self.config.protocol)
            self._send(wire)
            return PublishHandle(mid=None, qos=qos)

        mid = self.packet_ids.allocate()
        msg = OutboundMessage(
            mid=mid,
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
            state=OutboundQoSState.QUEUED,
            properties=properties,
        )
        packet = PublishPacket(
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
            dup=False,
            mid=mid,
            properties=properties,
        )
        msg.encoded_publish = packet.encode(self.config.protocol)
        if qos == QoS.EXACTLY_ONCE:
            msg.encoded_pubrel = PubRelPacket(mid=mid).encode(self.config.protocol)

        if self.state == ConnectionState.CONNECTED and self.flow.try_acquire():
            self._launch_outbound(msg)
        else:
            if self.config.max_queued and len(self._queued) >= self.config.max_queued:
                self.packet_ids.release(mid)
                raise FlowControlError("Outbound queue full")
            self._queued.append(msg)
            self.store.put_out(msg)
        return PublishHandle(mid=mid, qos=qos)

    def queue_subscribe(self, topic: str, qos: QoS | int = QoS.AT_MOST_ONCE) -> int:
        if self.state != ConnectionState.CONNECTED:
            raise NotConnectedError("subscribe requires an active connection")
        mid = self.packet_ids.allocate()
        packet = SubscribePacket(mid=mid, topic=topic, qos=QoS(qos))
        self._send(packet.encode(self.config.protocol))
        return mid

    def queue_unsubscribe(self, topic: str) -> int:
        if self.state != ConnectionState.CONNECTED:
            raise NotConnectedError("unsubscribe requires an active connection")
        mid = self.packet_ids.allocate()
        packet = UnsubscribePacket(mid=mid, topic=topic)
        self._send(packet.encode(self.config.protocol))
        return mid

    def queue_ping(self) -> None:
        self._send(encode_pingreq())

    def begin_disconnect(self, reason_code: int = 0) -> bytes:
        self.state = ConnectionState.DISCONNECTING
        return encode_disconnect(reason_code, self.config.protocol)

    def notify_transport_closed(self) -> None:
        was = self.state
        self.state = ConnectionState.DISCONNECTED
        if was != ConnectionState.DISCONNECTED:
            self._emit(EffectKind.DISCONNECTED)

    # ------------------------------------------------------------------ #
    # Incoming packets
    # ------------------------------------------------------------------ #
    def handle_raw(self, raw: RawPacket) -> None:
        handlers = {
            PacketType.CONNACK: self._on_connack,
            PacketType.PUBLISH: self._on_publish,
            PacketType.PUBACK: self._on_puback,
            PacketType.PUBREC: self._on_pubrec,
            PacketType.PUBREL: self._on_pubrel,
            PacketType.PUBCOMP: self._on_pubcomp,
            PacketType.SUBACK: self._on_suback,
            PacketType.UNSUBACK: self._on_unsuback,
            PacketType.PINGRESP: self._on_pingresp,
            PacketType.PINGREQ: self._on_pingreq,
            PacketType.DISCONNECT: self._on_disconnect,
        }
        handler = handlers.get(raw.packet_type)
        if handler is None:
            self._emit(EffectKind.PROTOCOL_ERROR, f"Unhandled packet {raw.packet_type!r}")
            return
        handler(raw)

    def _on_connack(self, raw: RawPacket) -> None:
        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        self._pending_connect = False
        if connack.reason_code != 0:
            self.state = ConnectionState.DISCONNECTED
            self._emit(EffectKind.CONNACK, connack)
            self._emit(EffectKind.DISCONNECTED)
            return

        self.state = ConnectionState.CONNECTED
        self.session_present = connack.session_present
        if not connack.session_present:
            # Fresh session: drop previous inflight and release IDs.
            for msg in list(self.store.out_items()):
                self.packet_ids.release(msg.mid)
            self.store.clear_out()
            self.store.clear_in()
            self._queued.clear()
            self.packet_ids.clear()
            self.flow.reset()
        else:
            self._replay_session()

        self._emit(EffectKind.CONNACK, connack)
        self._drain_queue()

    def _on_publish(self, raw: RawPacket) -> None:
        packet = PublishPacket.decode(raw.flags, raw.remaining, self.config.protocol)
        if packet.qos == QoS.AT_MOST_ONCE:
            self._emit(
                EffectKind.MESSAGE,
                Message(
                    topic=packet.topic,
                    payload=packet.payload,
                    qos=packet.qos,
                    retain=packet.retain,
                    dup=packet.dup,
                    mid=None,
                    properties=packet.properties,
                ),
            )
            return

        assert packet.mid is not None
        if packet.qos == QoS.AT_LEAST_ONCE:
            self._emit(
                EffectKind.MESSAGE,
                Message(
                    topic=packet.topic,
                    payload=packet.payload,
                    qos=packet.qos,
                    retain=packet.retain,
                    dup=packet.dup,
                    mid=packet.mid,
                    properties=packet.properties,
                ),
            )
            self._send(PubAckPacket(mid=packet.mid).encode(self.config.protocol))
            return

        # QoS 2 inbound
        existing = self.store.get_in(packet.mid)
        if existing is not None:
            # Duplicate PUBLISH: do not redeliver; retransmit PUBREC.
            self._send(PubRecPacket(mid=packet.mid).encode(self.config.protocol))
            return

        inbound = InboundMessage(
            mid=packet.mid,
            topic=packet.topic,
            payload=packet.payload,
            qos=packet.qos,
            retain=packet.retain,
            state=InboundQoSState.WAIT_PUBREL,
            delivered=True,
            properties=packet.properties,
        )
        self.store.put_in(inbound)
        self._emit(
            EffectKind.MESSAGE,
            Message(
                topic=packet.topic,
                payload=packet.payload,
                qos=packet.qos,
                retain=packet.retain,
                dup=packet.dup,
                mid=packet.mid,
                properties=packet.properties,
            ),
        )
        self._send(PubRecPacket(mid=packet.mid).encode(self.config.protocol))

    def _on_puback(self, raw: RawPacket) -> None:
        ack = PubAckPacket.decode(raw.remaining, self.config.protocol)
        msg = self.store.pop_out(ack.mid)
        if msg is None:
            return
        self.packet_ids.release(ack.mid)
        self.flow.release()
        self._emit(EffectKind.PUBLISH_COMPLETE, ack.mid)
        self._drain_queue()

    def _on_pubrec(self, raw: RawPacket) -> None:
        rec = PubRecPacket.decode(raw.remaining, self.config.protocol)
        msg = self.store.get_out(rec.mid)
        if msg is None:
            # Orphan PUBREC: still reply with PUBREL per common practice / MQTT recovery.
            self._send(PubRelPacket(mid=rec.mid).encode(self.config.protocol))
            return
        if rec.reason_code >= 128:
            self.store.pop_out(rec.mid)
            self.packet_ids.release(rec.mid)
            self.flow.release()
            self._emit(EffectKind.PUBLISH_COMPLETE, rec.mid)
            self._drain_queue()
            return
        # Critical fix vs gmqtt: keep MID + persist PUBREL until PUBCOMP.
        msg.state = OutboundQoSState.WAIT_PUBCOMP
        if msg.encoded_pubrel is None:
            msg.encoded_pubrel = PubRelPacket(mid=rec.mid).encode(self.config.protocol)
        self.store.update_out(msg)
        self._send(msg.encoded_pubrel)

    def _on_pubrel(self, raw: RawPacket) -> None:
        rel = PubRelPacket.decode(raw.remaining, self.config.protocol)
        self.store.pop_in(rel.mid)
        self._send(PubCompPacket(mid=rel.mid).encode(self.config.protocol))

    def _on_pubcomp(self, raw: RawPacket) -> None:
        comp = PubCompPacket.decode(raw.remaining, self.config.protocol)
        msg = self.store.pop_out(comp.mid)
        if msg is None:
            return
        self.packet_ids.release(comp.mid)
        self.flow.release()
        self._emit(EffectKind.PUBLISH_COMPLETE, comp.mid)
        self._drain_queue()

    def _on_suback(self, raw: RawPacket) -> None:
        ack = SubAckPacket.decode(raw.remaining, self.config.protocol)
        self.packet_ids.release(ack.mid)
        self._emit(EffectKind.SUBACK, ack)

    def _on_unsuback(self, raw: RawPacket) -> None:
        ack = UnsubAckPacket.decode(raw.remaining, self.config.protocol)
        self.packet_ids.release(ack.mid)
        self._emit(EffectKind.UNSUBACK, ack)

    def _on_pingresp(self, raw: RawPacket) -> None:
        return

    def _on_pingreq(self, raw: RawPacket) -> None:
        self._send(encode_pingresp())

    def _on_disconnect(self, raw: RawPacket) -> None:
        self.state = ConnectionState.DISCONNECTED
        self._emit(EffectKind.DISCONNECTED)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _launch_outbound(self, msg: OutboundMessage) -> None:
        assert msg.encoded_publish is not None
        if msg.qos == QoS.AT_LEAST_ONCE:
            msg.state = OutboundQoSState.WAIT_PUBACK
        else:
            msg.state = OutboundQoSState.WAIT_PUBREC
        self.store.put_out(msg)
        self._send(msg.encoded_publish)

    def _drain_queue(self) -> None:
        while self._queued and self.flow.available > 0:
            if not self.flow.try_acquire():
                break
            msg = self._queued.pop(0)
            # Already in store as QUEUED.
            self._launch_outbound(msg)

    def _replay_session(self) -> None:
        """Retransmit unacked outbound messages in insertion order."""
        self.flow.reset()
        self._queued.clear()
        for msg in list(self.store.out_items()):
            if msg.state == OutboundQoSState.QUEUED:
                self._queued.append(msg)
                continue
            if not self.flow.try_acquire():
                # Should not happen if limit covers session; park as queued.
                msg.state = OutboundQoSState.QUEUED
                self._queued.append(msg)
                continue
            if msg.state == OutboundQoSState.WAIT_PUBCOMP:
                assert msg.encoded_pubrel is not None
                self._send(msg.encoded_pubrel)
            else:
                # WAIT_PUBACK / WAIT_PUBREC → republish with DUP.
                packet = PublishPacket(
                    topic=msg.topic,
                    payload=msg.payload,
                    qos=msg.qos,
                    retain=msg.retain,
                    dup=True,
                    mid=msg.mid,
                    properties=msg.properties,
                )
                msg.dup = True
                msg.encoded_publish = packet.encode(self.config.protocol)
                self.store.update_out(msg)
                self._send(msg.encoded_publish)
