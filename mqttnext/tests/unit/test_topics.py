"""Topic / filter validation tests."""

from __future__ import annotations

import pytest

from mqttnext.errors import MalformedPacketError, ProtocolError
from mqttnext.topics import (
    validate_publish_topic,
    validate_received_publish_topic,
    validate_subscribe_filter,
)


def test_publish_topic_rejects_wildcards() -> None:
    with pytest.raises(ProtocolError):
        validate_publish_topic("a/+/b")
    with pytest.raises(ProtocolError):
        validate_publish_topic("a/#")
    with pytest.raises(ProtocolError):
        validate_publish_topic("")


def test_publish_topic_allow_empty_for_alias() -> None:
    validate_publish_topic("", allow_empty=True)


def test_subscribe_filter_ok() -> None:
    validate_subscribe_filter("a/+/b")
    validate_subscribe_filter("a/#")
    validate_subscribe_filter("#")
    validate_subscribe_filter("+")
    validate_subscribe_filter("$share/group/a/+/b")


def test_subscribe_filter_bad() -> None:
    with pytest.raises(ProtocolError):
        validate_subscribe_filter("")
    with pytest.raises(ProtocolError):
        validate_subscribe_filter("a/#/b")
    with pytest.raises(ProtocolError):
        validate_subscribe_filter("a+")
    with pytest.raises(ProtocolError):
        validate_subscribe_filter("$share//topic")
    with pytest.raises(ProtocolError):
        validate_subscribe_filter("$share/g+/topic")
    with pytest.raises(ProtocolError):
        validate_subscribe_filter("$share/group")


def test_received_publish_wildcard_malformed() -> None:
    with pytest.raises(MalformedPacketError):
        validate_received_publish_topic("a/#")
