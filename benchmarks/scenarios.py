"""Brokerless benchmark scenarios."""

from __future__ import absolute_import

import collections
import logging
import struct

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.matcher import MQTTMatcher
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from fakes import FakeRecvSocket, FakeSendSocket, make_out_packet, packet_deque
from harness import Scenario


TOPIC = b"devices/device-0001/telemetry"
TOPIC_TEXT = TOPIC.decode("utf-8")
PAYLOAD_SMALL = b'{"temperature":21.5,"humidity":44}'
PACK_U16 = struct.Struct("!H")


def _encode_varint(value):
    encoded = bytearray()
    while True:
        byte = value % 128
        value //= 128
        if value:
            byte |= 0x80
        encoded.append(byte)
        if not value:
            return bytes(encoded)


def _pack_utf8(data):
    return PACK_U16.pack(len(data)) + data


def _publish_packet(protocol, payload, properties=None, qos=0, mid=1):
    command = int(mqtt.PUBLISH) | (qos << 1)
    variable_header = bytearray()
    variable_header.extend(_pack_utf8(TOPIC))
    if qos:
        variable_header.extend(PACK_U16.pack(mid))
    if protocol == mqtt.MQTTv5:
        if properties is None:
            variable_header.extend(b"\x00")
        else:
            variable_header.extend(properties.pack())
    remaining_length = len(variable_header) + len(payload)
    return bytes([command]) + _encode_varint(remaining_length) + bytes(variable_header) + payload


def _common_properties():
    props = Properties(PacketTypes.PUBLISH)
    props.PayloadFormatIndicator = 1
    props.ContentType = "application/json"
    props.TopicAlias = 1
    return props


def _user_properties():
    props = Properties(PacketTypes.PUBLISH)
    for index in range(8):
        props.UserProperty = ("key{}".format(index), "value{}".format(index))
    return props


PACKED_EMPTY_PROPERTIES = Properties(PacketTypes.PUBLISH).pack()
PACKED_COMMON_PROPERTIES = _common_properties().pack()
PACKED_USER_PROPERTIES = _user_properties().pack()
PUBLISH_V3_QOS0_SMALL = _publish_packet(mqtt.MQTTv311, PAYLOAD_SMALL)
PUBLISH_V5_QOS0_EMPTY_PROPS = _publish_packet(mqtt.MQTTv5, PAYLOAD_SMALL)
PUBLISH_V5_QOS0_USER_PROPS = _publish_packet(mqtt.MQTTv5, PAYLOAD_SMALL, _user_properties())


def _new_client(protocol=mqtt.MQTTv311):
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        protocol=protocol,
    )
    client.on_message = lambda client, userdata, message: None
    return client


def properties_pack_empty(iterations):
    props = Properties(PacketTypes.PUBLISH)
    for _ in range(iterations):
        props.pack()


def properties_unpack_empty(iterations):
    packed = PACKED_EMPTY_PROPERTIES
    for _ in range(iterations):
        props = Properties(PacketTypes.PUBLISH)
        props.unpack(packed)


def properties_pack_common(iterations):
    props = _common_properties()
    for _ in range(iterations):
        props.pack()


def properties_unpack_common(iterations):
    packed = PACKED_COMMON_PROPERTIES
    for _ in range(iterations):
        props = Properties(PacketTypes.PUBLISH)
        props.unpack(packed)


def properties_pack_user_properties(iterations):
    props = _user_properties()
    for _ in range(iterations):
        props.pack()


def properties_unpack_user_properties(iterations):
    packed = PACKED_USER_PROPERTIES
    for _ in range(iterations):
        props = Properties(PacketTypes.PUBLISH)
        props.unpack(packed)


def reasoncode_create_puback_success(iterations):
    for _ in range(iterations):
        ReasonCode(PacketTypes.PUBACK, identifier=0)


def _parse_publish(iterations, protocol, packet):
    client = _new_client(protocol)
    client._sock = FakeRecvSocket(packet * iterations)
    for _ in range(iterations):
        rc = client._packet_read()
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("packet read failed: {}".format(rc))


def publish_parse_v3_qos0_small(iterations):
    _parse_publish(iterations, mqtt.MQTTv311, PUBLISH_V3_QOS0_SMALL)


def publish_parse_v5_qos0_empty_props(iterations):
    _parse_publish(iterations, mqtt.MQTTv5, PUBLISH_V5_QOS0_EMPTY_PROPS)


def publish_parse_v5_qos0_user_props(iterations):
    _parse_publish(iterations, mqtt.MQTTv5, PUBLISH_V5_QOS0_USER_PROPS)


def publish_pack_qos0_v3_small(iterations):
    client = _new_client(mqtt.MQTTv311)
    client._sock = FakeSendSocket()
    for _ in range(iterations):
        info = client.publish(TOPIC_TEXT, PAYLOAD_SMALL, qos=0)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("publish failed: {}".format(info.rc))


