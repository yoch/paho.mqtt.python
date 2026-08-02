"""MQTT packet framing helpers and typed packet views."""

from __future__ import annotations

from dataclasses import dataclass

from mqttnext.codec.primitives import pack_utf8, pack_u16, unpack_utf8, unpack_u16
from mqttnext.codec.properties import (
    CONNACK,
    CONNECT,
    DISCONNECT,
    PUBACK,
    PUBCOMP,
    PUBLISH,
    PUBREC,
    PUBREL,
    SUBACK,
    SUBSCRIBE,
    UNSUBACK,
    UNSUBSCRIBE,
    WILL,
    decode_properties,
    encode_properties,
)
from mqttnext.codec.vbi import append_vbi
from mqttnext.enums import MQTTProtocolVersion, PacketType, QoS
from mqttnext.errors import MalformedPacketError, ProtocolError
from mqttnext.transport.writes import SEGMENT_THRESHOLD, WriteItem
from mqttnext.types import Properties


_EMPTY_PROPS_V5 = b"\x00"


def encode_frame(packet_type: PacketType, flags: int, remaining: bytes | bytearray) -> bytes:
    if flags & 0xF0:
        raise ValueError("flags must fit in low nibble")
    header = bytearray(1)
    header[0] = int(packet_type) | (flags & 0x0F)
    append_vbi(header, len(remaining))
    header.extend(remaining)
    return bytes(header)


def _props_or_empty(
    props: Properties | None,
    packet: str,
    protocol: MQTTProtocolVersion,
) -> bytes:
    if protocol != MQTTProtocolVersion.MQTTv5:
        return b""
    if not props or not props.values:
        return _EMPTY_PROPS_V5
    return encode_properties(props, packet)


@dataclass(slots=True, frozen=True)
class SubscribeOptions:
    qos: QoS = QoS.AT_MOST_ONCE
    no_local: bool = False
    retain_as_published: bool = False
    retain_handling: int = 0  # 0, 1, or 2

    def encode_byte(self, protocol: MQTTProtocolVersion) -> int:
        if protocol != MQTTProtocolVersion.MQTTv5:
            if self.no_local or self.retain_as_published or self.retain_handling:
                raise ProtocolError("SubscribeOptions v5 flags require MQTT 5")
            return int(self.qos) & 0x03
        if self.retain_handling not in (0, 1, 2):
            raise ProtocolError("retain_handling must be 0, 1, or 2")
        return (
            (int(self.qos) & 0x03)
            | (int(self.no_local) << 2)
            | (int(self.retain_as_published) << 3)
            | ((self.retain_handling & 0x03) << 4)
        )


