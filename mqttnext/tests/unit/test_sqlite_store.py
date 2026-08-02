"""SqliteInflightStore round-trip tests."""

from __future__ import annotations

from pathlib import Path

from mqttnext.enums import InboundQoSState, OutboundQoSState, QoS
from mqttnext.persistence.sqlite import SqliteInflightStore
from mqttnext.types import InboundMessage, OutboundMessage


def test_sqlite_outbound_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "inflight.db"
    store = SqliteInflightStore(path)
    msg = OutboundMessage(
        mid=7,
        topic="a/b",
        payload=b"payload",
        qos=QoS.AT_LEAST_ONCE,
        retain=False,
        state=OutboundQoSState.WAIT_PUBACK,
        dup=False,
    )
    store.put_out(msg)
    store.close()

    store2 = SqliteInflightStore(path)
    got = store2.get_out(7)
    assert got is not None
    assert got.topic == "a/b"
    assert got.payload == b"payload"
    assert got.state is OutboundQoSState.WAIT_PUBACK
    items = list(store2.out_items())
    assert len(items) == 1
    popped = store2.pop_out(7)
    assert popped is not None
    assert store2.get_out(7) is None
    store2.close()


def test_sqlite_properties_binary_and_user_property(tmp_path: Path) -> None:
    from mqttnext.types import Properties

    path = tmp_path / "props.db"
    store = SqliteInflightStore(path)
    props = Properties()
    props.set("correlation_data", b"\x00\xffbinary")
    props.set("content_type", "application/octet-stream")
    props.add_user_property("k", "v")
    props.add_user_property("k2", "v2")
    props.values["subscription_identifier"] = [11, 22]
    msg = OutboundMessage(
        mid=9,
        topic="p",
        payload=b"x",
        qos=QoS.EXACTLY_ONCE,
        retain=False,
        state=OutboundQoSState.WAIT_PUBREC,
        properties=props,
    )
    store.put_out(msg)
    store.close()

    store2 = SqliteInflightStore(path)
    got = store2.get_out(9)
    assert got is not None
    assert got.properties is not None
    assert got.properties.get("correlation_data") == b"\x00\xffbinary"
    assert got.properties.get("content_type") == "application/octet-stream"
    assert got.properties.get("user_property") == [("k", "v"), ("k2", "v2")]
    assert got.properties.get("subscription_identifier") == [11, 22]
    store2.close()


def test_sqlite_inbound_manual_ack_flag(tmp_path: Path) -> None:
    path = tmp_path / "in.db"
    store = SqliteInflightStore(path)
    msg = InboundMessage(
        mid=3,
        topic="t",
        payload=b"x",
        qos=QoS.EXACTLY_ONCE,
        retain=False,
        state=InboundQoSState.WAIT_PUBREL,
        delivered=True,
        user_acked=True,
    )
    store.put_in(msg)
    got = store.get_in(3)
    assert got is not None
    assert got.user_acked is True
    store.clear_in()
    assert store.get_in(3) is None
    store.close()
