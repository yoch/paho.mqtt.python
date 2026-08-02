"""Comparative benchmarks: mqttnext vs gmqtt vs paho.

Two layers:
1. Micro (CPU, no broker): PUBLISH encode + ingress decode batch
2. E2E against local Mosquitto: publisher capacity QoS 0/1/2

Run:
  PYTHONPATH=src python3 mqttnext/benchmarks/compare_libs.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# --- libraries under test -------------------------------------------------
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.enums import QoS as MqQoS
from mqttnext.packets import PublishPacket as MqPublish

from gmqtt.mqtt.constants import MQTTv311 as G_MQTTv311
from gmqtt.mqtt.package import PublishPacket as GPublish
from gmqtt.mqtt.protocol import MQTTProtocol
from gmqtt.mqtt.utils import IdGenerator

import paho.mqtt.client as mqtt


BROKER = ("127.0.0.1", 11883)
RESULTS_DIR = Path(__file__).resolve().parent / "results"


@dataclass
class Sample:
    name: str
    library: str
    ops_per_s: float
    unit: str
    notes: str = ""


def _median_ops(fn, iterations: int, runs: int = 7, warmup: int = 200) -> float:
    for _ in range(warmup):
        fn()
    rates: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        for _ in range(iterations):
            fn()
        elapsed = time.perf_counter() - t0
        rates.append(iterations / elapsed)
    return statistics.median(rates)


# ---------------------------------------------------------------------------
# Micro benches
# ---------------------------------------------------------------------------

class _GProto:
    """Minimal stub so gmqtt PublishPacket can allocate mids."""

    def __init__(self) -> None:
        self.proto_ver = G_MQTTv311
        self.id_generator = IdGenerator()


def micro_encode() -> list[Sample]:
    topic = "bench/sensors/temp"
    payload = b'{"t":21.5,"h":40}'
    samples: list[Sample] = []

    # mqttnext
    pkt = MqPublish(topic=topic, payload=payload, qos=MqQoS.AT_MOST_ONCE, retain=False, dup=False)
    rate = _median_ops(pkt.encode, 20_000)
    samples.append(Sample("publish_encode_qos0_small", "mqttnext", rate, "msg/s"))

    # gmqtt
    from gmqtt import Message as GMessage

    proto = _GProto()
    msg = GMessage(topic, payload, qos=0)

    def g_encode() -> None:
        GPublish.build_package(msg, proto)

    rate = _median_ops(g_encode, 20_000)
    samples.append(Sample("publish_encode_qos0_small", "gmqtt", rate, "msg/s"))

    # paho: publish + drain to null socket
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bench-encode")
    from paho.mqtt.enums import _ConnectionState

    client._state = _ConnectionState.MQTT_CS_CONNECTED
    client._sock = _NullSock()  # type: ignore[assignment]
    client._sockpairR, client._sockpairW = _NullSock(), _NullSock()  # type: ignore[attr-defined]

    def p_encode_drained() -> None:
        client.publish(topic, payload, qos=0)
        while client._out_messages or client._out_packet:  # type: ignore[attr-defined]
            try:
                client._packet_write()  # type: ignore[attr-defined]
            except Exception:
                client._out_packet.clear()  # type: ignore[attr-defined]
                client._out_messages.clear()  # type: ignore[attr-defined]
                break

    rate = _median_ops(p_encode_drained, 5_000, runs=5, warmup=50)
    samples.append(
        Sample(
            "publish_encode_qos0_small",
            "paho",
            rate,
            "msg/s",
            notes="publish()+_packet_write to null sock (includes queue)",
        )
    )
    return samples


class _NullSock:
    def send(self, data):  # noqa: ANN001
        return len(data)

    def recv(self, n):  # noqa: ANN001
        return b""

    def fileno(self):
        return -1

    def close(self):
        return None

    def setblocking(self, flag):  # noqa: ANN001
        return None

    def setsockopt(self, *a, **k):  # noqa: ANN001
        return None


def micro_decode() -> list[Sample]:
    samples: list[Sample] = []
    pkt = MqPublish(
        topic="bench/sensors/temp",
        payload=b'{"t":21.5}',
        qos=MqQoS.AT_MOST_ONCE,
        retain=False,
        dup=False,
    )
    wire = pkt.encode()
    blob = wire * 50

    def mq_decode() -> None:
        dec = IncrementalDecoder()
        dec.feed(blob)
        while dec.next_packet() is not None:
            pass

    rate = _median_ops(mq_decode, 3_000)
    samples.append(Sample("ingress_decode_50x_qos0_small", "mqttnext", rate, "batch/s"))

    # gmqtt parser: MQTTProtocol._read_packet expects instance; use a light shim
    from gmqtt.mqtt.handler import MqttPackageHandler

    class _H(MqttPackageHandler):
        def __init__(self):
            # Minimal init bypass — handler needs many attrs; instead call low-level
            pass

    # Use gmqtt's remaining-length style read from protocol module
    from gmqtt.mqtt import protocol as gproto

    # gmqtt buffers with buf+= ; replicate their public path via MQTTProtocol method
    # by instantiating StreamReaderProtocol-like object is heavy. Measure package
    # body parse only if easy — skip fair decode for gmqtt if too coupled.
    # Instead: time their unpack of a single publish via PublishPacket is encode-only.
    # We'll document gmqtt decode as N/A at micro level and cover it in e2e.

    samples.append(
        Sample(
            "ingress_decode_50x_qos0_small",
            "gmqtt",
            float("nan"),
            "batch/s",
            notes="no isolated decoder API; see e2e",
        )
    )
    samples.append(
        Sample(
            "ingress_decode_50x_qos0_small",
            "paho",
            float("nan"),
            "batch/s",
            notes="decoder coupled to Client loop; see e2e",
        )
    )
    _ = gproto, _H  # silence lint about unused exploratory imports
    return samples


# ---------------------------------------------------------------------------
# E2E publisher capacity
# ---------------------------------------------------------------------------

async def e2e_mqttnext(qos: int, count: int, payload: bytes) -> float:
    from mqttnext.api import AsyncClient
    from mqttnext.protocol.reconnect import ReconnectPolicy

    client = AsyncClient(
        client_id=f"mn-qos{qos}-{int(time.time()*1000)%100000}",
        keepalive=60,
        local_receive_maximum=100,
        reconnect=ReconnectPolicy(enabled=False),
    )
    await client.connect(*BROKER, timeout=5)
    t0 = time.perf_counter()
    if qos == 0:
        for _ in range(count):
            await client.publish("bench/mn", payload, qos=0)
    else:
        # Pipeline: enqueue all (engine windows at receive_maximum), then wait.
        receipts = [
            await client.publish("bench/mn", payload, qos=qos) for _ in range(count)
        ]
        await asyncio.gather(*(r.wait() for r in receipts))
    elapsed = time.perf_counter() - t0
    await client.disconnect()
    return count / elapsed


async def e2e_gmqtt(qos: int, count: int, payload: bytes) -> float:
    from gmqtt import Client as GClient

    client = GClient(f"gm-qos{qos}-{int(time.time()*1000)%100000}")
    await client.connect(*BROKER)
    # gmqtt maps Receive Maximum onto MID space — keep batches small and drain.
    window = 10
    t0 = time.perf_counter()
    if qos == 0:
        for _ in range(count):
            client.publish("bench/gm", payload, qos=0)
        await asyncio.sleep(0.05)
    else:
        for start in range(0, count, window):
            batch = min(window, count - start)
            for _ in range(batch):
                client.publish("bench/gm", payload, qos=qos)
            await asyncio.wait_for(client._persistent_storage.wait_empty(), timeout=60)
    elapsed = time.perf_counter() - t0
    await client.disconnect()
    return count / elapsed


def e2e_paho(qos: int, count: int, payload: bytes) -> float:
    done = 0
    ev = __import__("threading").Event()

    def on_publish(client, userdata, mid, reason_codes=None, properties=None):  # noqa: ANN001
        nonlocal done
        done += 1
        if done >= count:
            ev.set()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"ph-qos{qos}-{int(time.time()*1000)%100000}",
    )
    client.max_inflight_messages_set(20)
    if qos > 0:
        client.on_publish = on_publish
    client.connect(*BROKER, keepalive=60)
    client.loop_start()
    t0 = time.perf_counter()
    for i in range(count):
        while True:
            info = client.publish("bench/ph", payload, qos=qos)
            if info.rc != mqtt.MQTT_ERR_QUEUE_SIZE:
                break
            time.sleep(0.001)
    if qos == 0:
        while client._out_packet or client._out_messages:  # type: ignore[attr-defined]
            time.sleep(0.001)
        time.sleep(0.05)
    else:
        if not ev.wait(60):
            client.loop_stop()
            client.disconnect()
            raise TimeoutError(f"paho on_publish incomplete ({done}/{count})")
    elapsed = time.perf_counter() - t0
    client.loop_stop()
    client.disconnect()
    return count / elapsed


async def run_e2e() -> list[Sample]:
    samples: list[Sample] = []
    payload = b"x" * 64
    # Counts tuned for ~1–3s runs
    plans = [
        (0, 80_000),
        (1, 8_000),
        (2, 4_000),
    ]
    for qos, count in plans:
        name = f"e2e_pub_qos{qos}_p64"
        # mqttnext
        rates = []
        for _ in range(3):
            rates.append(await e2e_mqttnext(qos, count, payload))
        samples.append(Sample(name, "mqttnext", statistics.median(rates), "msg/s"))

        # gmqtt
        rates = []
        for _ in range(3):
            rates.append(await e2e_gmqtt(qos, count, payload))
        samples.append(Sample(name, "gmqtt", statistics.median(rates), "msg/s"))

        # paho
        rates = []
        for _ in range(3):
            rates.append(e2e_paho(qos, count, payload))
        samples.append(Sample(name, "paho", statistics.median(rates), "msg/s"))
    return samples


def _fmt(x: float) -> str:
    if x != x:  # NaN
        return "n/a"
    if x >= 1000:
        return f"{x:,.0f}"
    return f"{x:,.1f}"


def print_table(samples: list[Sample]) -> str:
    by_name: dict[str, dict[str, Sample]] = {}
    for s in samples:
        by_name.setdefault(s.name, {})[s.library] = s

    libs = ["mqttnext", "gmqtt", "paho"]
    lines = [
        "| Scenario | mqttnext | gmqtt | paho | mqttnext/gmqtt | mqttnext/paho |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in by_name.items():
        vals = {lib: row[lib].ops_per_s if lib in row else float("nan") for lib in libs}
        ratio_g = (
            vals["mqttnext"] / vals["gmqtt"]
            if vals["gmqtt"] == vals["gmqtt"] and vals["gmqtt"] > 0
            else float("nan")
        )
        ratio_p = (
            vals["mqttnext"] / vals["paho"]
            if vals["paho"] == vals["paho"] and vals["paho"] > 0
            else float("nan")
        )
        lines.append(
            f"| `{name}` | {_fmt(vals['mqttnext'])} | {_fmt(vals['gmqtt'])} | {_fmt(vals['paho'])} "
            f"| {_fmt(ratio_g)}× | {_fmt(ratio_p)}× |"
        )
    return "\n".join(lines)


async def amain() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_samples: list[Sample] = []
    print("=== MICRO ===")
    all_samples.extend(micro_encode())
    all_samples.extend(micro_decode())
    print("=== E2E (Mosquitto :11883) ===")
    all_samples.extend(await run_e2e())
    table = print_table(all_samples)
    print(table)
    payload = {
        "broker": list(BROKER),
        "samples": [asdict(s) for s in all_samples],
        "table_md": table,
    }
    out = RESULTS_DIR / "compare_libs.json"
    out.write_text(json.dumps(payload, indent=2))
    notes = """
Notes:
- Micro encode for paho includes queue + `_packet_write` to a null socket.
- Micro decode is mqttnext-only (gmqtt/paho parsers are not isolatable).
- E2E QoS>0: mqttnext waits PUBACK/PUBCOMP via pipelined receipts;
  gmqtt drains inflight storage in batches of 10 (Receive-Maximum MID bug);
  paho waits `on_publish`.
- gmqtt QoS2 `wait_empty` returns after PUBREC (MID freed early) — optimistic vs true PUBCOMP.
"""
    (RESULTS_DIR / "compare_libs.md").write_text(
        "# Comparative benchmarks\n\n"
        f"Broker: `{BROKER[0]}:{BROKER[1]}` (local Mosquitto)\n\n"
        f"{table}\n"
        f"{notes}\n"
    )
    print(f"\nWrote {out}")


if __name__ == "__main__":
    asyncio.run(amain())