@dataclass(slots=True, frozen=True)
class PublishPacket:
    topic: str
    payload: bytes
    qos: QoS
    retain: bool
    dup: bool
    mid: int | None = None
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        item = self.encode_write_item(protocol)
        if isinstance(item, bytes):
            return item
        return item[0] + item[1]

    def encode_write_item(
        self,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> WriteItem:
        if self.qos and self.mid is None:
            raise ProtocolError("QoS > 0 PUBLISH requires a packet identifier")
        if self.qos == QoS.AT_MOST_ONCE and self.mid is not None:
            raise ProtocolError("QoS 0 PUBLISH must not carry a packet identifier")

        flags = 0
        if self.retain:
            flags |= 0x01
        flags |= (int(self.qos) & 0x03) << 1
        if self.dup:
            flags |= 0x08

        topic_bytes = self.topic.encode("utf-8")
        topic_len = len(topic_bytes)
        if topic_len > 65535:
            raise ValueError("UTF-8 string too long for MQTT")

        props = _props_or_empty(self.properties, PUBLISH, protocol)
        payload = self.payload
        payload_len = len(payload)
        mid_len = 2 if self.qos else 0
        remaining_length = 2 + topic_len + mid_len + len(props) + payload_len

        # Append-built buffer beats pre-sized index writes for typical small
        # PUBLISH frames (measured ~1.8× on QoS0 microbench).
        out = bytearray()
        out.append(int(PacketType.PUBLISH) | (flags & 0x0F))
        append_vbi(out, remaining_length)
        out.append((topic_len >> 8) & 0xFF)
        out.append(topic_len & 0xFF)
        out.extend(topic_bytes)
        if self.qos:
            assert self.mid is not None
            mid = self.mid
            out.append((mid >> 8) & 0xFF)
            out.append(mid & 0xFF)
        if props:
            out.extend(props)

        if payload_len >= SEGMENT_THRESHOLD and isinstance(payload, (bytes, bytearray)):
            return (bytes(out), bytes(payload))
        if payload_len:
            out.extend(payload)
        return bytes(out)

    @classmethod
    def decode(
        cls,
        flags: int,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PublishPacket:
        dup = bool(flags & 0x08)
        qos_raw = (flags >> 1) & 0x03
        if qos_raw == 3:
            raise MalformedPacketError("Invalid PUBLISH QoS 3")
        qos = QoS(qos_raw)
        retain = bool(flags & 0x01)

        topic, pos = unpack_utf8(remaining, 0)
        mid: int | None = None
        if qos:
            mid, pos = unpack_u16(remaining, pos)
            if mid == 0:
                raise MalformedPacketError("PUBLISH packet identifier must not be 0")
        properties: Properties | None = None
        if protocol == MQTTProtocolVersion.MQTTv5:
            properties, pos = decode_properties(remaining, pos, PUBLISH)
        # Owned bytes from IncrementalDecoder — slice once, no bytes() wrap.
        payload = remaining[pos:]
        return cls(
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
            dup=dup,
            mid=mid,
            properties=properties,
        )


@dataclass(slots=True, frozen=True)
class ConnectPacket:
    client_id: str
    clean_start: bool = True
    keepalive: int = 60
    username: str | None = None
    password: bytes | None = None
    will_topic: str | None = None
    will_payload: bytes = b""
    will_qos: QoS = QoS.AT_MOST_ONCE
    will_retain: bool = False
    will_properties: Properties | None = None
    protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311
    properties: Properties | None = None

    def encode(self) -> bytes:
        if self.protocol == MQTTProtocolVersion.MQTTv31:
            protocol_name = b"MQIsdp"
            protocol_level = 3
        elif self.protocol == MQTTProtocolVersion.MQTTv311:
            protocol_name = b"MQTT"
            protocol_level = 4
        elif self.protocol == MQTTProtocolVersion.MQTTv5:
            protocol_name = b"MQTT"
            protocol_level = 5
        else:
            raise ProtocolError(f"Unsupported protocol {self.protocol}")

        flags = 0
        if self.clean_start:
            flags |= 0x02
        if self.will_topic is not None:
            flags |= 0x04
            flags |= (int(self.will_qos) & 0x03) << 3
            if self.will_retain:
                flags |= 0x20
        if self.password is not None:
            flags |= 0x40
        if self.username is not None:
            flags |= 0x80

        body = bytearray()
        body.extend(pack_u16(len(protocol_name)))
        body.extend(protocol_name)
        body.append(protocol_level)
        body.append(flags)
        body.extend(pack_u16(self.keepalive))
        body.extend(_props_or_empty(self.properties, CONNECT, self.protocol))
        body.extend(pack_utf8(self.client_id))
        if self.will_topic is not None:
            body.extend(_props_or_empty(self.will_properties, WILL, self.protocol))
            body.extend(pack_utf8(self.will_topic))
            body.extend(pack_u16(len(self.will_payload)))
            body.extend(self.will_payload)
        if self.username is not None:
            body.extend(pack_utf8(self.username))
        if self.password is not None:
            body.extend(pack_u16(len(self.password)))
            body.extend(self.password)
        return encode_frame(PacketType.CONNECT, 0, body)


@dataclass(slots=True, frozen=True)
class ConnAckPacket:
    session_present: bool
    reason_code: int
    properties: Properties | None = None

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> ConnAckPacket:
        if len(remaining) < 2:
            raise MalformedPacketError("CONNACK too short")
        session_present = bool(remaining[0] & 0x01)
        reason_code = remaining[1]
        properties: Properties | None = None
        if protocol == MQTTProtocolVersion.MQTTv5:
            properties, _ = decode_properties(remaining, 2, CONNACK)
        return cls(
            session_present=session_present,
            reason_code=reason_code,
            properties=properties,
        )


@dataclass(slots=True, frozen=True)
class Subscription:
    topic: str
    options: SubscribeOptions = SubscribeOptions()


@dataclass(slots=True, frozen=True)
class SubscribePacket:
    mid: int
    subscriptions: tuple[Subscription, ...]
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        if not self.subscriptions:
            raise ProtocolError("SUBSCRIBE requires at least one filter")
        body = bytearray()
        body.extend(pack_u16(self.mid))
        body.extend(_props_or_empty(self.properties, SUBSCRIBE, protocol))
        for sub in self.subscriptions:
            body.extend(pack_utf8(sub.topic))
            body.append(sub.options.encode_byte(protocol))
        return encode_frame(PacketType.SUBSCRIBE, 0x02, body)


@dataclass(slots=True, frozen=True)
class SubAckPacket:
    mid: int
    reason_codes: tuple[int, ...]
    properties: Properties | None = None

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> SubAckPacket:
        if len(remaining) < 3:
            raise MalformedPacketError("SUBACK too short")
        mid, pos = unpack_u16(remaining, 0)
        properties: Properties | None = None
        if protocol == MQTTProtocolVersion.MQTTv5:
            properties, pos = decode_properties(remaining, pos, SUBACK)
        if pos >= len(remaining):
            raise MalformedPacketError("SUBACK missing reason codes")
        return cls(mid=mid, reason_codes=tuple(remaining[pos:]), properties=properties)


@dataclass(slots=True, frozen=True)
class UnsubscribePacket:
    mid: int
    topics: tuple[str, ...]
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        if not self.topics:
            raise ProtocolError("UNSUBSCRIBE requires at least one filter")
        body = bytearray()
        body.extend(pack_u16(self.mid))
        body.extend(_props_or_empty(self.properties, UNSUBSCRIBE, protocol))
        for topic in self.topics:
            body.extend(pack_utf8(topic))
        return encode_frame(PacketType.UNSUBSCRIBE, 0x02, body)


@dataclass(slots=True, frozen=True)
class UnsubAckPacket:
    mid: int
    reason_codes: tuple[int, ...] = ()
    properties: Properties | None = None

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> UnsubAckPacket:
        if len(remaining) < 2:
            raise MalformedPacketError("UNSUBACK too short")
        mid, pos = unpack_u16(remaining, 0)
        if protocol == MQTTProtocolVersion.MQTTv5:
            properties, pos = decode_properties(remaining, pos, UNSUBACK)
            return cls(mid=mid, reason_codes=tuple(remaining[pos:]), properties=properties)
        return cls(mid=mid)


def _decode_ack_with_reason(
    remaining: bytes,
    protocol: MQTTProtocolVersion,
    packet_name: str,
) -> tuple[int, int, Properties | None]:
    if len(remaining) < 2:
        raise MalformedPacketError(f"{packet_name} too short")
    mid, pos = unpack_u16(remaining, 0)
    if mid == 0:
        raise MalformedPacketError(f"{packet_name} packet identifier must not be 0")
    reason = 0
    properties: Properties | None = None
    if protocol == MQTTProtocolVersion.MQTTv5 and pos < len(remaining):
        reason = remaining[pos]
        pos += 1
        if pos < len(remaining):
            properties, pos = decode_properties(remaining, pos, packet_name)
        else:
            properties = Properties()
    return mid, reason, properties


def _encode_ack_with_reason(
    packet_type: PacketType,
    flags: int,
    mid: int,
    reason_code: int,
    properties: Properties | None,
    packet_name: str,
    protocol: MQTTProtocolVersion,
) -> bytes:
    body = bytearray(pack_u16(mid))
    if protocol == MQTTProtocolVersion.MQTTv5:
        if reason_code != 0 or (properties and properties.values):
            body.append(reason_code)
            body.extend(encode_properties(properties, packet_name))
    return encode_frame(packet_type, flags, body)


@dataclass(slots=True, frozen=True)
class PubAckPacket:
    mid: int
    reason_code: int = 0
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        return _encode_ack_with_reason(
            PacketType.PUBACK, 0, self.mid, self.reason_code, self.properties, PUBACK, protocol
        )

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubAckPacket:
        mid, reason, props = _decode_ack_with_reason(remaining, protocol, PUBACK)
        return cls(mid=mid, reason_code=reason, properties=props)


@dataclass(slots=True, frozen=True)
class PubRecPacket:
    mid: int
    reason_code: int = 0
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        return _encode_ack_with_reason(
            PacketType.PUBREC, 0, self.mid, self.reason_code, self.properties, PUBREC, protocol
        )

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubRecPacket:
        mid, reason, props = _decode_ack_with_reason(remaining, protocol, PUBREC)
        return cls(mid=mid, reason_code=reason, properties=props)


@dataclass(slots=True, frozen=True)
class PubRelPacket:
    mid: int
    reason_code: int = 0
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        return _encode_ack_with_reason(
            PacketType.PUBREL, 0x02, self.mid, self.reason_code, self.properties, PUBREL, protocol
        )

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubRelPacket:
        mid, reason, props = _decode_ack_with_reason(remaining, protocol, PUBREL)
        return cls(mid=mid, reason_code=reason, properties=props)


@dataclass(slots=True, frozen=True)
class PubCompPacket:
    mid: int
    reason_code: int = 0
    properties: Properties | None = None

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        return _encode_ack_with_reason(
            PacketType.PUBCOMP, 0, self.mid, self.reason_code, self.properties, PUBCOMP, protocol
        )

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubCompPacket:
        mid, reason, props = _decode_ack_with_reason(remaining, protocol, PUBCOMP)
        return cls(mid=mid, reason_code=reason, properties=props)


@dataclass(slots=True, frozen=True)
class DisconnectPacket:
    reason_code: int = 0
    properties: Properties | None = None

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> DisconnectPacket:
        if protocol != MQTTProtocolVersion.MQTTv5 or not remaining:
            return cls(reason_code=0, properties=None)
        reason = remaining[0]
        properties: Properties | None = None
        if len(remaining) > 1:
            properties, _ = decode_properties(remaining, 1, DISCONNECT)
        return cls(reason_code=reason, properties=properties)


def encode_pingreq() -> bytes:
    return encode_frame(PacketType.PINGREQ, 0, b"")


def encode_pingresp() -> bytes:
    return encode_frame(PacketType.PINGRESP, 0, b"")


def encode_disconnect(
    reason_code: int = 0,
    protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    properties: Properties | None = None,
) -> bytes:
    if protocol == MQTTProtocolVersion.MQTTv5:
        body = bytearray()
        body.append(reason_code)
        body.extend(encode_properties(properties, DISCONNECT))
        return encode_frame(PacketType.DISCONNECT, 0, body)
    return encode_frame(PacketType.DISCONNECT, 0, b"")
