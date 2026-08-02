from __future__ import annotations

from pathlib import Path


MEMORY = Path("mqttnext/src/mqttnext/persistence/memory.py")
SQLITE = Path("mqttnext/src/mqttnext/persistence/sqlite.py")
ENGINE = Path("mqttnext/src/mqttnext/protocol/engine.py")
CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
TEST = Path("mqttnext/tests/unit/test_inbound_recovery.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


memory = MEMORY.read_text()
memory = replace_once(
    memory,
    """    def update_in(self, msg: InboundMessage) -> None: ...
    def clear_in(self) -> None: ...
""",
    """    def update_in(self, msg: InboundMessage) -> None: ...
    def in_items(self) -> Iterator[InboundMessage]: ...
    def clear_in(self) -> None: ...
""",
    "store protocol in_items",
)
memory = replace_once(
    memory,
    """    def update_in(self, msg: InboundMessage) -> None:
        if msg.mid not in self._in:
            raise KeyError(msg.mid)
        self._in[msg.mid] = msg

    def clear_in(self) -> None:
""",
    """    def update_in(self, msg: InboundMessage) -> None:
        if msg.mid not in self._in:
            raise KeyError(msg.mid)
        self._in[msg.mid] = msg

    def in_items(self) -> Iterator[InboundMessage]:
        return iter(self._in.values())

    def clear_in(self) -> None:
""",
    "memory in_items",
)
MEMORY.write_text(memory)

sqlite = SQLITE.read_text()
sqlite = replace_once(
    sqlite,
    """    def clear_in(self) -> None:
        self._conn.execute("DELETE FROM inbound")
        self._conn.commit()
""",
    """    def in_items(self) -> Iterator[InboundMessage]:
        rows = self._conn.execute("SELECT * FROM inbound ORDER BY seq").fetchall()
        for row in rows:
            yield _row_to_in(row)

    def clear_in(self) -> None:
        self._conn.execute("DELETE FROM inbound")
        self._conn.commit()
""",
    "sqlite in_items",
)
SQLITE.write_text(sqlite)

engine = ENGINE.read_text()
engine = replace_once(
    engine,
    """        # Server→client QoS>0 not yet fully acknowledged (Receive Maximum).
        self._inbound_inflight = 0
        self._handlers = {
""",
    """        # Server→client QoS>0 not yet fully acknowledged (Receive Maximum).
        self._inbound_inflight = 0
        self._recovered_inbound_mids = {
            msg.mid for msg in self.store.in_items()
        }
        self._handlers = {
""",
    "recovered inbound tracking",
)
engine = replace_once(
    engine,
    """            self.store.clear_in()
            self.flow.reset()
""",
    """            self.store.clear_in()
            self._recovered_inbound_mids.clear()
            self._inbound_inflight = 0
            self.flow.reset()
""",
    "clean session inbound reset",
)
engine = replace_once(
    engine,
    """        self._fail_queued_violating_negotiation()
        self._emit(EffectKind.CONNACK, connack)
        self._drain_queue()
""",
    """        self._fail_queued_violating_negotiation()
        self._emit(EffectKind.CONNACK, connack)
        if connack.session_present:
            self._replay_inbound_session()
        self._drain_queue()
""",
    "inbound session replay call",
)
engine = replace_once(
    engine,
    """        if packet.qos == QoS.AT_LEAST_ONCE and self.config.manual_ack:
            # Redelivery (DUP) of an already-tracked QoS1 must not re-acquire a
            # Receive Maximum slot nor re-emit the message.
            existing = self.store.get_in(packet.mid)
            if existing is not None and existing.state is InboundQoSState.WAIT_PUBACK:
                return
""",
    """        if packet.qos == QoS.AT_LEAST_ONCE and self.config.manual_ack:
            # A duplicate QoS1 publish reuses the existing Receive Maximum slot,
            # but is surfaced again so an application can complete manual ACK
            # after a reconnect or callback cancellation.
            existing = self.store.get_in(packet.mid)
            if existing is not None and existing.state is InboundQoSState.WAIT_PUBACK:
                self._emit_inbound_message(existing, dup=True)
                return
""",
    "manual qos1 duplicate delivery",
)
engine = replace_once(
    engine,
    """                        state=InboundQoSState.WAIT_PUBACK,
                        delivered=True,
                        properties=packet.properties,
""",
    """                        state=InboundQoSState.WAIT_PUBACK,
                        delivered=False,
                        properties=packet.properties,
""",
    "manual qos1 delivery state",
)
engine = replace_once(
    engine,
    """            state=InboundQoSState.WAIT_PUBREL,
            delivered=True,
            properties=packet.properties,
""",
    """            state=InboundQoSState.WAIT_PUBREL,
            delivered=False,
            properties=packet.properties,
""",
    "qos2 delivery state",
)
engine = replace_once(
    engine,
    """    def _on_puback(self, raw: RawPacket) -> None:
""",
    """    def mark_inbound_delivered(self, mid: int) -> None:
        inbound = self.store.get_in(mid)
        if inbound is None or inbound.delivered:
            return
        inbound.delivered = True
        self.store.update_in(inbound)

    def _emit_inbound_message(self, inbound: InboundMessage, *, dup: bool) -> None:
        self._emit(
            EffectKind.MESSAGE,
            Message(
                topic=inbound.topic,
                payload=inbound.payload,
                qos=inbound.qos,
                retain=inbound.retain,
                dup=dup,
                mid=inbound.mid,
                properties=inbound.properties,
            ),
        )

    def _replay_inbound_session(self) -> None:
        inbound_items = list(self.store.in_items())
        self._inbound_inflight = len(inbound_items)
        recovered = self._recovered_inbound_mids
        for inbound in inbound_items:
            should_redeliver = not inbound.delivered
            if inbound.mid in recovered and self.config.manual_ack:
                if inbound.state in (
                    InboundQoSState.WAIT_PUBACK,
                    InboundQoSState.WAIT_USER_ACK,
                ):
                    should_redeliver = True
                elif (
                    inbound.state is InboundQoSState.WAIT_PUBREL
                    and not inbound.user_acked
                ):
                    should_redeliver = True
            if should_redeliver:
                self._emit_inbound_message(inbound, dup=True)
        recovered.clear()

    def _on_puback(self, raw: RawPacket) -> None:
""",
    "inbound recovery helpers",
)
ENGINE.write_text(engine)

client = CLIENT.read_text()
client = replace_once(
    client,
    """            if callback_delivery:
                assert self.on_message is not None
                self._spawn_callback(self.on_message, msg)
""",
    """            if callback_delivery:
                assert self.on_message is not None
                self._spawn_callback(self.on_message, msg)
            if msg.mid is not None:
                async with self._engine_lock:
                    self._engine.mark_inbound_delivered(msg.mid)
""",
    "mark inbound delivered",
)
CLIENT.write_text(client)

TEST.write_text(
    '''"""Persistent inbound QoS recovery and receive-window accounting."""

from __future__ import annotations

import asyncio

from mqttnext.api.async_client import AsyncClient
from mqttnext.enums import (
    ConnectionState,
    InboundQoSState,
    MQTTProtocolVersion,
    PacketType,
    QoS,
)
from mqttnext.persistence.memory import MemoryInflightStore
from mqttnext.persistence.sqlite import SqliteInflightStore
from mqttnext.protocol.engine import EffectKind, EngineConfig, EngineEffect, ProtocolEngine
from mqttnext.types import InboundMessage, Message
from mqttnext.codec.buffer import RawPacket


def _inbound(mid: int, *, state=InboundQoSState.WAIT_PUBREL, delivered=True, user_acked=False):
    return InboundMessage(
        mid=mid,
        topic=f"recover/{mid}",
        payload=str(mid).encode(),
        qos=QoS.EXACTLY_ONCE if state is not InboundQoSState.WAIT_PUBACK else QoS.AT_LEAST_ONCE,
        retain=False,
        state=state,
        delivered=delivered,
        user_acked=user_acked,
    )


def _resume(engine: ProtocolEngine) -> list:
    engine.begin_connect()
    engine.take_effects()
    body = b"\\x01\\x00" + (
        b"\\x00" if engine.config.protocol == MQTTProtocolVersion.MQTTv5 else b""
    )
    engine.handle_raw(RawPacket(PacketType.CONNACK, 0, body))
    return engine.take_effects()


def test_memory_store_iterates_inbound_in_insertion_order() -> None:
    store = MemoryInflightStore()
    store.put_in(_inbound(3))
    store.put_in(_inbound(1))
    assert [message.mid for message in store.in_items()] == [3, 1]


def test_sqlite_store_iterates_inbound_in_insertion_order(tmp_path) -> None:
    store = SqliteInflightStore(tmp_path / "inflight.sqlite")
    try:
        store.put_in(_inbound(4))
        store.put_in(_inbound(2))
        assert [message.mid for message in store.in_items()] == [4, 2]
    finally:
        store.close()


def test_session_resume_restores_receive_window_count() -> None:
    store = MemoryInflightStore()
    store.put_in(_inbound(1))
    store.put_in(_inbound(2))
    engine = ProtocolEngine(
        EngineConfig(clean_start=False, local_receive_maximum=2),
        store=store,
    )

    _resume(engine)

    assert engine.state is ConnectionState.CONNECTED
    assert engine._inbound_inflight == 2


def test_undelivered_qos2_is_replayed_once_after_restart() -> None:
    store = MemoryInflightStore()
    store.put_in(_inbound(7, delivered=False))
    engine = ProtocolEngine(EngineConfig(clean_start=False), store=store)

    effects = _resume(engine)
    messages = [effect.data for effect in effects if effect.kind is EffectKind.MESSAGE]

    assert len(messages) == 1
    assert messages[0].mid == 7
    assert messages[0].dup is True
    assert engine._inbound_inflight == 1
    assert engine._recovered_inbound_mids == set()


def test_recovered_manual_ack_is_redelivered_even_if_previously_delivered() -> None:
    store = MemoryInflightStore()
    store.put_in(
        _inbound(
            8,
            state=InboundQoSState.WAIT_USER_ACK,
            delivered=True,
        )
    )
    engine = ProtocolEngine(
        EngineConfig(clean_start=False, manual_ack=True),
        store=store,
    )

    effects = _resume(engine)
    messages = [effect.data for effect in effects if effect.kind is EffectKind.MESSAGE]

    assert [message.mid for message in messages] == [8]
    assert messages[0].dup is True


async def test_client_marks_persisted_message_delivered_after_api_delivery() -> None:
    store = MemoryInflightStore()
    store.put_in(_inbound(9, delivered=False))
    client = AsyncClient(
        client_id="mark-delivered",
        store=store,
        message_delivery="iterator",
    )
    message = Message(
        topic="recover/9",
        payload=b"9",
        qos=QoS.EXACTLY_ONCE,
        mid=9,
        dup=True,
    )

    await client._apply_effect(
        EngineEffect(EffectKind.MESSAGE, message),
        nowait=False,
    )

    persisted = store.get_in(9)
    assert persisted is not None and persisted.delivered is True
    queued = client._messages.get_nowait()
    assert isinstance(queued, Message) and queued.mid == 9
'''
)
