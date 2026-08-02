from pathlib import Path

import pytest

from mqttnext.api.async_client import AsyncClient


def test_async_client_exposes_outbound_window():
    client = AsyncClient(max_outbound_inflight=7)
    assert client._engine.config.max_outbound_inflight == 7


def test_async_client_rejects_invalid_outbound_window():
    with pytest.raises(ValueError, match="max_outbound_inflight"):
        AsyncClient(max_outbound_inflight=0)


def test_benchmarks_use_real_equal_outbound_windows():
    root = Path(__file__).resolve().parents[2]
    compare = (root / "benchmarks" / "compare_libs.py").read_text()
    sprint = (root / "benchmarks" / "perf_sprint.py").read_text()
    assert "max_outbound_inflight=WINDOW" in compare
    assert "max_inflight_messages_set(WINDOW)" in compare
    assert "window = WINDOW" in compare
    assert "QoS 0 and gmqtt QoS 2 are excluded" in compare
    assert "max_outbound_inflight=outbound_window" in sprint
    assert "local_receive_maximum=local_rm" not in sprint
