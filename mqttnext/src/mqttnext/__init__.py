"""mqttnext — async-native MQTT client (work-in-progress reference implementation).

Designed from scratch using lessons from Eclipse Paho MQTT Python performance
work and the gmqtt asyncio architecture, without inheriting either codebase's
protocol-engine debt.
"""

from __future__ import annotations

from mqttnext.enums import MQTTProtocolVersion, PacketType, QoS
from mqttnext.errors import MQTTError, MalformedPacketError, ProtocolError

__all__ = [
    "MQTTError",
    "MQTTProtocolVersion",
    "MalformedPacketError",
    "PacketType",
    "ProtocolError",
    "QoS",
    "__version__",
]

__version__ = "0.0.1.dev0"
