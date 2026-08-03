from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import platform
import resource
import select
import statistics
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
TCP_PORT = 11883
TLS_PORT = 18884
TIMEOUT = 120.0


@dataclass(frozen=True)
class Scenario:
    name: str
    qos: int
    payload_size: int
    count: int
    window: int
    tls: bool = False
    delay_ms: int = 0
    loss_percent: float = 0.0


SCENARIOS = (
    Scenario("tcp_qos1_64b", qos=1, payload_size=64, count=6000, window=100),
    Scenario("tcp_qos1_4k", qos=1, payload_size=4096, count=2500, window=100),
    Scenario("tcp_qos2_64b", qos=2, payload_size=64, count=2500, window=100),
    Scenario("tls_qos1_64b", qos=1, payload_size=64, count=4000, window=100, tls=True),
    Scenario(
        "wan20_qos1_64b",
        qos=1,
        payload_size=64,
        count=1500,
        window=100,
        delay_ms=10,
    ),
    Scenario(
        "wan80_loss02_qos1_64b",
        qos=1,
        payload_size=64,
        count=800,
        window=100,
        delay_ms=40,
        loss_percent=0.2,
    ),
)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def payload_for(seq: int, size: int) -> bytes:
    prefix = f"{time.monotonic_ns()}:{seq}:".encode("ascii")
    if len(prefix) >= size:
        return prefix
    return prefix + b"x" * (size - len(prefix))


def wait_subscribed(proc: subprocess.Popen[bytes]) -> None:
    assert proc.stderr is not None
    deadline = time.monotonic() + 8.0
    collected: list[bytes] = []
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        readable, _, _ = select.select([proc.stderr], [], [], max(0.0, remaining))
        if not readable:
            break
        line = proc.stderr.readline()
        if not line:
            break
        collected.append(line)
        if b"received SUBACK" in line:
            return
    proc.kill()
    detail = b"".join(collected).decode("utf-8", errors="replace")
    raise RuntimeError(f"subscriber did not confirm SUBACK: {detail}")


def start_subscriber(
    *, topic: str, qos: int, count: int, port: int, cafile: str | None
) -> tuple[subprocess.Popen[bytes], threading.Event, list[float], list[str]]:
    command = [
        "mosquitto_sub",
        "-d",
        "-h",
        HOST,
        "-p",
        str(port),
        "-t",
        topic,
        "-q",
        str(qos),
        "-C",
        str(count),
        "-F",
        "%p",
    ]
    if cafile is not None:
        command.extend(["--cafile", cafile])
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    wait_subscribed(proc)
    assert proc.stdout is not None
    finished = threading.Event()
    latencies_ms: list[float] = []
    errors: list[str] = []

    def read_messages() -> None:
        try:
            for _ in range(count):
                line = proc.stdout.readline()
                if not line:
                    errors.append("subscriber stdout ended before expected count")
                    return
                try:
                    sent_ns = int(line.split(b":", 1)[0])
                except (ValueError, IndexError):
                    errors.append(f"invalid payload prefix: {line[:80]!r}")
                    return
                latencies_ms.append((time.monotonic_ns() - sent_ns) / 1_000_000)
        finally:
            finished.set()

    threading.Thread(target=read_messages, name="audit-subscriber-reader", daemon=True).start()
    return proc, finished, latencies_ms, errors


