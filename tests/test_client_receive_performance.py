import paho.mqtt.client as client
from paho.mqtt.enums import CallbackAPIVersion


def test_incoming_message_info_is_created_lazily():
    message = client.MQTTMessage(create_info=False)

    assert message._info is None

    info = message.info

    assert isinstance(info, client.MQTTMessageInfo)
    assert message.info is info


def test_filtered_callback_count_tracks_add_replace_remove():
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)

    def callback_one(mqttc, userdata, message):
        pass

    def callback_two(mqttc, userdata, message):
        pass

    assert mqttc._on_message_filtered_count == 0

    mqttc.message_callback_add("sensors/+", callback_one)
    assert mqttc._on_message_filtered_count == 1

    mqttc.message_callback_add("sensors/+", callback_two)
    assert mqttc._on_message_filtered_count == 1

    mqttc.message_callback_add("devices/#", callback_one)
    assert mqttc._on_message_filtered_count == 2

    mqttc.message_callback_remove("missing/#")
    assert mqttc._on_message_filtered_count == 2

    mqttc.message_callback_remove("sensors/+")
    assert mqttc._on_message_filtered_count == 1

    mqttc.message_callback_remove("devices/#")
    assert mqttc._on_message_filtered_count == 0


def test_unfiltered_on_message_does_not_require_valid_utf8_topic():
    mqttc = client.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    messages = []
    mqttc.on_message = lambda mqttc, userdata, message: messages.append(message)

    message = client.MQTTMessage(create_info=False)
    message.topic = b"\xff"

    mqttc._handle_on_message(message)

    assert messages == [message]
