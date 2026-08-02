"""SQLite-backed inflight persistence (optional, phase 3)."""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator

from mqttnext.enums import InboundQoSState, OutboundQoSState, QoS
from mqttnext.types import InboundMessage, OutboundMessage, Properties


def _encode_payload(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode_payload(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _json_sanitize(value: Any) -> Any:
    """Convert property values to JSON-safe forms (bytes / tuples)."""
    if isinstance(value, bytes):
        return {"__mqttnext_bytes__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return {"__mqttnext_tuple__": [_json_sanitize(v) for v in value]}
    if isinstance(value, list):
        return [_json_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_sanitize(v) for k, v in value.items()}
    return value


def _json_revive(value: Any) -> Any:
    if isinstance(value, dict):
        if "__mqttnext_bytes__" in value and len(value) == 1:
            return base64.b64decode(value["__mqttnext_bytes__"].encode("ascii"))
        if "__mqttnext_tuple__" in value and len(value) == 1:
            return tuple(_json_revive(v) for v in value["__mqttnext_tuple__"])
        return {k: _json_revive(v) for k, v in value.items()}
    if isinstance(value, list):
        # user_property pairs often round-trip as [[k,v], ...] — restore tuples.
        revived = [_json_revive(v) for v in value]
        if (
            revived
            and all(isinstance(item, list) and len(item) == 2 for item in revived)
            and all(isinstance(item[0], str) for item in revived)
        ):
            return [tuple(item) for item in revived]
        return revived
    return value


def _props_to_json(props: Properties | None) -> str | None:
    if props is None or not props.values:
        return None
    return json.dumps(_json_sanitize(props.values), separators=(",", ":"))


def _props_from_json(raw: str | None) -> Properties | None:
    if not raw:
        return None
    values = _json_revive(json.loads(raw))
    if not isinstance(values, dict):
        raise ValueError("Invalid properties JSON payload")
    return Properties(values=values)


def _row_to_out(row: sqlite3.Row) -> OutboundMessage:
    return OutboundMessage(
        mid=int(row["mid"]),
        topic=str(row["topic"]),
        payload=_decode_payload(row["payload"]),
        qos=QoS(int(row["qos"])),
        retain=bool(row["retain"]),
        state=OutboundQoSState(int(row["state"])),
        dup=bool(row["dup"]),
        properties=_props_from_json(row["properties"]),
    )


def _row_to_in(row: sqlite3.Row) -> InboundMessage:
    return InboundMessage(
        mid=int(row["mid"]),
        topic=str(row["topic"]),
        payload=_decode_payload(row["payload"]),
        qos=QoS(int(row["qos"])),
        retain=bool(row["retain"]),
        state=InboundQoSState(int(row["state"])),
        delivered=bool(row["delivered"]),
        properties=_props_from_json(row["properties"]),
        user_acked=bool(row["user_acked"]),
    )


class SqliteInflightStore:
    """Persist inflight / queued messages across process restarts.

    Encoded wire bytes are not stored; they are rebuilt on session replay.
    MQTT 5 property bags (including binary correlation_data and user_property
    pairs) round-trip via a tagged JSON encoding.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS outbound (
                mid INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                qos INTEGER NOT NULL,
                retain INTEGER NOT NULL,
                state INTEGER NOT NULL,
                dup INTEGER NOT NULL,
                properties TEXT,
                extra INTEGER NOT NULL DEFAULT 0,
                seq INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inbound (
                mid INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                qos INTEGER NOT NULL,
                retain INTEGER NOT NULL,
                state INTEGER NOT NULL,
                delivered INTEGER NOT NULL,
                properties TEXT,
                user_acked INTEGER NOT NULL,
                seq INTEGER NOT NULL
            );
            """
        )
        self._conn.commit()
        self._out_seq = self._max_seq("outbound")
        self._in_seq = self._max_seq("inbound")

    def _max_seq(self, table: str) -> int:
        row = self._conn.execute(f"SELECT COALESCE(MAX(seq), 0) FROM {table}").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()

    def put_out(self, msg: OutboundMessage) -> None:
        self._out_seq += 1
        self._conn.execute(
            """
            INSERT INTO outbound(mid, topic, payload, qos, retain, state, dup, properties, extra, seq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(mid) DO UPDATE SET
                topic=excluded.topic, payload=excluded.payload, qos=excluded.qos,
                retain=excluded.retain, state=excluded.state, dup=excluded.dup,
                properties=excluded.properties
            """,
            (
                msg.mid,
                msg.topic,
                _encode_payload(msg.payload),
                int(msg.qos),
                int(msg.retain),
                int(msg.state),
                int(msg.dup),
                _props_to_json(msg.properties),
                self._out_seq,
            ),
        )
        self._conn.commit()

    def get_out(self, mid: int) -> OutboundMessage | None:
        row = self._conn.execute("SELECT * FROM outbound WHERE mid=?", (mid,)).fetchone()
        return _row_to_out(row) if row else None

    def pop_out(self, mid: int) -> OutboundMessage | None:
        row = self._conn.execute("SELECT * FROM outbound WHERE mid=?", (mid,)).fetchone()
        if row is None:
            return None
        self._conn.execute("DELETE FROM outbound WHERE mid=?", (mid,))
        self._conn.commit()
        return _row_to_out(row)

    def update_out(self, msg: OutboundMessage) -> None:
        cur = self._conn.execute(
            """
            UPDATE outbound SET topic=?, payload=?, qos=?, retain=?, state=?, dup=?, properties=?
            WHERE mid=?
            """,
            (
                msg.topic,
                _encode_payload(msg.payload),
                int(msg.qos),
                int(msg.retain),
                int(msg.state),
                int(msg.dup),
                _props_to_json(msg.properties),
                msg.mid,
            ),
        )
        if cur.rowcount == 0:
            raise KeyError(msg.mid)
        self._conn.commit()

    def out_items(self) -> Iterator[OutboundMessage]:
        rows = self._conn.execute("SELECT * FROM outbound ORDER BY seq").fetchall()
        for row in rows:
            yield _row_to_out(row)

    def clear_out(self) -> None:
        self._conn.execute("DELETE FROM outbound")
        self._conn.commit()

    def put_in(self, msg: InboundMessage) -> None:
        self._in_seq += 1
        self._conn.execute(
            """
            INSERT INTO inbound(
                mid, topic, payload, qos, retain, state, delivered, properties, user_acked, seq
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mid) DO UPDATE SET
                topic=excluded.topic, payload=excluded.payload, qos=excluded.qos,
                retain=excluded.retain, state=excluded.state, delivered=excluded.delivered,
                properties=excluded.properties, user_acked=excluded.user_acked
            """,
            (
                msg.mid,
                msg.topic,
                _encode_payload(msg.payload),
                int(msg.qos),
                int(msg.retain),
                int(msg.state),
                int(msg.delivered),
                _props_to_json(msg.properties),
                int(msg.user_acked),
                self._in_seq,
            ),
        )
        self._conn.commit()

    def get_in(self, mid: int) -> InboundMessage | None:
        row = self._conn.execute("SELECT * FROM inbound WHERE mid=?", (mid,)).fetchone()
        return _row_to_in(row) if row else None

    def pop_in(self, mid: int) -> InboundMessage | None:
        row = self._conn.execute("SELECT * FROM inbound WHERE mid=?", (mid,)).fetchone()
        if row is None:
            return None
        self._conn.execute("DELETE FROM inbound WHERE mid=?", (mid,))
        self._conn.commit()
        return _row_to_in(row)

    def update_in(self, msg: InboundMessage) -> None:
        cur = self._conn.execute(
            """
            UPDATE inbound SET topic=?, payload=?, qos=?, retain=?, state=?,
                delivered=?, properties=?, user_acked=?
            WHERE mid=?
            """,
            (
                msg.topic,
                _encode_payload(msg.payload),
                int(msg.qos),
                int(msg.retain),
                int(msg.state),
                int(msg.delivered),
                _props_to_json(msg.properties),
                int(msg.user_acked),
                msg.mid,
            ),
        )
        if cur.rowcount == 0:
            raise KeyError(msg.mid)
        self._conn.commit()

    def in_items(self) -> Iterator[InboundMessage]:
        rows = self._conn.execute("SELECT * FROM inbound ORDER BY seq").fetchall()
        for row in rows:
            yield _row_to_in(row)

    def clear_in(self) -> None:
        self._conn.execute("DELETE FROM inbound")
        self._conn.commit()