def publish_pack_qos1_v3_small(iterations):
    client = _new_client(mqtt.MQTTv311)
    client._sock = FakeSendSocket()
    for mid in range(1, iterations + 1):
        rc = client._send_publish(mid, TOPIC, PAYLOAD_SMALL, qos=1)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("send publish failed: {}".format(rc))


def _publish_wire_packet(mid=1, qos=0):
    info = mqtt.MQTTMessageInfo(mid) if qos == 0 else None
    packet = bytearray()
    packet.append(int(mqtt.PUBLISH) | (qos << 1))
    remaining_length = 2 + len(TOPIC) + len(PAYLOAD_SMALL)
    if qos:
        remaining_length += 2
    packet.extend(_encode_varint(remaining_length))
    packet.extend(_pack_utf8(TOPIC))
    if qos:
        packet.extend(PACK_U16.pack(mid))
    packet.extend(PAYLOAD_SMALL)
    return make_out_packet(mqtt.PUBLISH, packet, mid=mid, qos=qos, info=info)


def _packet_write_drain(iterations, packets_per_iteration):
    template_packets = [_publish_wire_packet(mid=index + 1) for index in range(packets_per_iteration)]
    client = _new_client(mqtt.MQTTv311)
    client._sock = FakeSendSocket()
    for _ in range(iterations):
        packets = []
        for packet in template_packets:
            copied = dict(packet)
            copied["pos"] = 0
            copied["to_process"] = len(copied["packet"])
            if copied["info"] is not None:
                copied["info"] = mqtt.MQTTMessageInfo(copied["mid"])
            packets.append(copied)
        client._out_packet = packet_deque(packets)
        rc = client._packet_write()
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("packet write failed: {}".format(rc))


def packet_write_drain_100(iterations):
    _packet_write_drain(iterations, 100)


def packet_write_drain_10000(iterations):
    _packet_write_drain(iterations, 10000)


def matcher_many_filters(iterations):
    matcher = MQTTMatcher()
    for index in range(1000):
        matcher["devices/device-{}/telemetry".format(str(index).zfill(4))] = index
    matcher["devices/+/telemetry"] = "wildcard"
    matcher["devices/#"] = "all-devices"
    topic = TOPIC_TEXT
    for _ in range(iterations):
        tuple(matcher.iter_match(topic))


def logging_disabled(iterations):
    client = _new_client(mqtt.MQTTv311)
    client.logger = logging.getLogger("paho.benchmark.disabled")
    client.logger.setLevel(logging.WARNING)
    for _ in range(iterations):
        client._easy_log(mqtt.MQTT_LOG_DEBUG, "Benchmark log message %d", 1)


SCENARIOS = [
    Scenario("properties_pack_empty", "mqttv5-codec", "property-set", 5000, properties_pack_empty),
    Scenario("properties_unpack_empty", "mqttv5-codec", "property-set", 5000, properties_unpack_empty),
    Scenario("properties_pack_common", "mqttv5-codec", "property-set", 3000, properties_pack_common),
    Scenario("properties_unpack_common", "mqttv5-codec", "property-set", 3000, properties_unpack_common),
    Scenario("properties_pack_user_properties", "mqttv5-codec", "property-set", 1000, properties_pack_user_properties),
    Scenario("properties_unpack_user_properties", "mqttv5-codec", "property-set", 1000, properties_unpack_user_properties),
    Scenario("reasoncode_create_puback_success", "mqttv5-codec", "reason-code", 5000, reasoncode_create_puback_success),
    Scenario("publish_parse_v3_qos0_small", "packet-read", "message", 5000, publish_parse_v3_qos0_small),
    Scenario("publish_parse_v5_qos0_empty_props", "packet-read", "message", 5000, publish_parse_v5_qos0_empty_props),
    Scenario("publish_parse_v5_qos0_user_props", "packet-read", "message", 1000, publish_parse_v5_qos0_user_props),
    Scenario("publish_pack_qos0_v3_small", "packet-write", "message", 5000, publish_pack_qos0_v3_small),
    Scenario("publish_pack_qos1_v3_small", "packet-write", "message", 5000, publish_pack_qos1_v3_small),
    Scenario("packet_write_drain_100", "packet-write", "packet", 100, packet_write_drain_100, operations_per_iteration=100),
    Scenario("packet_write_drain_10000", "packet-write", "packet", 1, packet_write_drain_10000, operations_per_iteration=10000),
    Scenario("matcher_many_filters", "supporting", "match", 2000, matcher_many_filters),
    Scenario("logging_disabled", "supporting", "log-call", 20000, logging_disabled),
]
