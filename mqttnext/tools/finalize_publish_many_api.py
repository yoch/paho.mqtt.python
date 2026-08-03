"""Finalize publish_many memory bounds and public API shape."""

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
        "mqttnext/src/mqttnext/api/models.py",
        '''    __slots__ = (
        "_mids",
        "_pending",
''',
        '''    __slots__ = (
        "_pending",
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''        self._mids: list[int | None] = []
        self._pending: dict[int, int] = {}
''',
        '''        # At most the client's bounded pending window is retained. MQTT
        # packet identifiers may be reused during a long batch, so failures are
        # keyed by the stable zero-based input index stored as the value.
        self._pending: dict[int, int] = {}
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''    @property
    def mids(self) -> tuple[int | None, ...]:
        return tuple(self._mids)

''',
        "",
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''        index = self._submitted
        self._mids.append(mid)
        self._submitted += 1
''',
        '''        index = self._submitted
        self._submitted += 1
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''        chunk_size: int = 256,
        max_pending: int | None = None,
        nowait: bool = False,
''',
        '''        chunk_size: int = 256,
        nowait: bool = False,
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/async_client.py",
        '''        if max_pending is not None and max_pending <= 0:
            raise ValueError("max_pending must be greater than 0")

        receipt = PublishBatchReceipt()
        iterator = iter(messages)
        flow_limit = self._engine.flow.limit
        pending_limit = max(
            flow_limit + chunk_size if max_pending is None else max_pending,
            flow_limit + chunk_size,
        )
''',
        '''        receipt = PublishBatchReceipt()
        iterator = iter(messages)
        flow_limit = self._engine.flow.limit
        # Bound retained QoS state to one active protocol window plus one
        # submission chunk. This keeps memory independent of total iterable size
        # while allowing the next chunk to refill the window continuously.
        pending_limit = flow_limit + chunk_size
''',
    )
    replace_once(
        "mqttnext/benchmarks/publish_many_ab.py",
        '''            chunk_size=CHUNK,
            max_pending=WINDOW + CHUNK,
''',
        '''            chunk_size=CHUNK,
''',
    )
    replace_once(
        "mqttnext/tests/unit/test_publish_many.py",
        '''    assert receipt.completed == 2
    assert receipt.failures == {1: failure}
''',
        '''    assert receipt.completed == 2
    assert receipt.failures == {1: failure}


def test_batch_receipt_does_not_retain_completed_mid_history() -> None:
    receipt = PublishBatchReceipt()
    for index in range(10_000):
        mid = index % 65_535 + 1
        receipt._register(mid)
        receipt._complete(mid)
    receipt._seal()

    assert receipt.submitted == 10_000
    assert receipt.completed == 10_000
    assert receipt.pending_count == 0
    assert not hasattr(receipt, "mids")
    assert not hasattr(receipt, "_mids")
''',
    )
    replace_once(
        "mqttnext/README.md",
        '''completion tracker; the negotiated inflight window is continuously refilled
without spawning a task or event for each packet identifier.
''',
        '''completion tracker; the negotiated inflight window is continuously refilled
without spawning a task or event for each packet identifier. Successful batches
retain only one inflight window plus one bounded submission chunk, regardless of
the total iterable size. Failures are reported by zero-based input index.
''',
    )

    Path(__file__).unlink()
    workflow = ROOT / ".github/workflows/mqttnext-publish-many-finalize.yml"
    if workflow.exists():
        workflow.unlink()


if __name__ == "__main__":
    main()
