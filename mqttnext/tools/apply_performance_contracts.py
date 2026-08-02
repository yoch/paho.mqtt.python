from pathlib import Path

CLIENT = Path("mqttnext/src/mqttnext/api/async_client.py")
SPRINT = Path("mqttnext/benchmarks/perf_sprint.py")
COMPARE = Path("mqttnext/benchmarks/compare_libs.py")
TEST = Path("mqttnext/tests/unit/test_performance_contracts.py")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


client = CLIENT.read_text()
client = replace_once(
    client,
    "        local_receive_maximum: int = 100,\n        connect_properties: Properties | None = None,\n",
    "        local_receive_maximum: int = 100,\n        max_outbound_inflight: int | None = None,\n        connect_properties: Properties | None = None,\n",
    "public outbound window",
)
client = replace_once(
    client,
    "                local_receive_maximum=local_receive_maximum,\n                connect_properties=connect_properties,\n",
    "                local_receive_maximum=local_receive_maximum,\n                max_outbound_inflight=max_outbound_inflight,\n                connect_properties=connect_properties,\n",
    "engine outbound window",
)
CLIENT.write_text(client)

sprint = SPRINT.read_text()
sprint = sprint.replace(
    "  D  pipeline_rm                  (e2e QoS1/2 vs local_receive_maximum)",
    "  D  pipeline_window              (e2e QoS1/2 vs max_outbound_inflight)",
)
sprint = replace_once(
    sprint,
    "async def _e2e_pub(qos: int, count: int, payload: bytes, *, local_rm: int = 20) -> float:\n",
    "async def _e2e_pub(\n    qos: int, count: int, payload: bytes, *, outbound_window: int = 20\n) -> float:\n",
    "sprint signature",
)
sprint = replace_once(
    sprint,
    "        client_id=f\"sprint-q{qos}-rm{local_rm}-{time.time_ns() % 1_000_000}\",\n        local_receive_maximum=local_rm,\n",
    "        client_id=f\"sprint-q{qos}-w{outbound_window}-{time.time_ns() % 1_000_000}\",\n        local_receive_maximum=100,\n        max_outbound_inflight=outbound_window,\n",
    "sprint window config",
)
sprint = sprint.replace("local_rm=20", "outbound_window=20")
sprint = sprint.replace("_rm20", "_w20")
sprint = sprint.replace("    rms = (20, 100, 500, 2000)\n", "    windows = (20, 100, 500, 2000)\n")
sprint = sprint.replace("            for rm in rms:\n", "            for window in windows:\n")
sprint = sprint.replace("local_rm=rm", "outbound_window=window")
sprint = sprint.replace("_rm{rm}", "_w{window}")
sprint = sprint.replace('print("=== Track D: pipeline RM ===")', 'print("=== Track D: outbound inflight window ===")')
SPRINT.write_text(sprint)

compare = COMPARE.read_text()
compare = compare.replace(
    "2. E2E against local Mosquitto: publisher capacity QoS 0/1/2",
    "2. E2E against local Mosquitto: QoS 1 PUBACK-complete throughput",
)
compare = compare.replace(
    'RESULTS_DIR = Path(__file__).resolve().parent / "results"\n',
    'RESULTS_DIR = Path(__file__).resolve().parent / "results"\nWINDOW = 20\n',
)
start = compare.index("    # paho: publish + drain to null socket\n")
end = compare.index("    return samples\n", start)
compare = compare[:start] + '''    samples.append(
        Sample(
            "publish_encode_qos0_small",
            "paho",
            float("nan"),
            "msg/s",
            notes="N/A: public publish includes queue and I/O; not a codec benchmark",
        )
    )
''' + compare[end:]
compare = compare.replace("        local_receive_maximum=100,\n", "        max_outbound_inflight=WINDOW,\n")
compare = compare.replace("    window = 10\n", "    window = WINDOW\n")
compare = compare.replace("    client.max_inflight_messages_set(20)\n", "    client.max_inflight_messages_set(WINDOW)\n")
run_start = compare.index("async def run_e2e() -> list[Sample]:\n")
run_end = compare.index("\n\ndef _fmt", run_start)
new_run = '''async def run_e2e() -> list[Sample]:
    samples: list[Sample] = []
    payload = b"x" * 64
    qos = 1
    count = 8_000
    rates: dict[str, list[float]] = {"mqttnext": [], "gmqtt": [], "paho": []}
    orders = (
        ("mqttnext", "gmqtt", "paho"),
        ("gmqtt", "paho", "mqttnext"),
        ("paho", "mqttnext", "gmqtt"),
    )
    for order in orders:
        for library in order:
            if library == "mqttnext":
                rate = await e2e_mqttnext(qos, count, payload)
            elif library == "gmqtt":
                rate = await e2e_gmqtt(qos, count, payload)
            else:
                rate = await asyncio.to_thread(e2e_paho, qos, count, payload)
            rates[library].append(rate)

    name = f"e2e_puback_qos1_p64_w{WINDOW}"
    for library in ("mqttnext", "gmqtt", "paho"):
        samples.append(
            Sample(
                name,
                library,
                statistics.median(rates[library]),
                "msg/s",
                notes=f"count={count}; PUBACK complete; inflight window={WINDOW}",
            )
        )
    return samples
'''
compare = compare[:run_start] + new_run + compare[run_end:]
compare = compare.replace(
    "- E2E QoS>0: mqttnext waits PUBACK/PUBCOMP via pipelined receipts;\n  gmqtt drains inflight storage in batches of 10 (Receive-Maximum MID bug);\n  paho waits `on_publish`.\n- gmqtt QoS2 `wait_empty` returns after PUBREC (MID freed early) — optimistic vs true PUBCOMP.\n",
    "- Comparative E2E is limited to QoS 1, completed after PUBACK.\n- All libraries use the same outbound inflight window.\n- Execution order rotates between runs to reduce warm-up/order bias.\n- QoS 0 and gmqtt QoS 2 are excluded because completion semantics differ.\n",
)
COMPARE.write_text(compare)

TEST.write_text('''from pathlib import Path

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
''')
