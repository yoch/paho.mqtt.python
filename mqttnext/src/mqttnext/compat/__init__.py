"""Compatibilité Paho — phase 3 (squelette VERSION2)."""

from mqttnext.compat.paho import (
    CallbackAPIVersion,
    Client,
    MQTTMessage,
    MQTTMessageInfo,
)

__all__ = [
    "CallbackAPIVersion",
    "Client",
    "MQTTMessage",
    "MQTTMessageInfo",
]
