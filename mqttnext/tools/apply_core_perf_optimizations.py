"""Apply measured low-risk mqttnext performance optimizations.

Temporary branch transformer. It removes itself and its workflow after applying
the production changes so profiling machinery never remains in the final tree.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one replacement, found {count}")
    path.write_text(text.replace(old, new, 1))


def append_once(relative: str, marker: str, addition: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n")


def main() -> None:
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''    async def _put_message(self, message: Message) -> None:
        try:
            await asyncio.wait_for(self._messages.put(message), timeout=self._delivery_timeout)
        except TimeoutError as exc:
            raise MessageDeliveryError(
                f"Iterator delivery queue remained full for {self._delivery_timeout:.3f}s"
            ) from exc
        self._message_ready.set()
''',
        '''    async def _put_message(self, message: Message) -> None:
        try:
            self._messages.put_nowait(message)
        except asyncio.QueueFull:
            try:
                await asyncio.wait_for(
                    self._messages.put(message),
                    timeout=self._delivery_timeout,
                )
            except TimeoutError as exc:
                raise MessageDeliveryError(
                    f"Iterator delivery queue remained full for "
                    f"{self._delivery_timeout:.3f}s"
                ) from exc
        self._message_ready.set()
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''    async def _enqueue_callback(self, callback: Callable[..., Any], *args: Any) -> None:
        self._ensure_callback_worker()
        try:
            await asyncio.wait_for(
                self._callback_queue.put((callback, args)),
                timeout=self._delivery_timeout,
            )
        except TimeoutError as exc:
            raise MessageDeliveryError(
                f"Callback delivery queue remained full for {self._delivery_timeout:.3f}s"
            ) from exc
''',
        '''    async def _enqueue_callback(self, callback: Callable[..., Any], *args: Any) -> None:
        self._ensure_callback_worker()
        job = (callback, args)
        try:
            self._callback_queue.put_nowait(job)
        except asyncio.QueueFull:
            try:
                await asyncio.wait_for(
                    self._callback_queue.put(job),
                    timeout=self._delivery_timeout,
                )
            except TimeoutError as exc:
                raise MessageDeliveryError(
                    f"Callback delivery queue remained full for "
                    f"{self._delivery_timeout:.3f}s"
                ) from exc
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''    def _collect_effects_locked(self) -> None:
        effects = self._engine.take_effects()
        self._pending_effects.extend(effect for effect in effects if effect.kind is EffectKind.SEND)
        self._pending_effects.extend(
            effect for effect in effects if effect.kind is not EffectKind.SEND
        )
''',
        '''    def _collect_effects_locked(self) -> None:
        sends: list[EngineEffect] = []
        events: list[EngineEffect] = []
        for effect in self._engine.take_effects():
            (sends if effect.kind is EffectKind.SEND else events).append(effect)
        self._pending_effects.extend(sends)
        self._pending_effects.extend(events)
''',
    )

    replace_once(
        "mqttnext/src/mqttnext/topics.py",
        '''def validate_received_publish_topic(topic: str) -> None:
    """Inbound PUBLISH topic: wildcards are a protocol error."""
    if not topic:
        return  # empty topic may be alias-resolved later
    try:
        _check_utf8_mqtt_topic(topic)
    except ProtocolError as exc:
        raise MalformedPacketError(str(exc)) from exc
    if "+" in topic or "#" in topic:
        raise MalformedPacketError("PUBLISH topic must not contain wildcards")
''',
        '''def validate_received_publish_topic(
    topic: str,
    *,
    utf8_validated: bool = False,
) -> None:
    """Validate an inbound PUBLISH topic.

    Packet decoding already performs the complete MQTT UTF-8 validation. The
    internal ``utf8_validated`` fast path avoids encoding and validating the
    same topic a second time while preserving the public standalone contract.
    """
    if not topic:
        return  # empty topic may be alias-resolved later
    if not utf8_validated:
        try:
            _check_utf8_mqtt_topic(topic)
        except ProtocolError as exc:
            raise MalformedPacketError(str(exc)) from exc
    if "+" in topic or "#" in topic:
        raise MalformedPacketError("PUBLISH topic must not contain wildcards")
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/protocol/engine.py",
        "        validate_received_publish_topic(topic)\n",
        "        validate_received_publish_topic(topic, utf8_validated=True)\n",
    )

    replace_once(
        "mqttnext/src/mqttnext/persistence/memory.py",
        '''    def pop_out(self, mid: int) -> OutboundMessage | None: ...
    def update_out(self, msg: OutboundMessage) -> None: ...
''',
        '''    def pop_out(self, mid: int) -> OutboundMessage | None: ...
    def delete_out(self, mid: int) -> bool: ...
    def update_out(self, msg: OutboundMessage) -> None: ...
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/persistence/memory.py",
        '''    def pop_out(self, mid: int) -> OutboundMessage | None:
        return self._out.pop(mid, None)

    def update_out(self, msg: OutboundMessage) -> None:
''',
        '''    def pop_out(self, mid: int) -> OutboundMessage | None:
        return self._out.pop(mid, None)

    def delete_out(self, mid: int) -> bool:
        return self._out.pop(mid, None) is not None

    def update_out(self, msg: OutboundMessage) -> None:
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/persistence/sqlite.py",
        '''    def pop_out(self, mid: int) -> OutboundMessage | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM outbound WHERE mid=?", (mid,)).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM outbound WHERE mid=?", (mid,))
            self._commit_if_needed()
        return _row_to_out(row) if row else None

    def update_out(self, msg: OutboundMessage) -> None:
''',
        '''    def pop_out(self, mid: int) -> OutboundMessage | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM outbound WHERE mid=?", (mid,)).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM outbound WHERE mid=?", (mid,))
            self._commit_if_needed()
        return _row_to_out(row)

    def delete_out(self, mid: int) -> bool:
        """Delete an outbound record without reading or reconstructing it."""
        with self._lock:
            cursor = self._conn.execute("DELETE FROM outbound WHERE mid=?", (mid,))
            self._commit_if_needed()
            return cursor.rowcount > 0

    def update_out(self, msg: OutboundMessage) -> None:
''',
    )
    engine_path = ROOT / "mqttnext/src/mqttnext/protocol/engine.py"
    engine = engine_path.read_text()
    count = engine.count("self.store.pop_out(")
    if count != 4:
        raise RuntimeError(f"engine.py: expected four pop_out calls, found {count}")
    engine_path.write_text(engine.replace("self.store.pop_out(", "self.store.delete_out("))

    append_once(
        "mqttnext/tests/unit/test_delivery_backpressure.py",
        "test_delivery_queue_fast_paths_avoid_timeout_task",
        '''
async def test_delivery_queue_fast_paths_avoid_timeout_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncClient(message_delivery="iterator")

    async def unexpected_wait_for(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("wait_for must only be used after queue saturation")

    monkeypatch.setattr(asyncio, "wait_for", unexpected_wait_for)
    message = Message(topic="fast", payload=b"x")
    await client._put_message(message)
    assert client._messages.get_nowait() is message

    called = asyncio.Event()

    def callback(_message: Message) -> None:
        called.set()

    await client._enqueue_callback(callback, message)
    await asyncio.sleep(0)
    assert called.is_set()
    await client._shutdown_callback_worker(drain=False)
''',
    )
    append_once(
        "mqttnext/tests/unit/test_effect_atomicity.py",
        "test_effect_collection_stably_prioritizes_sends",
        '''
def test_effect_collection_stably_prioritizes_sends() -> None:
    client = AsyncClient(client_id="stable-effect-partition")
    client._engine._emit(EffectKind.MESSAGE, Message(topic="first", payload=b"1"))
    client._engine._send(b"send-1")
    client._engine._emit(EffectKind.PINGRESP)
    client._engine._send(b"send-2")

    client._collect_effects_locked()

    assert [(effect.kind, effect.data) for effect in client._pending_effects] == [
        (EffectKind.SEND, b"send-1"),
        (EffectKind.SEND, b"send-2"),
        (EffectKind.MESSAGE, Message(topic="first", payload=b"1")),
        (EffectKind.PINGRESP, None),
    ]
''',
    )
    append_once(
        "mqttnext/tests/unit/test_topics.py",
        "test_received_publish_utf8_fast_path_keeps_structural_validation",
        '''
def test_received_publish_utf8_fast_path_keeps_structural_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_validation(_topic: str) -> None:
        raise AssertionError("decoded topics must not be UTF-8 validated twice")

    monkeypatch.setattr("mqttnext.topics._check_utf8_mqtt_topic", unexpected_validation)
    validate_received_publish_topic("already/decoded", utf8_validated=True)
    with pytest.raises(MalformedPacketError):
        validate_received_publish_topic("still/#", utf8_validated=True)
''',
    )
    append_once(
        "mqttnext/tests/unit/test_sqlite_store.py",
        "test_delete_out_uses_single_delete_without_select",
        '''
def test_delete_out_uses_single_delete_without_select(tmp_path: Path) -> None:
    store = SqliteInflightStore(tmp_path / "delete.db")
    store.put_out(outbound())
    trace: list[str] = []
    store._conn.set_trace_callback(trace.append)

    assert store.delete_out(7) is True
    assert store.delete_out(7) is False

    statements = [
        statement
        for statement in trace
        if statement.startswith(("SELECT", "DELETE"))
    ]
    assert statements == [
        "DELETE FROM outbound WHERE mid=7",
        "DELETE FROM outbound WHERE mid=7",
    ]
    store.close()
''',
    )

    Path(__file__).unlink()
    workflow = ROOT / ".github/workflows/mqttnext-core-perf-transform.yml"
    if workflow.exists():
        workflow.unlink()


if __name__ == "__main__":
    main()
