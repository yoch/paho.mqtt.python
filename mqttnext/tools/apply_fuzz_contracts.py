from __future__ import annotations

from pathlib import Path


FUZZ = Path("mqttnext/tests/fuzz/fuzz.py")
HYP = Path("mqttnext/tests/fuzz/test_hypothesis_fuzz.py")
TEST = Path("mqttnext/tests/unit/test_fuzz_contracts.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


fuzz = FUZZ.read_text()
fuzz = replace_once(fuzz, "import struct\n", "", "seeded struct import")
fuzz = replace_once(
    fuzz,
    "ALLOWED = (MQTTError, ValueError, IndexError, struct.error, ConnectionError)\n",
    "ALLOWED = (MQTTError, ConnectionError)\n",
    "seeded allowed exceptions",
)
fuzz = replace_once(
    fuzz,
    """def _check_engine_invariants(engine: ProtocolEngine) -> None:
    assert engine.flow.inflight >= 0, "negative flow inflight"
    assert engine.flow.inflight <= engine.flow.limit, "flow inflight exceeds limit"
    assert len(engine.packet_ids) <= 65535, "packet id pool overflow"
    assert engine._inbound_inflight >= 0, "negative inbound inflight"
    # No mid may be both pending-sub and in the store outbound.
    for mid in engine._pending_sub_mids:
        assert engine.store.get_out(mid) is None, f"mid {mid} both sub and publish"
    # Every inflight outbound mid must be reserved in the pool.
    for msg in engine.store.out_items():
        assert engine.packet_ids.in_use(msg.mid), f"inflight mid {msg.mid} not reserved"
""",
    """def _check_engine_invariants(engine: ProtocolEngine) -> None:
    assert engine.flow.inflight >= 0, "negative flow inflight"
    assert engine.flow.inflight <= engine.flow.limit, "flow inflight exceeds limit"
    assert engine._inbound_inflight >= 0, "negative inbound inflight"

    outbound = list(engine.store.out_items())
    outbound_mids = {msg.mid for msg in outbound}
    expected_mids = outbound_mids | set(engine._pending_sub_mids)
    actual_mids = set(engine.packet_ids._used)
    assert actual_mids == expected_mids, (
        f"packet-id mismatch: actual={sorted(actual_mids)} "
        f"expected={sorted(expected_mids)}"
    )

    queued_mids = {msg.mid for msg in engine._queued}
    expected_flow = sum(
        1
        for msg in outbound
        if msg.state is not OutboundQoSState.QUEUED and msg.mid not in queued_mids
    )
    assert engine.flow.inflight == expected_flow, (
        f"flow mismatch: actual={engine.flow.inflight} expected={expected_flow}"
    )
""",
    "seeded engine invariants",
)
fuzz = replace_once(
    fuzz,
    "from mqttnext.enums import MQTTProtocolVersion, PacketType, QoS\n",
    "from mqttnext.enums import MQTTProtocolVersion, OutboundQoSState, PacketType, QoS\n",
    "seeded state import",
)
fuzz = replace_once(
    fuzz,
    """        try:
            _parse_frame(buf, max_frame)
        except ALLOWED:
            pass
        except Exception as exc:  # noqa: BLE001
            result.crashes += 1
            detail = f"{exc!r}\\n{traceback.format_exc()}"
            if logger:
                msg = logger.failure(i, "crash", detail, bytes(buf))
                if result.first_failure is None:
                    result.first_failure = msg
            elif result.first_failure is None:
                result.first_failure = f"iter {i}: {detail}"
        # Invariant: buffer never grows unbounded on partial frames.
        if len(buf) > max_frame + 64 and _is_plausible_partial(buf):
            result.invariant_violations += 1
            if logger:
                msg = logger.failure(
                    i, "invariant", f"buffer grew to {len(buf)} on partial frame", bytes(buf)
                )
                if result.first_failure is None:
                    result.first_failure = msg
            elif result.first_failure is None:
                result.first_failure = f"iter {i} INVARIANT: buffer {len(buf)}"
""",
    """        before = len(buf)
        try:
            _parse_frame(buf, max_frame)
        except ALLOWED:
            pass
        except Exception as exc:  # noqa: BLE001
            result.crashes += 1
            detail = f"{exc!r}\\n{traceback.format_exc()}"
            if logger:
                msg = logger.failure(i, "crash", detail, bytes(buf))
                if result.first_failure is None:
                    result.first_failure = msg
            elif result.first_failure is None:
                result.first_failure = f"iter {i}: {detail}"
        if len(buf) > before:
            result.invariant_violations += 1
            detail = f"parser grew input buffer from {before} to {len(buf)}"
            if logger:
                msg = logger.failure(i, "invariant", detail, bytes(buf))
                if result.first_failure is None:
                    result.first_failure = msg
            elif result.first_failure is None:
                result.first_failure = f"iter {i} INVARIANT: {detail}"
""",
    "seeded WebSocket bound",
)
FUZZ.write_text(fuzz)

hyp = HYP.read_text()
hyp = replace_once(hyp, "import struct\n", "", "hypothesis struct import")
hyp = replace_once(
    hyp,
    "ALLOWED = (MQTTError, ValueError, IndexError, struct.error, ConnectionError)\n",
    "ALLOWED = (MQTTError, ConnectionError)\n",
    "hypothesis allowed exceptions",
)
hyp = replace_once(
    hyp,
    "from mqttnext.enums import MQTTProtocolVersion, PacketType, QoS\n",
    "from mqttnext.enums import MQTTProtocolVersion, OutboundQoSState, PacketType, QoS\n",
    "hypothesis state import",
)
hyp = replace_once(
    hyp,
    """def _engine_invariants(engine: ProtocolEngine) -> None:
    assert engine.flow.inflight >= 0
    assert engine.flow.inflight <= engine.flow.limit
    assert len(engine.packet_ids) <= 65535
    assert engine._inbound_inflight >= 0
    for mid in engine._pending_sub_mids:
        assert engine.store.get_out(mid) is None
    for msg in engine.store.out_items():
        assert engine.packet_ids.in_use(msg.mid)
""",
    """def _engine_invariants(engine: ProtocolEngine) -> None:
    assert engine.flow.inflight >= 0
    assert engine.flow.inflight <= engine.flow.limit
    assert engine._inbound_inflight >= 0

    outbound = list(engine.store.out_items())
    expected_mids = {msg.mid for msg in outbound} | set(engine._pending_sub_mids)
    assert set(engine.packet_ids._used) == expected_mids

    queued_mids = {msg.mid for msg in engine._queued}
    expected_flow = sum(
        1
        for msg in outbound
        if msg.state is not OutboundQoSState.QUEUED and msg.mid not in queued_mids
    )
    assert engine.flow.inflight == expected_flow
""",
    "hypothesis engine invariants",
)
hyp = replace_once(
    hyp,
    """    buf = bytearray(header + tail)
    try:
        _parse_frame(buf, 1024)
    except ALLOWED:
        pass
""",
    """    buf = bytearray(header + tail)
    before = len(buf)
    try:
        _parse_frame(buf, 1024)
    except ALLOWED:
        pass
    assert len(buf) <= before
""",
    "hypothesis WebSocket bound",
)
HYP.write_text(hyp)

TEST.write_text(
    '''"""Fuzzer exception contracts and exact engine invariants."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fuzz"))

import fuzz as fuzzmod  # noqa: E402
from mqttnext.enums import ConnectionState, OutboundQoSState, QoS  # noqa: E402
from mqttnext.errors import MQTTError  # noqa: E402
from mqttnext.protocol.engine import ProtocolEngine  # noqa: E402
from mqttnext.types import OutboundMessage  # noqa: E402


def test_low_level_parser_exceptions_are_not_allowed() -> None:
    assert fuzzmod.ALLOWED == (MQTTError, ConnectionError)
    assert IndexError not in fuzzmod.ALLOWED


def test_exact_mid_invariant_detects_unreserved_store_record() -> None:
    engine = ProtocolEngine()
    engine.store.put_out(
        OutboundMessage(
            mid=7,
            topic="fuzz/mid",
            payload=b"x",
            qos=QoS.AT_LEAST_ONCE,
            retain=False,
            state=OutboundQoSState.QUEUED,
        )
    )
    with pytest.raises(AssertionError, match="packet-id mismatch"):
        fuzzmod._check_engine_invariants(engine)


def test_exact_flow_invariant_detects_unaccounted_transaction() -> None:
    engine = ProtocolEngine()
    engine.state = ConnectionState.CONNECTED
    message = OutboundMessage(
        mid=9,
        topic="fuzz/flow",
        payload=b"x",
        qos=QoS.AT_LEAST_ONCE,
        retain=False,
        state=OutboundQoSState.WAIT_PUBACK,
    )
    engine.store.put_out(message)
    engine.packet_ids.reserve(message.mid)
    with pytest.raises(AssertionError, match="flow mismatch"):
        fuzzmod._check_engine_invariants(engine)
'''
)
