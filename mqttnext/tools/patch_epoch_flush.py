from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one marker, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))


def patch_client() -> None:
    path = ROOT / "src/mqttnext/api/async_client.py"
    text = path.read_text()
    call_count = text.count("self._discard_connection_sends()")
    if call_count != 2:
        raise RuntimeError(f"unexpected discard call count: {call_count}")
    text = text.replace(
        "self._discard_connection_sends()",
        "self._discard_connection_effects()",
    )
    path.write_text(text)

    replace_once(
        path,
        "        self._effect_flush_task: asyncio.Task[None] | None = None\n"
        "        self._delivery_timeout = delivery_timeout\n",
        "        self._effect_flush_task: asyncio.Task[None] | None = None\n"
        "        self._effect_flush_requested = False\n"
        "        self._delivery_timeout = delivery_timeout\n",
    )

    replace_once(
        path,
        '''    def _schedule_effect_flush(self) -> None:
        task = self._effect_flush_task
        if task is not None and not task.done():
            return
        task = asyncio.create_task(self._flush_effects(), name="mqttnext-effect-flush")
        self._effect_flush_task = task
        task.add_done_callback(self._effect_flush_done)

    def _effect_flush_done(self, task: asyncio.Task[None]) -> None:
''',
        '''    def _schedule_effect_flush(self) -> None:
        # A producer may request another flush while the current task is
        # blocked on outbound backpressure. Record that wakeup rather than
        # silently coalescing it away.
        self._effect_flush_requested = True
        task = self._effect_flush_task
        if task is not None and not task.done():
            return
        task = asyncio.create_task(
            self._run_scheduled_effect_flush(),
            name="mqttnext-effect-flush",
        )
        self._effect_flush_task = task
        task.add_done_callback(self._effect_flush_done)

    async def _run_scheduled_effect_flush(self) -> None:
        while True:
            self._effect_flush_requested = False
            await self._flush_effects()
            if not self._effect_flush_requested:
                return

    def _effect_flush_done(self, task: asyncio.Task[None]) -> None:
''',
    )

    replace_once(
        path,
        "        if self._effect_flush_task is not current:\n"
        "            self._effect_flush_task = None\n"
        "        if not preserve_reconnect and self._reconnect_task is not current:\n",
        "        if self._effect_flush_task is not current:\n"
        "            self._effect_flush_task = None\n"
        "            self._effect_flush_requested = False\n"
        "        if not preserve_reconnect and self._reconnect_task is not current:\n",
    )

    replace_once(
        path,
        '''    def _discard_connection_sends(self) -> None:
        if not self._pending_effects:
            return
        self._pending_effects = deque(
            effect for effect in self._pending_effects if effect.kind is not EffectKind.SEND
        )
''',
        '''    def _discard_connection_effects(self) -> None:
        # Every pending effect was derived from the old protocol/transport
        # epoch. Session replay, failures and inbound redelivery are rebuilt
        # from the engine/store after the next CONNACK; retaining an old
        # MESSAGE or completion effect can duplicate delivery just as surely
        # as retaining old wire bytes can duplicate a publish.
        self._pending_effects.clear()
''',
    )

    replace_once(
        path,
        "        # Wire effects belong to a transport epoch. QoS 1/2 replay is rebuilt\n"
        "        # from the engine/store after CONNACK; carrying old bytes into a new\n"
        "        # transport can publish a packet the engine has already failed.\n",
        "        # Effects belong to a protocol/transport epoch. QoS replay and\n"
        "        # inbound redelivery are rebuilt from the engine/store after\n"
        "        # CONNACK; no old effect may cross into the new connection.\n",
    )


def append_tests() -> None:
    atomicity = ROOT / "tests/unit/test_effect_atomicity.py"
    text = atomicity.read_text()
    marker = "test_scheduled_flush_records_wakeup_while_active"
    if marker not in text:
        atomicity.write_text(
            text
            + '''\n\nasync def test_scheduled_flush_records_wakeup_while_active() -> None:\n'''
            + '''    client = AsyncClient(client_id="flush-wakeup")\n'''
            + '''    started = asyncio.Event()\n'''
            + '''    release = asyncio.Event()\n'''
            + '''    calls = 0\n\n'''
            + '''    async def controlled_flush(*, nowait: bool = False) -> None:\n'''
            + '''        nonlocal calls\n'''
            + '''        calls += 1\n'''
            + '''        if calls == 1:\n'''
            + '''            started.set()\n'''
            + '''            await release.wait()\n\n'''
            + '''    client._flush_effects = controlled_flush  # type: ignore[method-assign]\n'''
            + '''    client._schedule_effect_flush()\n'''
            + '''    await started.wait()\n'''
            + '''    client._schedule_effect_flush()\n'''
            + '''    release.set()\n'''
            + '''    task = client._effect_flush_task\n'''
            + '''    assert task is not None\n'''
            + '''    await task\n'''
            + '''    assert calls == 2\n'''
        )

    delivery = ROOT / "tests/unit/test_delivery_backpressure.py"
    text = delivery.read_text()
    marker = "test_force_close_discards_all_old_connection_effects"
    if marker not in text:
        delivery.write_text(
            text
            + '''\n\nasync def test_force_close_discards_all_old_connection_effects() -> None:\n'''
            + '''    client = AsyncClient(message_delivery="iterator")\n'''
            + '''    client._pending_effects.extend(\n'''
            + '''        [\n'''
            + '''            EngineEffect(\n'''
            + '''                kind=EffectKind.MESSAGE,\n'''
            + '''                data=Message(topic="old", payload=b"old"),\n'''
            + '''            ),\n'''
            + '''            EngineEffect(kind=EffectKind.PUBLISH_COMPLETE, data=7),\n'''
            + '''        ]\n'''
            + '''    )\n'''
            + '''    await client._force_close()\n'''
            + '''    assert not client._pending_effects\n'''
        )


if __name__ == "__main__":
    patch_client()
    append_tests()
