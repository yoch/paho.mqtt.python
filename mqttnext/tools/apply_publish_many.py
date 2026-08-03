"""Apply the publish_many API and its correctness tests.

Temporary transformer. It removes itself and its workflow before committing the
production tree.
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


def main() -> None:
    replace_once(
        "mqttnext/src/mqttnext/errors.py",
        '''class SessionDiscardedError(MQTTError):
    """Pending publish was discarded because a clean session replaced the old one."""
''',
        '''class SessionDiscardedError(MQTTError):
    """Pending publish was discarded because a clean session replaced the old one."""


class PublishBatchError(MQTTError):
    """One or more publications in a batch failed."""

    def __init__(
        self,
        failures: dict[int, BaseException] | None = None,
        *,
        cause: BaseException | None = None,
        receipt: object | None = None,
    ) -> None:
        self.failures = dict(failures or {})
        self.cause = cause
        self.receipt = receipt
        if cause is not None:
            message = f"Batch submission failed: {cause}"
        else:
            message = f"{len(self.failures)} publication(s) failed in batch"
        super().__init__(message)
''',
    )

    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''from dataclasses import dataclass

from mqttnext.enums import QoS
''',
        '''from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mqttnext.enums import QoS
from mqttnext.errors import PublishBatchError
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''from mqttnext.types import Message


@dataclass(slots=True)
class PublishReceipt:
''',
        '''from mqttnext.types import Message, Properties


@dataclass(slots=True, frozen=True)
class PublishMessage:
    """One immutable entry accepted by :meth:`AsyncClient.publish_many`."""

    topic: str
    payload: bytes | str = b""
    qos: QoS | int = QoS.AT_MOST_ONCE
    retain: bool = False
    properties: Properties | None = None


class PublishBatchReceipt:
    """Aggregate completion handle without one task/event per publication."""

    __slots__ = (
        "_mids",
        "_pending",
        "_failures",
        "_done",
        "_progress",
        "_sealed",
        "_submitted",
        "_completed",
        "_fatal",
    )

    def __init__(self) -> None:
        self._mids: list[int | None] = []
        self._pending: set[int] = set()
        self._failures: dict[int, BaseException] = {}
        self._done = asyncio.Event()
        self._progress = asyncio.Event()
        self._sealed = False
        self._submitted = 0
        self._completed = 0
        self._fatal: BaseException | None = None

    @property
    def mids(self) -> tuple[int | None, ...]:
        return tuple(self._mids)

    @property
    def submitted(self) -> int:
        return self._submitted

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def failures(self) -> Mapping[int, BaseException]:
        return MappingProxyType(self._failures)

    def is_done(self) -> bool:
        return self._done.is_set()

    async def wait(self) -> None:
        await self._done.wait()
        if self._fatal is not None:
            raise PublishBatchError(
                self._failures,
                cause=self._fatal,
                receipt=self,
            ) from self._fatal
        if self._failures:
            raise PublishBatchError(self._failures, receipt=self)

    def _register(self, mid: int | None) -> None:
        self._mids.append(mid)
        self._submitted += 1
        if mid is None:
            self._completed += 1
        else:
            self._pending.add(mid)

    def _complete(self, mid: int, error: BaseException | None = None) -> None:
        if mid not in self._pending:
            return
        self._pending.remove(mid)
        self._completed += 1
        if error is not None:
            self._failures[mid] = error
        self._progress.set()
        self._finish_if_ready()

    def _seal(self) -> None:
        self._sealed = True
        self._finish_if_ready()

    def _fail_remaining(self, error: BaseException) -> None:
        self._fatal = error
        for mid in self._pending:
            self._failures.setdefault(mid, error)
        self._completed += len(self._pending)
        self._pending.clear()
        self._sealed = True
        self._progress.set()
        self._done.set()

    async def _wait_pending_at_most(self, limit: int) -> None:
        while len(self._pending) > limit:
            self._progress.clear()
            if len(self._pending) <= limit:
                break
            await self._progress.wait()

    def _finish_if_ready(self) -> None:
        if self._sealed and not self._pending:
            self._done.set()


@dataclass(slots=True)
class PublishReceipt:
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''    "Message",
    "PublishReceipt",
''',
        '''    "Message",
    "PublishBatchReceipt",
    "PublishMessage",
    "PublishReceipt",
''',
    )

    replace_once(
        "mqttnext/src/mqttnext/api/__init__.py",
        '''from mqttnext.api.models import PublishReceipt, SubscribeResult, UnsubscribeResult

__all__ = ["AsyncClient", "PublishReceipt", "SubscribeResult", "UnsubscribeResult"]
''',
        '''from mqttnext.api.models import (
    PublishBatchReceipt,
    PublishMessage,
    PublishReceipt,
    SubscribeResult,
    UnsubscribeResult,
)

__all__ = [
    "AsyncClient",
    "PublishBatchReceipt",
    "PublishMessage",
    "PublishReceipt",
    "SubscribeResult",
    "UnsubscribeResult",
]
''',
    )

    replace_once(
        "mqttnext/src/mqttnext/protocol/engine.py",
        '''    def queue_subscribe(
''',
        '''    def queue_publish_many(
        self,
        messages: Iterable[tuple[str, bytes, QoS | int, bool, Properties | None]],
    ) -> list[PublishHandle]:
        """Queue one bounded chunk atomically with respect to engine/store state."""
        effect_start = len(self._effects)
        queued_start = len(self._queued)
        inflight_start = self.flow.inflight
        handles: list[PublishHandle] = []
        try:
            with self.store.batch():
                for topic, payload, qos, retain, properties in messages:
                    handles.append(
                        self.queue_publish(
                            topic,
                            payload,
                            qos=qos,
                            retain=retain,
                            properties=properties,
                        )
                    )
        except BaseException:
            del self._effects[effect_start:]
            while len(self._queued) > queued_start:
                self._queued.pop()
            while self.flow.inflight > inflight_start:
                self.flow.release()
            for handle in handles:
                if handle.mid is None:
                    continue
                try:
                    self.store.delete_out(handle.mid)
                except Exception:
                    pass
                self.packet_ids.release(handle.mid)
            raise
        return handles

    def queue_subscribe(
''',
    )

    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''import ssl
import time
from collections import deque
''',
        '''import ssl
import time
from collections import deque
from itertools import islice
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''from mqttnext.api.models import PublishReceipt, SubscribeResult, UnsubscribeResult
''',
        '''from mqttnext.api.models import (
    PublishBatchReceipt,
    PublishMessage,
    PublishReceipt,
    SubscribeResult,
    UnsubscribeResult,
)
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''    MQTTTimeoutError,
    MalformedPacketError,
''',
        '''    MQTTTimeoutError,
    MalformedPacketError,
    PublishBatchError,
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''        self._receipts: dict[int, PublishReceipt] = {}
        self._sub_futs: dict[int, asyncio.Future[SubscribeResult]] = {}
''',
        '''        self._receipts: dict[int, PublishReceipt] = {}
        self._batch_receipts: dict[int, PublishBatchReceipt] = {}
        self._sub_futs: dict[int, asyncio.Future[SubscribeResult]] = {}
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''    async def auth(
''',
        '''    async def publish_many(
        self,
        messages: Iterable[PublishMessage],
        *,
        chunk_size: int = 256,
        max_pending: int | None = None,
        nowait: bool = False,
    ) -> PublishBatchReceipt:
        """Publish a batch with bounded memory and aggregate completion.

        QoS 0 avoids one lock/effect flush per message. QoS 1/2 use one shared
        receipt and continuously refill the negotiated inflight window without
        creating waiter tasks for individual packet identifiers.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if max_pending is not None and max_pending <= 0:
            raise ValueError("max_pending must be greater than 0")

        receipt = PublishBatchReceipt()
        iterator = iter(messages)
        flow_limit = self._engine.flow.limit
        pending_limit = max(
            flow_limit + chunk_size if max_pending is None else max_pending,
            flow_limit + chunk_size,
        )

        try:
            while True:
                chunk = list(islice(iterator, chunk_size))
                if not chunk:
                    break
                target = max(flow_limit, pending_limit - len(chunk))
                await receipt._wait_pending_at_most(target)

                requests: list[tuple[str, bytes, QoS | int, bool, Properties | None]] = []
                for message in chunk:
                    if not isinstance(message, PublishMessage):
                        raise TypeError("publish_many entries must be PublishMessage instances")
                    payload = (
                        message.payload.encode("utf-8")
                        if isinstance(message.payload, str)
                        else message.payload
                    )
                    requests.append(
                        (
                            message.topic,
                            payload,
                            message.qos,
                            message.retain,
                            message.properties,
                        )
                    )

                async with self._engine_lock:
                    handles = self._engine.queue_publish_many(requests)
                    for handle in handles:
                        receipt._register(handle.mid)
                        if handle.mid is not None:
                            self._batch_receipts[handle.mid] = receipt
                    self._collect_effects_locked()
                await self._drain_effects(nowait=nowait)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            receipt._seal()
            raise PublishBatchError(cause=exc, receipt=receipt) from exc

        receipt._seal()
        return receipt

    async def auth(
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''        elif kind is EffectKind.PUBLISH_COMPLETE:
            mid: int = effect.data
            receipt = self._receipts.pop(mid, None)
            if receipt is not None and receipt._event is not None:
                receipt._event.set()
            if self.on_publish is not None:
                await self._enqueue_callback(self.on_publish, mid, None)
        elif kind is EffectKind.PUBLISH_FAILED:
            failure: PublishFailure = effect.data
            receipt = self._receipts.pop(failure.mid, None)
            if receipt is not None:
                receipt._error = failure.reason
                if receipt._event is not None:
                    receipt._event.set()
            if self.on_publish is not None:
                await self._enqueue_callback(self.on_publish, failure.mid, failure.reason)
''',
        '''        elif kind is EffectKind.PUBLISH_COMPLETE:
            mid: int = effect.data
            receipt = self._receipts.pop(mid, None)
            if receipt is not None and receipt._event is not None:
                receipt._event.set()
            batch = self._batch_receipts.pop(mid, None)
            if batch is not None:
                batch._complete(mid)
            if self.on_publish is not None:
                await self._enqueue_callback(self.on_publish, mid, None)
        elif kind is EffectKind.PUBLISH_FAILED:
            failure: PublishFailure = effect.data
            receipt = self._receipts.pop(failure.mid, None)
            if receipt is not None:
                receipt._error = failure.reason
                if receipt._event is not None:
                    receipt._event.set()
            batch = self._batch_receipts.pop(failure.mid, None)
            if batch is not None:
                batch._complete(failure.mid, failure.reason)
            if self.on_publish is not None:
                await self._enqueue_callback(self.on_publish, failure.mid, failure.reason)
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''    def _fail_pending(self, exc: BaseException) -> None:
        for receipt in self._receipts.values():
            receipt._error = exc
            if receipt._event is not None:
                receipt._event.set()
        self._receipts.clear()
        self._fail_non_replayable(exc)
''',
        '''    def _fail_pending(self, exc: BaseException) -> None:
        for receipt in self._receipts.values():
            receipt._error = exc
            if receipt._event is not None:
                receipt._event.set()
        self._receipts.clear()
        batches = set(self._batch_receipts.values())
        self._batch_receipts.clear()
        for batch in batches:
            batch._fail_remaining(exc)
        self._fail_non_replayable(exc)
''',
    )

    (ROOT / "mqttnext/tests/unit/test_publish_many.py").write_text(
        '''"""Correctness and lifecycle tests for aggregate batch publishing."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from mqttnext.api import AsyncClient, PublishMessage
from mqttnext.api.models import PublishBatchReceipt
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.enums import ConnectionState, MQTTProtocolVersion, PacketType, QoS
from mqttnext.errors import PublishBatchError
from mqttnext.packets import (
    PubAckPacket,
    PubCompPacket,
    PublishPacket,
    PubRecPacket,
    PubRelPacket,
    encode_frame,
)
from mqttnext.persistence.sqlite import SqliteInflightStore
from mqttnext.protocol.engine import EngineConfig, ProtocolEngine


class BatchBrokerTransport:
    def __init__(self, protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311) -> None:
        self.protocol = protocol
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._decoder = IncrementalDecoder()
        self._closing = False
        self.publishes: list[PublishPacket] = []

    async def write(self, data: bytes) -> None:
        self._decoder.feed(data)
        for raw in self._decoder.drain_packets(limit=10_000):
            if raw.packet_type is PacketType.CONNECT:
                body = b"\\x00\\x00\\x00" if self.protocol is MQTTProtocolVersion.MQTTv5 else b"\\x00\\x00"
                self._rx.put_nowait(encode_frame(PacketType.CONNACK, 0, body))
            elif raw.packet_type is PacketType.PUBLISH:
                packet = PublishPacket.decode(raw.flags, raw.remaining, self.protocol)
                self.publishes.append(packet)
                if packet.qos is QoS.AT_LEAST_ONCE:
                    assert packet.mid is not None
                    self._rx.put_nowait(PubAckPacket(packet.mid).encode(self.protocol))
                elif packet.qos is QoS.EXACTLY_ONCE:
                    assert packet.mid is not None
                    self._rx.put_nowait(PubRecPacket(packet.mid).encode(self.protocol))
            elif raw.packet_type is PacketType.PUBREL:
                rel = PubRelPacket.decode(raw.remaining, self.protocol)
                self._rx.put_nowait(PubCompPacket(rel.mid).encode(self.protocol))

    async def read(self, n: int = 65536) -> bytes:
        return await self._rx.get()

    async def close(self) -> None:
        self._closing = True
        self._rx.put_nowait(b"")

    def is_closing(self) -> bool:
        return self._closing


def client_with_broker(
    *,
    protocol: MQTTProtocolVersion = MQTTProtocolVersion.MQTTv311,
    window: int = 16,
) -> tuple[AsyncClient, BatchBrokerTransport]:
    client = AsyncClient(
        client_id="batch-test",
        protocol=protocol,
        max_outbound_inflight=window,
    )
    broker = BatchBrokerTransport(protocol)

    async def factory(host: str, port: int, *, ssl: object = None) -> BatchBrokerTransport:
        return broker

    client._transport_factory = factory
    return client, broker


async def test_publish_many_qos0_uses_immediate_aggregate_receipt() -> None:
    client, broker = client_with_broker()
    await client.connect("fake", timeout=2.0)
    receipt = await client.publish_many(
        [PublishMessage("batch/q0", str(index), qos=0) for index in range(200)],
        chunk_size=32,
    )
    await asyncio.wait_for(client._outbound.join(), timeout=2.0)
    assert receipt.submitted == 200
    assert receipt.completed == 200
    assert receipt.pending_count == 0
    assert receipt.is_done()
    await receipt.wait()
    assert len(broker.publishes) == 200
    await client.disconnect()


@pytest.mark.parametrize("qos", [QoS.AT_LEAST_ONCE, QoS.EXACTLY_ONCE])
async def test_publish_many_qos_acknowledged_without_per_message_waiters(qos: QoS) -> None:
    client, broker = client_with_broker(window=8)
    await client.connect("fake", timeout=2.0)
    receipt = await client.publish_many(
        [PublishMessage("batch/ack", b"x", qos=qos) for _ in range(160)],
        chunk_size=24,
    )
    await asyncio.wait_for(receipt.wait(), timeout=5.0)
    assert receipt.submitted == 160
    assert receipt.completed == 160
    assert receipt.pending_count == 0
    assert not client._receipts
    assert not client._batch_receipts
    assert len(broker.publishes) == 160
    await client.disconnect()


def test_engine_chunk_rollback_restores_all_mutable_state() -> None:
    engine = ProtocolEngine(EngineConfig(client_id="rollback"))
    engine.state = ConnectionState.CONNECTED

    with pytest.raises(Exception):
        engine.queue_publish_many(
            [
                ("valid/topic", b"x", QoS.AT_LEAST_ONCE, False, None),
                ("invalid/#", b"x", QoS.AT_LEAST_ONCE, False, None),
            ]
        )

    assert not engine.take_effects()
    assert not list(engine.store.out_items())
    assert not engine._queued
    assert engine.flow.inflight == 0
    assert len(engine.packet_ids) == 0


def test_engine_chunk_uses_one_sqlite_commit(tmp_path: Path) -> None:
    store = SqliteInflightStore(tmp_path / "batch-publish.db")
    engine = ProtocolEngine(EngineConfig(client_id="sqlite-batch"), store=store)
    engine.state = ConnectionState.CONNECTED
    trace: list[str] = []
    store._conn.set_trace_callback(trace.append)

    handles = engine.queue_publish_many(
        [(f"batch/{index}", b"x", QoS.AT_LEAST_ONCE, False, None) for index in range(20)]
    )

    assert len(handles) == 20
    assert sum(statement == "COMMIT" for statement in trace) == 1
    store.close()


async def test_batch_receipt_aggregates_failures() -> None:
    receipt = PublishBatchReceipt()
    receipt._register(7)
    receipt._register(8)
    receipt._complete(7)
    failure = RuntimeError("rejected")
    receipt._complete(8, failure)
    receipt._seal()

    with pytest.raises(PublishBatchError) as raised:
        await receipt.wait()
    assert raised.value.failures == {8: failure}
'''
    )

    replace_once(
        "mqttnext/README.md",
        '''## Persistence
''',
        '''## Batch publishing

`AsyncClient.publish_many()` accepts immutable `PublishMessage` entries and
returns one `PublishBatchReceipt`. QoS 0 publications are queued in bounded
chunks with one engine lock/effect flush per chunk. QoS 1/2 share one aggregate
completion tracker; the negotiated inflight window is continuously refilled
without spawning a task or event for each packet identifier.

```python
from mqttnext.api import PublishMessage

receipt = await client.publish_many(
    [PublishMessage("sensors/temperature", payload, qos=1) for payload in payloads]
)
await receipt.wait()
```

## Persistence
''',
    )

    Path(__file__).unlink()
    workflow = ROOT / ".github/workflows/mqttnext-publish-many-transform.yml"
    if workflow.exists():
        workflow.unlink()


if __name__ == "__main__":
    main()
