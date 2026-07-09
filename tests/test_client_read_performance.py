import struct

import pytest

import paho.mqtt.client as client
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties


class PartialRecvSocket:
    """Socket that exposes only the first `available` bytes; further recv raises BlockingIOError."""

    def __init__(self, data, available=0):
        self._data = bytes(data)
        self._pos = 0
        self.available = available
        self.calls = 0

    def recv(self, size):
        self.calls += 1
        if self._pos >= self.available:
            raise BlockingIOError()
        n = min(size, self.available - self._pos)
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def send(self, data):
        return len(data)

    def close(self):
        return None

    def fileno(self):
        return 1

    def setblocking(self, flag):
        return None


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


def _publish_packet(protocol, topic=b"t/a", payload=b"hi", qos=0, mid=1, properties=None):
    command = int(client.PUBLISH) | (qos << 1)
    variable = bytearray()
    variable.extend(struct.pack("!H", len(topic)))
    variable.extend(topic)
    if qos:
        variable.extend(struct.pack("!H", mid))
    if protocol == client.MQTTv5:
        if properties is None:
            variable.extend(b"\x00")
        else:
            variable.extend(properties.pack())
    remaining = len(variable) + len(payload)
    return bytes([command]) + _encode_varint(remaining) + bytes(variable) + payload


def _new_client(protocol=client.MQTTv311):
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2, protocol=protocol)
    mqttc.on_message = lambda mqttc, userdata, message: None
    return mqttc


def test_in_packet_state_is_reused_across_reads():
    mqttc = _new_client()
    packet = _publish_packet(client.MQTTv311)
    sock = PartialRecvSocket(packet * 2, available=len(packet) * 2)
    mqttc._sock = sock
    state = mqttc._in_packet

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert mqttc._in_packet is state
    assert state.command == 0
    assert state.remaining_count == 0
    assert len(state.packet) == 0

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert mqttc._in_packet is state


def test_partial_fixed_header_read_returns_again():
    mqttc = _new_client()
    packet = _publish_packet(client.MQTTv311)
    sock = PartialRecvSocket(packet, available=1)
    mqttc._sock = sock

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_AGAIN
    assert mqttc._in_packet.command == packet[0]
    assert mqttc._in_packet.have_remaining == 0

    sock.available = len(packet)
    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert mqttc._in_packet.command == 0


def test_partial_remaining_length_and_payload_reads():
    mqttc = _new_client()
    packet = _publish_packet(client.MQTTv311, payload=b"x" * 200)
    assert packet[1] & 0x80  # multi-byte remaining length
    messages = []
    mqttc.on_message = lambda mqttc, userdata, message: messages.append(message)
    sock = PartialRecvSocket(packet, available=2)
    mqttc._sock = sock

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_AGAIN
    assert mqttc._in_packet.command != 0
    assert mqttc._in_packet.have_remaining == 0
    assert mqttc._in_packet.remaining_count == 1

    sock.available = 8
    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_AGAIN
    assert mqttc._in_packet.have_remaining == 1
    assert mqttc._in_packet.to_process > 0

    sock.available = len(packet)
    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert len(messages) == 1
    assert messages[0].payload == b"x" * 200


def test_invalid_remaining_length_over_four_bytes():
    mqttc = _new_client()
    bad = bytes([int(client.PUBLISH), 0x80, 0x80, 0x80, 0x80, 0x01])
    mqttc._sock = PartialRecvSocket(bad, available=len(bad))

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_PROTOCOL


def test_handle_publish_v5_empty_properties_fast_path():
    mqttc = _new_client(protocol=client.MQTTv5)
    messages = []
    mqttc.on_message = lambda mqttc, userdata, message: messages.append(message)
    packet = _publish_packet(client.MQTTv5, topic=b"sensors/1", payload=b"{}", properties=None)
    mqttc._sock = PartialRecvSocket(packet, available=len(packet))

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert len(messages) == 1
    assert messages[0].payload == b"{}"
    assert messages[0].properties is not None
    assert messages[0].properties.isEmpty()


def test_handle_publish_v5_with_user_properties():
    mqttc = _new_client(protocol=client.MQTTv5)
    messages = []
    mqttc.on_message = lambda mqttc, userdata, message: messages.append(message)

    props = Properties(PacketTypes.PUBLISH)
    props.UserProperty = ("k", "v")
    packet = _publish_packet(client.MQTTv5, payload=b"p", properties=props)
    mqttc._sock = PartialRecvSocket(packet, available=len(packet))

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert messages[0].properties.UserProperty == [("k", "v")]


def test_handle_publish_qos1_mid_and_invalid_utf8_topic():
    mqttc = _new_client()
    messages = []
    mqttc.on_message = lambda mqttc, userdata, message: messages.append(message)
    packet = _publish_packet(client.MQTTv311, topic=b"\xff", payload=b"x", qos=1, mid=42)
    mqttc._sock = PartialRecvSocket(packet, available=len(packet))
    mqttc.manual_ack_set(True)

    assert mqttc._packet_read() == MQTTErrorCode.MQTT_ERR_SUCCESS
    assert messages[0].mid == 42
    assert messages[0]._topic == b"\xff"
    with pytest.raises(UnicodeDecodeError):
        _ = messages[0].topic


def test_in_packet_reset_clears_fields():
    mqttc = _new_client()
    state = mqttc._in_packet
    state.command = 0x30
    state.have_remaining = 1
    state.remaining_count = 3
    state.remaining_mult = 128
    state.remaining_length = 10
    state.packet.extend(b"abc")
    state.to_process = 4
    state.pos = 1

    state.reset()

    assert state.command == 0
    assert state.have_remaining == 0
    assert state.remaining_count == 0
    assert state.remaining_mult == 1
    assert state.remaining_length == 0
    assert len(state.packet) == 0
    assert state.to_process == 0
    assert state.pos == 0
    assert mqttc._in_packet is state
