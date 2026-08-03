"""Refine batch failure accounting for MQTT packet-id reuse."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected source shape in {relative}")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '        self._pending: set[int] = set()\n',
        '        self._pending: dict[int, int] = {}\n',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''    def _register(self, mid: int | None) -> None:
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
''',
        '''    def _register(self, mid: int | None) -> None:
        index = self._submitted
        self._mids.append(mid)
        self._submitted += 1
        if mid is None:
            self._completed += 1
        else:
            self._pending[mid] = index

    def _complete(self, mid: int, error: BaseException | None = None) -> None:
        index = self._pending.pop(mid, None)
        if index is None:
            return
        self._completed += 1
        if error is not None:
            self._failures[index] = error
''',
    )
    replace_once(
        "mqttnext/src/mqttnext/api/models.py",
        '''        for mid in self._pending:
            self._failures.setdefault(mid, error)
''',
        '''        for index in self._pending.values():
            self._failures.setdefault(index, error)
''',
    )
    replace_once(
        "mqttnext/tests/unit/test_publish_many.py",
        '''    assert raised.value.failures == {8: failure}
''',
        '''    assert raised.value.failures == {1: failure}


def test_batch_receipt_failure_indexes_survive_mid_reuse() -> None:
    receipt = PublishBatchReceipt()
    receipt._register(7)
    receipt._complete(7)
    receipt._register(7)
    failure = RuntimeError("second use rejected")
    receipt._complete(7, failure)
    receipt._seal()

    assert receipt.completed == 2
    assert receipt.failures == {1: failure}
''',
    )

    Path(__file__).unlink()
    workflow = ROOT / ".github/workflows/mqttnext-publish-many-refine.yml"
    if workflow.exists():
        workflow.unlink()


if __name__ == "__main__":
    main()
