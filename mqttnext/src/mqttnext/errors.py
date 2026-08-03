"""Exception hierarchy for mqttnext."""

from __future__ import annotations


class MQTTError(Exception):
    """Base error for mqttnext."""


class MalformedPacketError(MQTTError):
    """Wire data cannot be parsed as a valid MQTT packet."""


class ProtocolError(MQTTError):
    """Valid framing but illegal MQTT protocol usage."""


class PacketTooLargeError(ProtocolError):
    """Packet exceeds local or negotiated maximum size."""


class FlowControlError(MQTTError):
    """Outbound inflight window exhausted (raise mode)."""


class MessageDeliveryError(FlowControlError):
    """Application delivery could not keep up within the configured deadline."""


class NotConnectedError(MQTTError):
    """Operation requires an active connection."""


class MQTTTimeoutError(MQTTError):
    """Operation exceeded its deadline."""


class SessionDiscardedError(MQTTError):
    """Pending publish was discarded because a clean session replaced the old one."""
