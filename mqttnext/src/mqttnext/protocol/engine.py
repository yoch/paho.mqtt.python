"""Synchronous MQTT protocol engine.

No asyncio, no sockets, no user callbacks. Feed packets / commands in, collect
effects out. This is the correctness core that AsyncClient adapts.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from mqttnext.codec.buffer import RawPacket
from mqttnext.codec.properties import PUBLISH, encode_properties
from mqttnext.enums import (
    ConnectionState,
    InboundQoSState,
    MQTTProtocolVersion,
    OutboundQoSState,
    PacketType,
    QoS,
)
from mqttnext.packets import (
    ConnAckPacket,
    ConnectPacket,
    DisconnectPacket,
    PubAckPacket,
    PubCompPacket,
    PublishPacket,
    PubRecPacket,
    PubRelPacket,
    SubAckPacket,
    SubscribeOptions,
    SubscribePacket,
    Subscription,
    UnsubAckPacket,
    UnsubscribePacket,
    encode_disconnect,
    encode_pingreq,
    encode_pingresp,
)
from mqttnext.persistence.memory import InflightStore, MemoryInflightStore
from mqttnext.protocol.flow_control import FlowControl
from mqttnext.protocol.negotiated import NegotiatedSettings
from mqttnext.protocol.packet_ids import PacketIdPool
from mqttnext.protocol.validate import validate_raw_packet
from mqttnext.topics import (
    validate_publish_topic,
    validate_received_publish_topic,
    validate_subscribe_filter,
)
from mqttnext.transport.writes import WriteItem, item_size
from mqttnext.types import InboundMessage, Message, OutboundMessage, Properties
from mqttnext.errors import (
    FlowControlError,
    MalformedPacketError,
    NotConnectedError,
    PacketTooLargeError,
    ProtocolError,
    SessionDiscardedError,
)

class EffectKind(Enum):
    SEND = auto()
    MESSAGE = auto()
    CONNACK = auto()
    PUBLISH_COMPLETE = auto()
    PUBLISH_FAILED = auto()
    SUBACK = auto()
    UNSUBACK = auto()
    DISCONNECTED = auto()
    PROTOCOL_ERROR = auto()
    PINGRESP = auto()


@dataclass(slots=True)
class EngineEffect:
    kind: EffectKind
    data: Any = None


@dataclass(slots=True)
class PublishHandle:
    mid: int | None
    qos: QoS


@dataclass(slots=True)
class PublishFailure:
    mid: int
    reason: BaseException


@dataclass(slots=True)
class DisconnectInfo:
    """Broker or local disconnect signal carried on EffectKind.DISCONNECTED."""

    reason_code: int = 0
    properties: Properties | None = None
    from_broker: bool = False


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
    connect_properties: Properties | None = None
    will: Message | None = None
    will_properties: Properties | None = None
    # Local maximum packet size announced to broker (and enforced on ingress).
    maximum_packet_size: int | None = None
    topic_alias_maximum: int = 0  # announced to broker for inbound aliases
    manual_ack: bool = False  # defer PUBACK (QoS1) / PUBCOMP (QoS2) until ack()


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
        self.negotiated = NegotiatedSettings()
        self._pending_connect = False
        self._effects: list[EngineEffect] = []
        self._queued: deque[OutboundMessage] = deque()
        # Inbound topic aliases (connection-scoped).
        self._topic_aliases: dict[int, str] = {}
        # After a durable session is established, next CONNECT uses Clean Start 0.
        self._prefer_session_resume = False
        # Server→client QoS>0 not yet fully acknowledged (Receive Maximum).
        self._inbound_inflight = 0
        self._handlers = {
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
            PacketType.AUTH: self._on_auth,
        }
        # Hydrate packet ids + offline queue from a durable store (restart).
        for msg in list(self.store.out_items()):
            self.packet_ids.reserve(msg.mid)
            if msg.state is OutboundQoSState.QUEUED:
                self._queued.append(msg)
            elif msg.state in (
                OutboundQoSState.WAIT_PUBACK,
                OutboundQoSState.WAIT_PUBREC,
                OutboundQoSState.WAIT_PUBCOMP,
            ):
                self.flow.try_acquire()

    def take_effects(self) -> list[EngineEffect]:
        effects = self._effects
        self._effects = []
        return effects

    def _emit(self, kind: EffectKind, data: Any = None) -> None:
        self._effects.append(EngineEffect(kind=kind, data=data))

    def _send(self, packet: WriteItem) -> None:
        self._emit(EffectKind.SEND, packet)

    def begin_connect(self) -> bytes:
        if self.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            raise ProtocolError("Already connected or connecting")
        self.state = ConnectionState.CONNECTING
        self._pending_connect = True
        self._topic_aliases.clear()
        self._inbound_inflight = 0

        clean_start = self.config.clean_start
        if self._prefer_session_resume:
            clean_start = False

        connect_props = self.config.connect_properties
        if self.config.protocol == MQTTProtocolVersion.MQTTv5:
            connect_props = Properties(
                values=dict(connect_props.values) if connect_props else {}
            )
            if "receive_maximum" not in connect_props.values:
                connect_props.set("receive_maximum", self.config.local_receive_maximum)
            if (
                self.config.maximum_packet_size is not None
                and "maximum_packet_size" not in connect_props.values
            ):
                connect_props.set("maximum_packet_size", self.config.maximum_packet_size)
            if (
                self.config.topic_alias_maximum
                and "topic_alias_maximum" not in connect_props.values
            ):
                connect_props.set("topic_alias_maximum", self.config.topic_alias_maximum)

        will = self.config.will
        packet = ConnectPacket(
            client_id=self.config.client_id,
            clean_start=clean_start,
            keepalive=self.config.keepalive,
            username=self.config.username,
            password=self.config.password,
            will_topic=will.topic if will else None,
            will_payload=will.payload if will else b"",
            will_qos=will.qos if will else QoS.AT_MOST_ONCE,
            will_retain=will.retain if will else False,
            will_properties=self.config.will_properties,
            protocol=self.config.protocol,
            properties=connect_props,
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
        allow_empty = bool(
            properties
            and properties.get("topic_alias")
            and self.config.protocol == MQTTProtocolVersion.MQTTv5
        )
        validate_publish_topic(topic, allow_empty=allow_empty)

        if self.state == ConnectionState.CONNECTED:
            if qos > self.negotiated.maximum_qos:
                raise ProtocolError(
                    f"QoS {int(qos)} exceeds broker maximum_qos {self.negotiated.maximum_qos}"
                )
            if retain and not self.negotiated.retain_available:
                raise ProtocolError("Broker does not support retain")
            if properties and properties.get("topic_alias") is not None:
                alias = int(properties.get("topic_alias"))
                if alias > self.negotiated.topic_alias_maximum:
                    raise ProtocolError(
                        f"topic_alias {alias} exceeds broker topic_alias_maximum "
                        f"{self.negotiated.topic_alias_maximum}"
                    )

        if self.state != ConnectionState.CONNECTED and qos == QoS.AT_MOST_ONCE:
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
            wire = packet.encode_write_item(self.config.protocol)
            self._check_outbound_size(wire)
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
        # Defer wire encode until launch: avoids double work when messages sit
        # in the Receive Maximum queue. Still enforce maximum_packet_size via
        # a cheap upper-bound estimate when the broker advertised a limit.
        self._check_outbound_publish_budget(topic, payload, qos, properties)

        if self.state == ConnectionState.CONNECTED and self.flow.try_acquire():
            self._launch_outbound(msg)
        else:
            if self.config.max_queued and len(self._queued) >= self.config.max_queued:
                self.packet_ids.release(mid)
                raise FlowControlError("Outbound queue full")
            self._queued.append(msg)
            self.store.put_out(msg)
        return PublishHandle(mid=mid, qos=qos)

    def queue_subscribe(
        self,
        topics: str | Iterable[str | tuple[str, SubscribeOptions | int | QoS]],
        *,
        qos: QoS | int = QoS.AT_MOST_ONCE,
        properties: Properties | None = None,
    ) -> int:
        if self.state != ConnectionState.CONNECTED:
            raise NotConnectedError("subscribe requires an active connection")

        subscriptions: list[Subscription] = []
        if isinstance(topics, str):
            validate_subscribe_filter(topics)
            self._check_subscribe_capabilities(topics, properties)
            subscriptions.append(
                Subscription(topic=topics, options=SubscribeOptions(qos=QoS(qos)))
            )
        else:
            for item in topics:
                if isinstance(item, str):
                    topic, options = item, SubscribeOptions(qos=QoS(qos))
                else:
                    topic, opt = item
                    if isinstance(opt, SubscribeOptions):
                        options = opt
                    else:
                        options = SubscribeOptions(qos=QoS(opt))
                validate_subscribe_filter(topic)
                self._check_subscribe_capabilities(topic, properties)
                subscriptions.append(Subscription(topic=topic, options=options))

        mid = self.packet_ids.allocate()
        packet = SubscribePacket(
            mid=mid,
            subscriptions=tuple(subscriptions),
            properties=properties,
        )
        wire = packet.encode(self.config.protocol)
        self._check_outbound_size(wire)
        self._send(wire)
        return mid

    def queue_unsubscribe(self, topics: str | Iterable[str]) -> int:
        if self.state != ConnectionState.CONNECTED:
            raise NotConnectedError("unsubscribe requires an active connection")
        if isinstance(topics, str):
            topic_list = (topics,)
        else:
            topic_list = tuple(topics)
        if not topic_list:
            raise ProtocolError("unsubscribe requires at least one topic")
        mid = self.packet_ids.allocate()
        packet = UnsubscribePacket(mid=mid, topics=topic_list)
        self._send(packet.encode(self.config.protocol))
        return mid

    def queue_ping(self) -> None:
        self._send(encode_pingreq())

    def begin_disconnect(
        self,
        reason_code: int = 0,
        properties: Properties | None = None,
    ) -> bytes:
        self.state = ConnectionState.DISCONNECTING
        return encode_disconnect(reason_code, self.config.protocol, properties)

    def notify_transport_closed(self) -> None:
        was = self.state
        self.state = ConnectionState.DISCONNECTED
        self._topic_aliases.clear()
        if was != ConnectionState.DISCONNECTED:
            self._emit(EffectKind.DISCONNECTED, DisconnectInfo(from_broker=False))

    def handle_raw(self, raw: RawPacket) -> None:
        handler = self._handlers.get(raw.packet_type)
        if handler is None:
            self._emit(EffectKind.PROTOCOL_ERROR, f"Unhandled packet {raw.packet_type!r}")
            return
        try:
            validate_raw_packet(raw)
            handler(raw)
        except (ProtocolError, MalformedPacketError) as exc:
            self._emit(EffectKind.PROTOCOL_ERROR, str(exc))


    def _on_connack(self, raw: RawPacket) -> None:
        connack = ConnAckPacket.decode(raw.remaining, self.config.protocol)
        self._pending_connect = False
        if connack.reason_code != 0:
            self.state = ConnectionState.DISCONNECTED
            self._emit(EffectKind.CONNACK, connack)
            self._emit(EffectKind.DISCONNECTED)
            return

        requested_expiry = None
        if self.config.connect_properties:
            requested_expiry = self.config.connect_properties.get("session_expiry_interval")
        self.negotiated = NegotiatedSettings.from_connack(
            connack.properties,
            requested_keepalive=self.config.keepalive,
            requested_session_expiry=requested_expiry,
            local_client_id=self.config.client_id,
        )
        self.flow.apply_broker_receive_maximum(
            self.negotiated.receive_maximum,
            self.config.local_receive_maximum,
        )

        self.state = ConnectionState.CONNECTED
        self.session_present = connack.session_present
        self._update_session_resume_preference()
        if not connack.session_present:
            for msg in list(self.store.out_items()):
                if msg.state is OutboundQoSState.QUEUED:
                    continue
                self.store.pop_out(msg.mid)
                self.packet_ids.release(msg.mid)
                self._emit(
                    EffectKind.PUBLISH_FAILED,
                    PublishFailure(
                        mid=msg.mid,
                        reason=SessionDiscardedError(
                            "Publish lost: clean session replaced the previous one"
                        ),
                    ),
                )
            self.store.clear_in()
            self.flow.reset()
            # Re-apply negotiated limit after reset.
            self.flow.apply_broker_receive_maximum(
                self.negotiated.receive_maximum,
                self.config.local_receive_maximum,
            )
        else:
            self._replay_session()

        self._fail_queued_violating_negotiation()
        self._emit(EffectKind.CONNACK, connack)
        self._drain_queue()

    def _on_publish(self, raw: RawPacket) -> None:
        packet = PublishPacket.decode(raw.flags, raw.remaining, self.config.protocol)
        topic = self._resolve_inbound_topic(packet)
        validate_received_publish_topic(topic)

        if packet.qos == QoS.AT_MOST_ONCE:
            self._emit(
                EffectKind.MESSAGE,
                Message(
                    topic=topic,
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
        if packet.qos == QoS.EXACTLY_ONCE:
            existing = self.store.get_in(packet.mid)
            if existing is not None:
                self._send(PubRecPacket(mid=packet.mid).encode(self.config.protocol))
                return

        self._acquire_inbound_slot()
        if packet.qos == QoS.AT_LEAST_ONCE:
            self._emit(
                EffectKind.MESSAGE,
                Message(
                    topic=topic,
                    payload=packet.payload,
                    qos=packet.qos,
                    retain=packet.retain,
                    dup=packet.dup,
                    mid=packet.mid,
                    properties=packet.properties,
                ),
            )
            if self.config.manual_ack:
                self.store.put_in(
                    InboundMessage(
                        mid=packet.mid,
                        topic=topic,
                        payload=packet.payload,
                        qos=packet.qos,
                        retain=packet.retain,
                        state=InboundQoSState.WAIT_PUBACK,
                        delivered=True,
                        properties=packet.properties,
                    )
                )
            else:
                self._send(PubAckPacket(mid=packet.mid).encode(self.config.protocol))
                self._release_inbound_slot()
            return

        inbound = InboundMessage(
            mid=packet.mid,
            topic=topic,
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
                topic=topic,
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
        msg = self.store.get_out(ack.mid)
        if msg is None or msg.state is not OutboundQoSState.WAIT_PUBACK:
            return
        self.store.pop_out(ack.mid)
        self.packet_ids.release(ack.mid)
        self.flow.release()
        if ack.reason_code >= 128:
            self._emit(
                EffectKind.PUBLISH_FAILED,
                PublishFailure(
                    mid=ack.mid,
                    reason=ProtocolError(f"PUBACK reason_code={ack.reason_code}"),
                ),
            )
        else:
            self._emit(EffectKind.PUBLISH_COMPLETE, ack.mid)
        self._drain_queue()

    def _on_pubrec(self, raw: RawPacket) -> None:
        rec = PubRecPacket.decode(raw.remaining, self.config.protocol)
        msg = self.store.get_out(rec.mid)
        if msg is None:
            # Orphan PUBREC: reply PUBREL with 0x92 when MQTT 5.
            reason = 0x92 if self.config.protocol == MQTTProtocolVersion.MQTTv5 else 0
            self._send(
                PubRelPacket(mid=rec.mid, reason_code=reason).encode(self.config.protocol)
            )
            return
        if msg.state is not OutboundQoSState.WAIT_PUBREC:
            return
        if rec.reason_code >= 128:
            self.store.pop_out(rec.mid)
            self.packet_ids.release(rec.mid)
            self.flow.release()
            self._emit(
                EffectKind.PUBLISH_FAILED,
                PublishFailure(
                    mid=rec.mid,
                    reason=ProtocolError(f"PUBREC reason_code={rec.reason_code}"),
                ),
            )
            self._drain_queue()
            return
        msg.state = OutboundQoSState.WAIT_PUBCOMP
        if msg.encoded_pubrel is None:
            msg.encoded_pubrel = PubRelPacket(mid=rec.mid).encode(self.config.protocol)
        self.store.update_out(msg)
        # Keep the local flow slot until PUBCOMP. MQTT 5 allows releasing at
        # PUBREC, but freeing early lets WAIT_PUBCOMP accumulate without bound
        # and has caused intermittent multi-second stalls under load.
        self._send(msg.encoded_pubrel)

    def _on_pubrel(self, raw: RawPacket) -> None:
        rel = PubRelPacket.decode(raw.remaining, self.config.protocol)
        inbound = self.store.get_in(rel.mid)
        if inbound is None:
            # Orphan PUBREL: idempotent PUBCOMP (v5 reason 0x92 optional later).
            self._send(PubCompPacket(mid=rel.mid).encode(self.config.protocol))
            return
        if self.config.manual_ack and not inbound.user_acked:
            inbound.state = InboundQoSState.WAIT_USER_ACK
            self.store.update_in(inbound)
            return
        self.store.pop_in(rel.mid)
        self._send(PubCompPacket(mid=rel.mid).encode(self.config.protocol))
        self._release_inbound_slot()

    def ack(self, mid: int) -> None:
        """Complete a deferred inbound ACK (manual_ack mode).

        QoS 1: send PUBACK. QoS 2: mark ready / send PUBCOMP if PUBREL already seen.
        """
        if not self.config.manual_ack:
            raise ProtocolError("manual_ack is disabled")
        inbound = self.store.get_in(mid)
        if inbound is None:
            raise ProtocolError(f"No pending inbound ack for mid={mid}")
        if inbound.state is InboundQoSState.WAIT_PUBACK:
            self.store.pop_in(mid)
            self._send(PubAckPacket(mid=mid).encode(self.config.protocol))
            self._release_inbound_slot()
            return
        if inbound.state is InboundQoSState.WAIT_PUBREL:
            inbound.user_acked = True
            self.store.update_in(inbound)
            return
        if inbound.state is InboundQoSState.WAIT_USER_ACK:
            self.store.pop_in(mid)
            self._send(PubCompPacket(mid=mid).encode(self.config.protocol))
            self._release_inbound_slot()
            return
        raise ProtocolError(f"Inbound mid={mid} is not awaiting ack (state={inbound.state!r})")

    def _on_pubcomp(self, raw: RawPacket) -> None:
        comp = PubCompPacket.decode(raw.remaining, self.config.protocol)
        msg = self.store.get_out(comp.mid)
        if msg is None or msg.state is not OutboundQoSState.WAIT_PUBCOMP:
            return
        self.store.pop_out(comp.mid)
        self.packet_ids.release(comp.mid)
        self.flow.release()
        if comp.reason_code >= 128:
            self._emit(
                EffectKind.PUBLISH_FAILED,
                PublishFailure(
                    mid=comp.mid,
                    reason=ProtocolError(f"PUBCOMP reason_code={comp.reason_code}"),
                ),
            )
        else:
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
        self._emit(EffectKind.PINGRESP)

    def _on_pingreq(self, raw: RawPacket) -> None:
        # Brokers must not send PINGREQ to clients.
        raise ProtocolError("Unexpected PINGREQ from broker")

    def _on_disconnect(self, raw: RawPacket) -> None:
        packet = DisconnectPacket.decode(raw.remaining, self.config.protocol)
        self.state = ConnectionState.DISCONNECTED
        self._emit(
            EffectKind.DISCONNECTED,
            DisconnectInfo(
                reason_code=packet.reason_code,
                properties=packet.properties,
                from_broker=True,
            ),
        )

    def _on_auth(self, raw: RawPacket) -> None:
        # Phase 1 stub: reject unsolicited AUTH.
        self._send(
            encode_disconnect(
                0x8C,
                self.config.protocol,
            )
        )
        self.state = ConnectionState.DISCONNECTED
        self._emit(EffectKind.DISCONNECTED, DisconnectInfo(reason_code=0x8C, from_broker=False))

    def _launch_outbound(self, msg: OutboundMessage) -> None:
        if msg.encoded_publish is None:
            msg.encoded_publish = PublishPacket(
                topic=msg.topic,
                payload=msg.payload,
                qos=msg.qos,
                retain=msg.retain,
                dup=msg.dup,
                mid=msg.mid,
                properties=msg.properties,
            ).encode_write_item(self.config.protocol)
        self._check_outbound_size(msg.encoded_publish)
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
            msg = self._queued.popleft()
            self._launch_outbound(msg)

    def _replay_session(self) -> None:
        self.flow.reset()
        self.flow.apply_broker_receive_maximum(
            self.negotiated.receive_maximum,
            self.config.local_receive_maximum,
        )
        self._queued.clear()
        for msg in list(self.store.out_items()):
            if msg.state == OutboundQoSState.QUEUED:
                self._queued.append(msg)
                continue
            if msg.state == OutboundQoSState.WAIT_PUBCOMP:
                if msg.encoded_pubrel is None:
                    msg.encoded_pubrel = PubRelPacket(mid=msg.mid).encode(self.config.protocol)
                    self.store.update_out(msg)
                self.flow.try_acquire()
                self._send(msg.encoded_pubrel)
                continue
            if not self.flow.try_acquire():
                msg.state = OutboundQoSState.QUEUED
                self.store.update_out(msg)
                self._queued.append(msg)
                continue
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
            msg.encoded_publish = packet.encode_write_item(self.config.protocol)
            self.store.update_out(msg)
            self._send(msg.encoded_publish)
        self._drain_queue()

    def _resolve_inbound_topic(self, packet: PublishPacket) -> str:
        if self.config.protocol != MQTTProtocolVersion.MQTTv5:
            return packet.topic
        props = packet.properties
        alias = props.get("topic_alias") if props else None
        if alias is None:
            return packet.topic
        alias = int(alias)
        max_alias = self.config.topic_alias_maximum
        # max_alias == 0 means inbound aliases are not accepted.
        if alias == 0 or alias > max_alias:
            raise ProtocolError(f"Invalid topic alias {alias}")
        if packet.topic:
            self._topic_aliases[alias] = packet.topic
            return packet.topic
        if alias not in self._topic_aliases:
            raise ProtocolError(f"Unknown topic alias {alias}")
        return self._topic_aliases[alias]

    def _check_outbound_size(self, wire: WriteItem) -> None:
        limit = self.negotiated.maximum_packet_size
        size = item_size(wire)
        if limit is not None and size > limit:
            raise PacketTooLargeError(
                f"Encoded packet size {size} exceeds broker maximum_packet_size {limit}"
            )

    def _check_outbound_publish_budget(
        self,
        topic: str,
        payload: bytes,
        qos: QoS,
        properties: Properties | None,
    ) -> None:
        """Cheap upper bound vs negotiated maximum_packet_size (before full encode)."""
        limit = self.negotiated.maximum_packet_size
        if limit is None:
            return
        topic_len = len(topic.encode("utf-8"))
        props_len = 0
        if self.config.protocol == MQTTProtocolVersion.MQTTv5:
            # Worst case: encode_properties; empty → 1 byte.
            props_len = len(encode_properties(properties, PUBLISH))
        mid_len = 2 if qos else 0
        # Fixed header worst case: 1 type + 4 VBI bytes.
        estimate = 1 + 4 + 2 + topic_len + mid_len + props_len + len(payload)
        if estimate > limit:
            # Exact check — estimate is pessimistic on VBI length.
            wire = PublishPacket(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=False,
                dup=False,
                mid=1 if qos else None,
                properties=properties,
            ).encode_write_item(self.config.protocol)
            self._check_outbound_size(wire)

    def _check_subscribe_capabilities(
        self,
        topic: str,
        properties: Properties | None,
    ) -> None:
        if topic.startswith("$share/") and not self.negotiated.shared_subscription_available:
            raise ProtocolError("Broker does not support shared subscriptions")
        if ("+" in topic or "#" in topic) and not self.negotiated.wildcard_subscription_available:
            raise ProtocolError("Broker does not support wildcard subscriptions")
        if (
            properties
            and properties.get("subscription_identifier") is not None
            and not self.negotiated.subscription_identifier_available
        ):
            raise ProtocolError("Broker does not support subscription identifiers")

    def _acquire_inbound_slot(self) -> None:
        limit = self.config.local_receive_maximum
        if self._inbound_inflight >= limit:
            raise ProtocolError("Receive Maximum exceeded")
        self._inbound_inflight += 1

    def _release_inbound_slot(self) -> None:
        if self._inbound_inflight > 0:
            self._inbound_inflight -= 1

    def _update_session_resume_preference(self) -> None:
        """Next CONNECT should use Clean Start 0 when the session is durable."""
        if self.config.protocol == MQTTProtocolVersion.MQTTv5:
            expiry = self.negotiated.session_expiry_interval
            self._prefer_session_resume = bool(expiry)
        else:
            self._prefer_session_resume = not self.config.clean_start

    def _validate_outbound_against_negotiated(self, msg: OutboundMessage) -> None:
        if int(msg.qos) > self.negotiated.maximum_qos:
            raise ProtocolError(
                f"QoS {int(msg.qos)} exceeds broker maximum_qos {self.negotiated.maximum_qos}"
            )
        if msg.retain and not self.negotiated.retain_available:
            raise ProtocolError("Broker does not support retain")
        if msg.properties and msg.properties.get("topic_alias") is not None:
            alias = int(msg.properties.get("topic_alias"))
            if alias > self.negotiated.topic_alias_maximum:
                raise ProtocolError(
                    f"topic_alias {alias} exceeds broker topic_alias_maximum "
                    f"{self.negotiated.topic_alias_maximum}"
                )
        if msg.encoded_publish is not None:
            self._check_outbound_size(msg.encoded_publish)
        else:
            self._check_outbound_publish_budget(
                msg.topic, msg.payload, msg.qos, msg.properties
            )

    def _fail_queued_violating_negotiation(self) -> None:
        kept: deque[OutboundMessage] = deque()
        while self._queued:
            msg = self._queued.popleft()
            try:
                self._validate_outbound_against_negotiated(msg)
            except (ProtocolError, PacketTooLargeError) as exc:
                self.store.pop_out(msg.mid)
                self.packet_ids.release(msg.mid)
                self._emit(
                    EffectKind.PUBLISH_FAILED,
                    PublishFailure(mid=msg.mid, reason=exc),
                )
                continue
            kept.append(msg)
        self._queued = kept