def usage_snapshot() -> tuple[float, float, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime, usage.ru_stime, usage.ru_maxrss


async def publish_mqttnext(
    *, topic: str, scenario: Scenario, cafile: str | None
) -> float:
    import ssl

    from mqttnext.api import AsyncClient
    from mqttnext.protocol.reconnect import ReconnectPolicy

    tls_context = None
    if scenario.tls:
        assert cafile is not None
        tls_context = ssl.create_default_context(cafile=cafile)
    client = AsyncClient(
        client_id=f"audit-mn-{uuid.uuid4().hex[:10]}",
        max_outbound_inflight=scenario.window,
        max_outbound_messages=max(10_000, scenario.count + 100),
        reconnect=ReconnectPolicy(enabled=False),
    )
    await client.connect(
        HOST,
        TLS_PORT if scenario.tls else TCP_PORT,
        ssl=tls_context,
        timeout=10.0,
    )
    try:
        receipts = []
        for seq in range(scenario.count):
            receipt = await client.publish(
                topic,
                payload_for(seq, scenario.payload_size),
                qos=scenario.qos,
            )
            if scenario.qos:
                receipts.append(receipt)
        if receipts:
            await asyncio.wait_for(
                asyncio.gather(*(receipt.wait() for receipt in receipts)),
                timeout=TIMEOUT,
            )
        return time.perf_counter()
    finally:
        await client.disconnect()


def publish_paho(*, topic: str, scenario: Scenario, cafile: str | None) -> float:
    import paho.mqtt.client as mqtt

    connected = threading.Event()
    acknowledged = threading.Event()
    published = 0

    def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        connected.set()

    def on_publish(client: Any, userdata: Any, mid: int, reason_code: Any, properties: Any) -> None:
        nonlocal published
        published += 1
        if published >= scenario.count:
            acknowledged.set()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"audit-ph-{uuid.uuid4().hex[:10]}",
    )
    client.max_inflight_messages_set(scenario.window)
    client.on_connect = on_connect
    if scenario.qos:
        client.on_publish = on_publish
    if scenario.tls:
        assert cafile is not None
        client.tls_set(ca_certs=cafile)
    client.connect(HOST, TLS_PORT if scenario.tls else TCP_PORT, keepalive=60)
    client.loop_start()
    try:
        if not connected.wait(10.0):
            raise TimeoutError("Paho connect timeout")
        for seq in range(scenario.count):
            info = client.publish(
                topic,
                payload_for(seq, scenario.payload_size),
                qos=scenario.qos,
            )
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"Paho publish failed rc={info.rc}")
        if scenario.qos and not acknowledged.wait(TIMEOUT):
            raise TimeoutError(f"Paho acknowledgements incomplete: {published}/{scenario.count}")
        return time.perf_counter()
    finally:
        client.disconnect()
        client.loop_stop()


def run_child(args: argparse.Namespace) -> None:
    scenario = Scenario(
        name=args.scenario,
        qos=args.qos,
        payload_size=args.payload_size,
        count=args.count,
        window=args.window,
        tls=args.tls,
        delay_ms=args.delay_ms,
        loss_percent=args.loss_percent,
    )
    topic = f"audit/{scenario.name}/{args.library}/{uuid.uuid4().hex}"
    port = TLS_PORT if scenario.tls else TCP_PORT
    cafile = args.cafile if scenario.tls else None
    subscriber, received, latencies_ms, subscriber_errors = start_subscriber(
        topic=topic,
        qos=scenario.qos,
        count=scenario.count,
        port=port,
        cafile=cafile,
    )
    before_user, before_system, _ = usage_snapshot()
    started = time.perf_counter()
    try:
        if args.library == "mqttnext":
            ack_completed = asyncio.run(
                publish_mqttnext(topic=topic, scenario=scenario, cafile=cafile)
            )
        elif args.library == "paho":
            ack_completed = publish_paho(topic=topic, scenario=scenario, cafile=cafile)
        else:
            raise ValueError(args.library)
        if not received.wait(TIMEOUT):
            raise TimeoutError(
                f"subscriber incomplete: {len(latencies_ms)}/{scenario.count}"
            )
        if subscriber_errors:
            raise RuntimeError("; ".join(subscriber_errors))
        subscriber.wait(timeout=10.0)
        completed = time.perf_counter()
    finally:
        if subscriber.poll() is None:
            subscriber.kill()
            subscriber.wait(timeout=5.0)
    after_user, after_system, max_rss = usage_snapshot()
    wall_s = completed - started
    ack_s = ack_completed - started
    cpu_s = (after_user - before_user) + (after_system - before_system)
    result = {
        "library": args.library,
        "scenario": asdict(scenario),
        "wall_s": wall_s,
        "ack_s": ack_s,
        "throughput_msg_s": scenario.count / wall_s,
        "publisher_cpu_s": cpu_s,
        "messages_per_cpu_s": scenario.count / cpu_s if cpu_s > 0 else None,
        "publisher_max_rss_mib": max_rss / 1024,
        "latency_ms": {
            "p50": percentile(latencies_ms, 0.50),
            "p95": percentile(latencies_ms, 0.95),
            "p99": percentile(latencies_ms, 0.99),
            "max": max(latencies_ms),
        },
        "received": len(latencies_ms),
    }
    print(json.dumps(result, sort_keys=True), flush=True)


