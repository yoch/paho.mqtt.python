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
