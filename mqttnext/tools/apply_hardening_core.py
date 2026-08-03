from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one marker, found {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1))


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).lstrip())


def patch_async_client() -> None:
    path = "src/mqttnext/api/async_client.py"

    replace_once(
        path,
        """    MalformedPacketError,\n    PacketTooLargeError,\n""",
        """    MalformedPacketError,\n    MessageDeliveryError,\n    PacketTooLargeError,\n""",
    )

    replace_once(
        path,
        '''MessageDelivery = Literal["auto", "iterator", "callback", "both"]

_MESSAGE_SENTINEL = object()


class _MessageStream(asyncio.Queue[Message | object]):
    """Bounded queue whose terminal sentinel never evicts a real message.

    The sentinel is the only wake-up ``messages()`` gets when the stream ends
    while the queue is full; making room by dropping a queued message would
    silently lose user data (audit P1.7). Uses the same ``_put`` extension
    hook ``asyncio.Queue`` exposes to its own stdlib subclasses.
    """

    def put_sentinel(self, item: object) -> None:
        # asyncio.Queue extension hooks (stable since 3.8, used the same way by
        # stdlib subclasses); covered by test_full_message_queue_close_loses_nothing.
        self._put(item)
        self._wakeup_next(self._getters)  # type: ignore[attr-defined]


class AsyncClient:
''',
        '''MessageDelivery = Literal["auto", "iterator", "callback", "both"]
CallbackJob = tuple[Callable[..., Any], tuple[Any, ...]]


class AsyncClient:
''',
    )

    replace_once(
        path,
        """        max_pending_messages: int = 65_536,\n        message_delivery: MessageDelivery = \"auto\",\n""",
        """        max_pending_messages: int = 65_536,\n        max_pending_callbacks: int = 1_024,\n        delivery_timeout: float = 1.0,\n        callback_shutdown_timeout: float = 5.0,\n        message_delivery: MessageDelivery = \"auto\",\n""",
    )

    replace_once(
        path,
        """        if max_pending_messages <= 0:\n            raise ValueError(\"max_pending_messages must be greater than 0\")\n        if max_outbound_messages <= 0:\n""",
        """        if max_pending_messages <= 0:\n            raise ValueError(\"max_pending_messages must be greater than 0\")\n        if max_pending_callbacks <= 0:\n            raise ValueError(\"max_pending_callbacks must be greater than 0\")\n        if delivery_timeout <= 0:\n            raise ValueError(\"delivery_timeout must be greater than 0\")\n        if callback_shutdown_timeout <= 0:\n            raise ValueError(\"callback_shutdown_timeout must be greater than 0\")\n        if max_outbound_messages <= 0:\n""",
    )

    replace_once(
        path,
        """        self._effect_flush_lock = asyncio.Lock()\n        self._pending_effects: deque[EngineEffect] = deque()\n        self._callback_tasks: set[asyncio.Task[Any]] = set()\n        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()\n""",
        """        self._effect_flush_lock = asyncio.Lock()\n        self._pending_effects: deque[EngineEffect] = deque()\n        self._callback_queue: asyncio.Queue[CallbackJob] = asyncio.Queue(\n            maxsize=max_pending_callbacks\n        )\n        self._callback_worker_task: asyncio.Task[None] | None = None\n        self._delivery_timeout = delivery_timeout\n        self._callback_shutdown_timeout = callback_shutdown_timeout\n        self._outbound: asyncio.Queue[WriteItem] = asyncio.Queue()\n""",
    )

    replace_once(
        path,
        """        self._messages = _MessageStream(maxsize=self._max_pending_messages)\n        self._closed = asyncio.Event()\n""",
        """        self._messages: asyncio.Queue[Message] = asyncio.Queue(\n            maxsize=self._max_pending_messages\n        )\n        self._message_ready = asyncio.Event()\n        self._closed = asyncio.Event()\n""",
    )

    replace_once(
        path,
        """        if self._engine.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):\n            raise ProtocolError(\"Already connected or connecting\")\n        try:\n""",
        """        if self._engine.state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):\n            raise ProtocolError(\"Already connected or connecting\")\n        # Wire effects belong to a transport epoch. QoS 1/2 replay is rebuilt\n        # from the engine/store after CONNACK; carrying old bytes into a new\n        # transport can publish a packet the engine has already failed.\n        self._discard_connection_sends()\n        try:\n""",
    )

    replace_once(
        path,
        """    async def messages(self) -> AsyncIterator[Message]:\n        while True:\n            item = await self._messages.get()\n            if item is _MESSAGE_SENTINEL:\n                return\n            yield item  # type: ignore[misc]\n""",
        """    async def messages(self) -> AsyncIterator[Message]:\n        # Fast-path get_nowait avoids allocating two tasks per delivered\n        # message. The event is only a wake-up signal; the queue remains the\n        # source of truth and is drained before the stream terminates.\n        while True:\n            try:\n                yield self._messages.get_nowait()\n                continue\n            except asyncio.QueueEmpty:\n                if self._closed.is_set():\n                    return\n            self._message_ready.clear()\n            if not self._messages.empty() or self._closed.is_set():\n                continue\n            await self._message_ready.wait()\n""",
    )

    replace_once(
        path,
        """                handled = 0\n                async with self._engine_lock:\n                    while True:\n                        n = self._decoder.process_packets(\n                            self._engine.handle_raw, limit=256\n                        )\n                        if n == 0:\n                            break\n                        handled += n\n                    if handled:\n                        self._collect_effects_locked()\n""",
        """                handled = 0\n                async with self._engine_lock:\n                    # Commit protocol state before any generated ACK/replay\n                    # bytes are released to the writer.\n                    with self._engine.store.batch():\n                        while True:\n                            n = self._decoder.process_packets(\n                                self._engine.handle_raw, limit=256\n                            )\n                            if n == 0:\n                                break\n                            handled += n\n                    if handled:\n                        self._collect_effects_locked()\n""",
    )

    replace_once(
        path,
        """            self._closed.set()\n            if not will_reconnect:\n                # Never evict a queued message to make room (audit P1.7).\n                self._messages.put_sentinel(_MESSAGE_SENTINEL)\n            try:\n                await self._invoke(self.on_disconnect, self._disconnect_exc)\n            except Exception:\n                pass\n            if will_reconnect and (\n""",
        """            self._closed.set()\n            self._message_ready.set()\n            try:\n                await self._invoke(self.on_disconnect, self._disconnect_exc)\n            except Exception as exc:\n                self._report_callback_error(self.on_disconnect, exc)\n            if not will_reconnect:\n                await self._shutdown_callback_worker(drain=True)\n            if will_reconnect and (\n""",
    )

    replace_once(
        path,
        """        return (\n            not self._intentional_disconnect\n            and self._reconnect.enabled\n""",
        """        return (\n            not isinstance(self._disconnect_exc, MessageDeliveryError)\n            and not self._intentional_disconnect\n            and self._reconnect.enabled\n""",
    )

    replace_once(
        path,
        """            if self.on_connect is not None:\n                self._spawn_callback(self.on_connect, connack)\n""",
        """            if self.on_connect is not None:\n                await self._enqueue_callback(self.on_connect, connack)\n""",
    )

    replace_once(
        path,
        """            if iterator_delivery:\n                await self._messages.put(msg)\n            if callback_delivery:\n                assert self.on_message is not None\n                self._spawn_callback(self.on_message, msg)\n""",
        """            if iterator_delivery:\n                await self._put_message(msg)\n            if callback_delivery:\n                assert self.on_message is not None\n                await self._enqueue_callback(self.on_message, msg)\n""",
    )

    replace_once(
        path,
        """    def _reset_message_stream(self) -> None:\n        if self._closed.is_set():\n            self._messages = _MessageStream(maxsize=self._max_pending_messages)\n            self._closed.clear()\n\n    def _spawn_callback(self, callback: Callable[..., Any], *args: Any) -> None:\n        task = asyncio.create_task(self._invoke(callback, *args))\n        self._callback_tasks.add(task)\n        task.add_done_callback(self._callback_done)\n\n    def _callback_done(self, task: asyncio.Task[Any]) -> None:\n        self._callback_tasks.discard(task)\n        try:\n            task.result()\n        except (asyncio.CancelledError, Exception):\n            pass\n""",
        """    def _reset_message_stream(self) -> None:\n        if self._closed.is_set():\n            self._messages = asyncio.Queue(maxsize=self._max_pending_messages)\n            self._message_ready = asyncio.Event()\n            self._closed.clear()\n\n    async def _put_message(self, message: Message) -> None:\n        try:\n            await asyncio.wait_for(\n                self._messages.put(message), timeout=self._delivery_timeout\n            )\n        except TimeoutError as exc:\n            raise MessageDeliveryError(\n                \"Iterator delivery queue remained full for \"\n                f\"{self._delivery_timeout:.3f}s\"\n            ) from exc\n        self._message_ready.set()\n\n    def _ensure_callback_worker(self) -> None:\n        if self._callback_worker_task is None or self._callback_worker_task.done():\n            self._callback_worker_task = asyncio.create_task(\n                self._callback_worker(), name=\"mqttnext-callback-worker\"\n            )\n\n    async def _enqueue_callback(\n        self, callback: Callable[..., Any], *args: Any\n    ) -> None:\n        self._ensure_callback_worker()\n        try:\n            await asyncio.wait_for(\n                self._callback_queue.put((callback, args)),\n                timeout=self._delivery_timeout,\n            )\n        except TimeoutError as exc:\n            raise MessageDeliveryError(\n                \"Callback delivery queue remained full for \"\n                f\"{self._delivery_timeout:.3f}s\"\n            ) from exc\n\n    async def _callback_worker(self) -> None:\n        try:\n            while True:\n                callback, args = await self._callback_queue.get()\n                try:\n                    await self._invoke(callback, *args)\n                except asyncio.CancelledError:\n                    raise\n                except Exception as exc:\n                    self._report_callback_error(callback, exc)\n                finally:\n                    self._callback_queue.task_done()\n        except asyncio.CancelledError:\n            raise\n\n    def _report_callback_error(\n        self,\n        callback: Callable[..., Any] | None,\n        exc: BaseException,\n    ) -> None:\n        asyncio.get_running_loop().call_exception_handler(\n            {\n                \"message\": \"mqttnext user callback failed\",\n                \"exception\": exc,\n                \"callback\": callback,\n            }\n        )\n\n    async def _shutdown_callback_worker(self, *, drain: bool) -> None:\n        task = self._callback_worker_task\n        if task is None:\n            return\n        if drain and not task.done():\n            try:\n                await asyncio.wait_for(\n                    self._callback_queue.join(),\n                    timeout=self._callback_shutdown_timeout,\n                )\n            except TimeoutError:\n                pass\n        if not task.done():\n            task.cancel()\n            try:\n                await task\n            except asyncio.CancelledError:\n                pass\n        self._callback_worker_task = None\n        while True:\n            try:\n                self._callback_queue.get_nowait()\n            except asyncio.QueueEmpty:\n                break\n            else:\n                self._callback_queue.task_done()\n\n    def _discard_connection_sends(self) -> None:\n        if not self._pending_effects:\n            return\n        self._pending_effects = deque(\n            effect\n            for effect in self._pending_effects\n            if effect.kind is not EffectKind.SEND\n        )\n""",
    )

    replace_once(
        path,
        """        if not preserve_reconnect:\n            tasks.append(self._reconnect_task)\n        tasks.extend(self._callback_tasks)\n        for task in tasks:\n""",
        """        if not preserve_reconnect:\n            tasks.append(self._reconnect_task)\n        for task in tasks:\n""",
    )

    replace_once(
        path,
        """                except (asyncio.CancelledError, Exception):\n                    pass\n        if self._reader_task is not current:\n""",
        """                except (asyncio.CancelledError, Exception):\n                    pass\n        self._discard_connection_sends()\n        async with self._outbound_space:\n            self._outbound_space.notify_all()\n        if self._reader_task is not current:\n""",
    )

    replace_once(
        path,
        """        self._callback_tasks = {\n            task\n            for task in self._callback_tasks\n            if task is current and not task.done()\n        }\n        if self._transport is not None:\n""",
        """        if self._transport is not None:\n""",
    )

    replace_once(
        path,
        """            self._transport = None\n        self._closed.set()\n""",
        """            self._transport = None\n        if not preserve_reconnect:\n            await self._shutdown_callback_worker(drain=True)\n        self._closed.set()\n        self._message_ready.set()\n""",
    )