def set_netem(delay_ms: int, loss_percent: float) -> None:
    subprocess.run(
        ["sudo", "tc", "qdisc", "del", "dev", "lo", "root"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if delay_ms <= 0 and loss_percent <= 0:
        return
    command = ["sudo", "tc", "qdisc", "add", "dev", "lo", "root", "netem"]
    if delay_ms > 0:
        command.extend(["delay", f"{delay_ms}ms"])
    if loss_percent > 0:
        command.extend(["loss", f"{loss_percent}%"])
    subprocess.run(command, check=True)


def run_measurement(
    *, library: str, scenario: Scenario, cafile: str, repetition: int
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        "--library",
        library,
        "--scenario",
        scenario.name,
        "--qos",
        str(scenario.qos),
        "--payload-size",
        str(scenario.payload_size),
        "--count",
        str(scenario.count),
        "--window",
        str(scenario.window),
        "--delay-ms",
        str(scenario.delay_ms),
        "--loss-percent",
        str(scenario.loss_percent),
        "--cafile",
        cafile,
    ]
    if scenario.tls:
        command.append("--tls")
    completed = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
        timeout=TIMEOUT + 30,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"no benchmark output; stderr={completed.stderr}")
    result = json.loads(lines[-1])
    result["repetition"] = repetition
    return result


def aggregate(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in raw:
        key = (row["scenario"]["name"], row["library"])
        grouped.setdefault(key, []).append(row)
    result: list[dict[str, Any]] = []
    for (scenario_name, library), rows in sorted(grouped.items()):
        def med(path: tuple[str, ...]) -> float:
            values: list[float] = []
            for row in rows:
                value: Any = row
                for key in path:
                    value = value[key]
                values.append(float(value))
            return statistics.median(values)

        result.append(
            {
                "scenario": scenario_name,
                "library": library,
                "runs": len(rows),
                "throughput_msg_s": med(("throughput_msg_s",)),
                "publisher_cpu_s": med(("publisher_cpu_s",)),
                "messages_per_cpu_s": med(("messages_per_cpu_s",)),
                "publisher_max_rss_mib": med(("publisher_max_rss_mib",)),
                "latency_ms": {
                    "p50": med(("latency_ms", "p50")),
                    "p95": med(("latency_ms", "p95")),
                    "p99": med(("latency_ms", "p99")),
                    "max": med(("latency_ms", "max")),
                },
            }
        )
    return result


def environment() -> dict[str, Any]:
    versions = {}
    for package in ("mqttnext", "paho-mqtt"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    cpu = subprocess.run(
        ["lscpu"], text=True, capture_output=True, check=False
    ).stdout
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "cpu": cpu,
        "packages": versions,
        "commit": os.environ.get("GITHUB_SHA"),
    }


def run_parent(args: argparse.Namespace) -> None:
    raw: list[dict[str, Any]] = []
    try:
        for scenario in SCENARIOS:
            set_netem(scenario.delay_ms, scenario.loss_percent)
            orders = (("mqttnext", "paho"), ("paho", "mqttnext"), ("mqttnext", "paho"))
            for repetition, order in enumerate(orders, start=1):
                for library in order:
                    row = run_measurement(
                        library=library,
                        scenario=scenario,
                        cafile=args.cafile,
                        repetition=repetition,
                    )
                    raw.append(row)
                    print(
                        f"{scenario.name:26s} {library:8s} "
                        f"{row['throughput_msg_s']:10.1f} msg/s "
                        f"p95={row['latency_ms']['p95']:8.2f} ms "
                        f"cpu={row['publisher_cpu_s']:6.3f}s "
                        f"rss={row['publisher_max_rss_mib']:6.1f} MiB",
                        flush=True,
                    )
    finally:
        set_netem(0, 0.0)
    payload = {
        "environment": environment(),
        "method": {
            "subscriber": "mosquitto_sub, unique topic, exact received count",
            "completion": "max(all publisher acknowledgements, all subscriber deliveries)",
            "process_isolation": "fresh Python process per library/run",
            "runs": 3,
            "order": "alternating",
            "netem": "delay/loss applied to loopback after broker startup",
        },
        "aggregate": aggregate(raw),
        "raw": raw,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("REALWORLD_RESULT_BEGIN")
    print(json.dumps(payload, sort_keys=True))
    print("REALWORLD_RESULT_END")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--library", choices=("mqttnext", "paho"))
    parser.add_argument("--scenario", default="")
    parser.add_argument("--qos", type=int, default=1)
    parser.add_argument("--payload-size", type=int, default=64)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--tls", action="store_true")
    parser.add_argument("--delay-ms", type=int, default=0)
    parser.add_argument("--loss-percent", type=float, default=0.0)
    parser.add_argument("--cafile", required=True)
    parser.add_argument("--output", default="/tmp/mqttnext-realworld.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.child:
        if args.library is None:
            raise SystemExit("--library is required with --child")
        run_child(args)
    else:
        run_parent(args)


if __name__ == "__main__":
    main()
