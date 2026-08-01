"""MQTT packet framing helpers and typed packet views."""

from __future__ import annotations

from dataclasses import dataclass

from mqttnext.codec.primitives import pack_utf8, pack_u16, unpack_utf8, unpack_u16
from mqttnext.codec.vbi import encode_vbi, vbi_len
from mqttnext.enums import MQTTProtocolVersion, PacketType, QoS
from mqttnext.errors import MalformedPacketError, ProtocolError
from mqttnext.types import Properties


def encode_frame(packet_type: PacketType, flags: int, remaining: bytes | bytearray) -> bytes:
    if flags & 0xF0:
        raise ValueError("flags must fit in low nibble")
    header = bytearray()
    header.append(int(packet_type) | (flags & 0x0F))
    header.extend(encode_vbi(len(remaining)))
    header.extend(remaining)
    return bytes(header)


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

        body = bytearray()
        body.extend(pack_utf8(self.topic))
        if self.qos:
            assert self.mid is not None
            body.extend(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5:
            # Empty properties fast path (audit §01 / §11).
            if self.properties and self.properties.values:
                raise NotImplementedError("MQTT 5 property encoding lands in phase 1")
            body.append(0x00)
        body.extend(self.payload)
        return encode_frame(PacketType.PUBLISH, flags, body)

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
        properties: Properties | None = None
        if protocol == MQTTProtocolVersion.MQTTv5:
            if pos >= len(remaining):
                raise MalformedPacketError("Missing PUBLISH properties length")
            # Phase 0: only empty properties.
            if remaining[pos] != 0:
                raise NotImplementedError("MQTT 5 property decoding lands in phase 1")
            pos += 1
            properties = Properties()
        payload = bytes(remaining[pos:])
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
        if self.protocol == MQTTProtocolVersion.MQTTv5:
            if self.properties and self.properties.values:
                raise NotImplementedError("MQTT 5 CONNECT properties in phase 1")
            body.append(0x00)
        body.extend(pack_utf8(self.client_id))
        if self.will_topic is not None:
            if self.protocol == MQTTProtocolVersion.MQTTv5:
                body.append(0x00)  # will properties empty
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
            if len(remaining) < 3:
                raise MalformedPacketError("CONNACK missing properties")
            if remaining[2] != 0:
                raise NotImplementedError("MQTT 5 CONNACK properties in phase 1")
            properties = Properties()
        return cls(session_present=session_present, reason_code=reason_code, properties=properties)


@dataclass(slots=True, frozen=True)
class SubscribePacket:
    mid: int
    topic: str
    qos: QoS

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        body = bytearray()
        body.extend(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5:
            body.append(0x00)
        body.extend(pack_utf8(self.topic))
        body.append(int(self.qos) & 0x03)
        return encode_frame(PacketType.SUBSCRIBE, 0x02, body)


@dataclass(slots=True, frozen=True)
class SubAckPacket:
    mid: int
    reason_codes: tuple[int, ...]

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> SubAckPacket:
        if len(remaining) < 3:
            raise MalformedPacketError("SUBACK too short")
        mid, pos = unpack_u16(remaining, 0)
        if protocol == MQTTProtocolVersion.MQTTv5:
            if pos >= len(remaining):
                raise MalformedPacketError("SUBACK missing properties")
            if remaining[pos] != 0:
                raise NotImplementedError("MQTT 5 SUBACK properties in phase 1")
            pos += 1
        if pos >= len(remaining):
            raise MalformedPacketError("SUBACK missing reason codes")
        return cls(mid=mid, reason_codes=tuple(remaining[pos:]))


@dataclass(slots=True, frozen=True)
class UnsubscribePacket:
    mid: int
    topic: str

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        body = bytearray()
        body.extend(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5:
            body.append(0x00)
        body.extend(pack_utf8(self.topic))
        return encode_frame(PacketType.UNSUBSCRIBE, 0x02, body)


@dataclass(slots=True, frozen=True)
class UnsubAckPacket:
    mid: int
    reason_codes: tuple[int, ...] = ()

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
            if pos >= len(remaining):
                raise MalformedPacketError("UNSUBACK missing properties")
            if remaining[pos] != 0:
                raise NotImplementedError("MQTT 5 UNSUBACK properties in phase 1")
            pos += 1
            return cls(mid=mid, reason_codes=tuple(remaining[pos:]))
        return cls(mid=mid)


@dataclass(slots=True, frozen=True)
class PubAckPacket:
    mid: int
    reason_code: int = 0

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        body = bytearray(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5 and self.reason_code != 0:
            body.append(self.reason_code)
            body.append(0x00)
        return encode_frame(PacketType.PUBACK, 0, body)

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubAckPacket:
        mid, pos = unpack_u16(remaining, 0)
        reason = 0
        if protocol == MQTTProtocolVersion.MQTTv5 and pos < len(remaining):
            reason = remaining[pos]
        return cls(mid=mid, reason_code=reason)


@dataclass(slots=True, frozen=True)
class PubRecPacket:
    mid: int
    reason_code: int = 0

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        body = bytearray(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5 and self.reason_code != 0:
            body.append(self.reason_code)
            body.append(0x00)
        return encode_frame(PacketType.PUBREC, 0, body)

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubRecPacket:
        mid, pos = unpack_u16(remaining, 0)
        reason = 0
        if protocol == MQTTProtocolVersion.MQTTv5 and pos < len(remaining):
            reason = remaining[pos]
        return cls(mid=mid, reason_code=reason)


@dataclass(slots=True, frozen=True)
class PubRelPacket:
    mid: int
    reason_code: int = 0

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        body = bytearray(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5 and self.reason_code != 0:
            body.append(self.reason_code)
            body.append(0x00)
        return encode_frame(PacketType.PUBREL, 0x02, body)

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubRelPacket:
        mid, pos = unpack_u16(remaining, 0)
        reason = 0
        if protocol == MQTTProtocolVersion.MQTTv5 and pos < len(remaining):
            reason = remaining[pos]
        return cls(mid=mid, reason_code=reason)


@dataclass(slots=True, frozen=True)
class PubCompPacket:
    mid: int
    reason_code: int = 0

    def encode(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> bytes:
        body = bytearray(pack_u16(self.mid))
        if protocol == MQTTProtocolVersion.MQTTv5 and self.reason_code != 0:
            body.append(self.reason_code)
            body.append(0x00)
        return encode_frame(PacketType.PUBCOMP, 0, body)

    @classmethod
    def decode(
        cls,
        remaining: bytes,
        protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    ) -> PubCompPacket:
        mid, pos = unpack_u16(remaining, 0)
        reason = 0
        if protocol == MQTTProtocolVersion.MQTTv5 and pos < len(remaining):
            reason = remaining[pos]
        return cls(mid=mid, reason_code=reason)


def encode_pingreq() -> bytes:
    return encode_frame(PacketType.PINGREQ, 0, b"")


def encode_pingresp() -> bytes:
    return encode_frame(PacketType.PINGRESP, 0, b"")


def encode_disconnect(
    reason_code: int = 0,
    protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
) -> bytes:
    if protocol == MQTTProtocolVersion.MQTTv5:
        body = bytes((reason_code, 0x00))
        return encode_frame(PacketType.DISCONNECT, 0, body)
    return encode_frame(PacketType.DISCONNECT, 0, b"")


# Silence unused import warning for vbi_len until property codec lands.
_ = vbi_len