def patch_errors() -> None:
    replace_once(
        "src/mqttnext/errors.py",
        '''class FlowControlError(MQTTError):
    """Outbound inflight window exhausted (raise mode)."""


class NotConnectedError''',
        '''class FlowControlError(MQTTError):
    """Outbound inflight window exhausted (raise mode)."""


class MessageDeliveryError(FlowControlError):
    """Application delivery could not keep up within the configured deadline."""


class NotConnectedError''',
    )


def write_memory_store() -> None:
    write(
        "src/mqttnext/persistence/memory.py",
        r'''
        """In-memory inflight persistence (ordered, injectable interface)."""

        from __future__ import annotations

        from collections.abc import ContextManager, Iterator
        from contextlib import nullcontext
        from typing import Protocol

        from mqttnext.types import InboundMessage, OutboundMessage


        class InflightStore(Protocol):
            def batch(self) -> ContextManager[None]: ...
            def put_out(self, msg: OutboundMessage) -> None: ...
            def get_out(self, mid: int) -> OutboundMessage | None: ...
            def pop_out(self, mid: int) -> OutboundMessage | None: ...
            def update_out(self, msg: OutboundMessage) -> None: ...
            def out_items(self) -> Iterator[OutboundMessage]: ...
            def clear_out(self) -> None: ...

            def put_in(self, msg: InboundMessage) -> None: ...
            def get_in(self, mid: int) -> InboundMessage | None: ...
            def pop_in(self, mid: int) -> InboundMessage | None: ...
            def update_in(self, msg: InboundMessage) -> None: ...
            def in_items(self) -> Iterator[InboundMessage]: ...
            def clear_in(self) -> None: ...


        class MemoryInflightStore:
            """Ordered dict-backed store. Insertion order is retransmission order."""

            __slots__ = ("_out", "_in")

            def __init__(self) -> None:
                self._out: dict[int, OutboundMessage] = {}
                self._in: dict[int, InboundMessage] = {}

            def batch(self) -> ContextManager[None]:
                return nullcontext()

            def put_out(self, msg: OutboundMessage) -> None:
                self._out[msg.mid] = msg

            def get_out(self, mid: int) -> OutboundMessage | None:
                return self._out.get(mid)

            def pop_out(self, mid: int) -> OutboundMessage | None:
                return self._out.pop(mid, None)

            def update_out(self, msg: OutboundMessage) -> None:
                if msg.mid not in self._out:
                    raise KeyError(msg.mid)
                self._out[msg.mid] = msg

            def out_items(self) -> Iterator[OutboundMessage]:
                return iter(self._out.values())

            def clear_out(self) -> None:
                self._out.clear()

            def put_in(self, msg: InboundMessage) -> None:
                self._in[msg.mid] = msg

            def get_in(self, mid: int) -> InboundMessage | None:
                return self._in.get(mid)

            def pop_in(self, mid: int) -> InboundMessage | None:
                return self._in.pop(mid, None)

            def update_in(self, msg: InboundMessage) -> None:
                if msg.mid not in self._in:
                    raise KeyError(msg.mid)
                self._in[msg.mid] = msg

            def in_items(self) -> Iterator[InboundMessage]:
                return iter(self._in.values())

            def clear_in(self) -> None:
                self._in.clear()
        ''',
    )


def write_sqlite_store() -> None:
    write(
        "src/mqttnext/persistence/sqlite.py",
        r'''
        """SQLite-backed inflight persistence.

        The store is synchronous by design and is called from the client's event-loop
        thread. A re-entrant lock protects accidental cross-thread access, while
        ``batch()`` groups protocol transitions into one durable transaction before
        generated wire effects are released.
        """

        from __future__ import annotations

        import base64
        import json
        import sqlite3
        import threading
        from collections.abc import Iterator
        from contextlib import contextmanager
        from pathlib import Path
        from typing import Any

        from mqttnext.enums import InboundQoSState, OutboundQoSState, QoS
        from mqttnext.types import InboundMessage, OutboundMessage, Properties


        def _decode_payload(data: bytes | str) -> bytes:
            if isinstance(data, str):
                return base64.b64decode(data.encode("ascii"))
            return bytes(data)


        def _json_sanitize(value: Any) -> Any:
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
            """Durable ordered store for outbound and inbound QoS state."""

            def __init__(self, path: str | Path) -> None:
                self._path = Path(path)
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._lock = threading.RLock()
                self._batch_depth = 0
                self._conn = sqlite3.connect(self._path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
                self._conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS outbound (
                        mid INTEGER PRIMARY KEY,
                        topic TEXT NOT NULL,
                        payload BLOB NOT NULL,
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
                        payload BLOB NOT NULL,
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
                row = self._conn.execute(
                    f"SELECT COALESCE(MAX(seq), 0) FROM {table}"
                ).fetchone()
                assert row is not None
                return int(row[0])

            @contextmanager
            def batch(self) -> Iterator[None]:
                with self._lock:
                    outermost = self._batch_depth == 0
                    if outermost:
                        self._conn.execute("BEGIN IMMEDIATE")
                    self._batch_depth += 1
                    try:
                        yield
                    except BaseException:
                        self._batch_depth -= 1
                        if outermost:
                            self._conn.rollback()
                        raise
                    else:
                        self._batch_depth -= 1
                        if outermost:
                            self._conn.commit()

            def _commit_if_needed(self) -> None:
                if self._batch_depth == 0:
                    self._conn.commit()

            def close(self) -> None:
                with self._lock:
                    if self._batch_depth:
                        raise RuntimeError("Cannot close SQLite store inside batch()")
                    self._conn.commit()
                    self._conn.close()

            def put_out(self, msg: OutboundMessage) -> None:
                with self._lock:
                    self._out_seq += 1
                    self._conn.execute(
                        """
                        INSERT INTO outbound(
                            mid, topic, payload, qos, retain, state, dup,
                            properties, extra, seq
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                        ON CONFLICT(mid) DO UPDATE SET
                            topic=excluded.topic, payload=excluded.payload,
                            qos=excluded.qos, retain=excluded.retain,
                            state=excluded.state, dup=excluded.dup,
                            properties=excluded.properties
                        """,
                        (
                            msg.mid,
                            msg.topic,
                            sqlite3.Binary(msg.payload),
                            int(msg.qos),
                            int(msg.retain),
                            int(msg.state),
                            int(msg.dup),
                            _props_to_json(msg.properties),
                            self._out_seq,
                        ),
                    )
                    self._commit_if_needed()

            def get_out(self, mid: int) -> OutboundMessage | None:
                with self._lock:
                    row = self._conn.execute(
                        "SELECT * FROM outbound WHERE mid=?", (mid,)
                    ).fetchone()
                return _row_to_out(row) if row else None

            def pop_out(self, mid: int) -> OutboundMessage | None:
                with self._lock:
                    row = self._conn.execute(
                        "SELECT * FROM outbound WHERE mid=?", (mid,)
                    ).fetchone()
                    if row is None:
                        return None
                    self._conn.execute("DELETE FROM outbound WHERE mid=?", (mid,))
                    self._commit_if_needed()
                return _row_to_out(row)

            def update_out(self, msg: OutboundMessage) -> None:
                with self._lock:
                    cur = self._conn.execute(
                        "UPDATE outbound SET state=?, dup=? WHERE mid=?",
                        (int(msg.state), int(msg.dup), msg.mid),
                    )
                    if cur.rowcount == 0:
                        raise KeyError(msg.mid)
                    self._commit_if_needed()

            def out_items(self) -> Iterator[OutboundMessage]:
                with self._lock:
                    rows = self._conn.execute(
                        "SELECT * FROM outbound ORDER BY seq"
                    ).fetchall()
                return iter(_row_to_out(row) for row in rows)

            def clear_out(self) -> None:
                with self._lock:
                    self._conn.execute("DELETE FROM outbound")
                    self._commit_if_needed()

            def put_in(self, msg: InboundMessage) -> None:
                with self._lock:
                    self._in_seq += 1
                    self._conn.execute(
                        """
                        INSERT INTO inbound(
                            mid, topic, payload, qos, retain, state, delivered,
                            properties, user_acked, seq
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(mid) DO UPDATE SET
                            topic=excluded.topic, payload=excluded.payload,
                            qos=excluded.qos, retain=excluded.retain,
                            state=excluded.state, delivered=excluded.delivered,
                            properties=excluded.properties,
                            user_acked=excluded.user_acked
                        """,
                        (
                            msg.mid,
                            msg.topic,
                            sqlite3.Binary(msg.payload),
                            int(msg.qos),
                            int(msg.retain),
                            int(msg.state),
                            int(msg.delivered),
                            _props_to_json(msg.properties),
                            int(msg.user_acked),
                            self._in_seq,
                        ),
                    )
                    self._commit_if_needed()

            def get_in(self, mid: int) -> InboundMessage | None:
                with self._lock:
                    row = self._conn.execute(
                        "SELECT * FROM inbound WHERE mid=?", (mid,)
                    ).fetchone()
                return _row_to_in(row) if row else None

            def pop_in(self, mid: int) -> InboundMessage | None:
                with self._lock:
                    row = self._conn.execute(
                        "SELECT * FROM inbound WHERE mid=?", (mid,)
                    ).fetchone()
                    if row is None:
                        return None
                    self._conn.execute("DELETE FROM inbound WHERE mid=?", (mid,))
                    self._commit_if_needed()
                return _row_to_in(row)

            def update_in(self, msg: InboundMessage) -> None:
                with self._lock:
                    cur = self._conn.execute(
                        """
                        UPDATE inbound
                        SET state=?, delivered=?, user_acked=?
                        WHERE mid=?
                        """,
                        (
                            int(msg.state),
                            int(msg.delivered),
                            int(msg.user_acked),
                            msg.mid,
                        ),
                    )
                    if cur.rowcount == 0:
                        raise KeyError(msg.mid)
                    self._commit_if_needed()

            def in_items(self) -> Iterator[InboundMessage]:
                with self._lock:
                    rows = self._conn.execute(
                        "SELECT * FROM inbound ORDER BY seq"
                    ).fetchall()
                return iter(_row_to_in(row) for row in rows)

            def clear_in(self) -> None:
                with self._lock:
                    self._conn.execute("DELETE FROM inbound")
                    self._commit_if_needed()
        ''',
    )


def main() -> None:
    patch_async_client()
    patch_errors()
    write_memory_store()
    write_sqlite_store()


if __name__ == "__main__":
    main()
