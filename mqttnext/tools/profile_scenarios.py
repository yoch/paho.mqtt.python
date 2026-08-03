"""Focused profiling workloads for mqttnext.

This file is intentionally audit-only. It drives stable CPU and broker workloads
long enough for sampling profilers without changing production code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import tempfile
import time
import tracemalloc
from collections import deque
from pathlib import Path
from typing import Callable

from mqttnext.api import AsyncClient
from mqttnext.codec.buffer import IncrementalDecoder
from mqttnext.codec.vbi import decode_vbi
from mqttnext.dispatch.matcher import TopicMatcher
from mqttnext.enums import ConnectionState, MQTTProtocolVersion, OutboundQoSState, QoS
from mqttnext.packets import PublishPacket
from mqttnext.persistence.sqlite import SqliteInflightStore
from mqttnext.protocol.engine import EngineConfig, ProtocolEngine
from mqttnext.protocol.reconnect import ReconnectPolicy
from mqttnext.types import OutboundMessage

TOPIC = "profile/sensors/temperature"
PAYLOAD_64 = b"x" * 64


def _rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _run_timed(seconds: float, batch: Callable[[], int]) -> int:
    deadline = time.perf_counter() + seconds
    operations = 0
    while time.perf_counter() < deadline:
        operations += batch()
    return operations


def _codec_encode(seconds: float) -> int:
    packet = PublishPacket(
        topic=TOPIC,
        payload=PAYLOAD_64,
        qos=QoS.AT_LEAST_ONCE,
        retain=False,
        dup=False,
        mid=42,
    )

    def batch() -> int:
        for _ in range(10_000):
            packet.encode(MQTTProtocolVersion.MQTTv5)
        return 10_000

    return _run_timed(seconds, batch)


def _codec_decode(seconds: float) -> int:
    packet = PublishPacket(
        topic=TOPIC,
        payload=PAYLOAD_64,
        qos=QoS.AT_LEAST_ONCE,
        retain=False,
        dup=False,
        mid=42,
    )
    wire = packet.encode(MQTTProtocolVersion.MQTTv5)
    remaining, pos = decode_vbi(wire, 1)
    body = wire[pos : pos + remaining]
    flags = wire[0] & 0x0F

    def batch() -> int:
        for _ in range(5_000):
            PublishPacket.decode(flags, body, MQTTProtocolVersion.MQTTv5)
        return 5_000

    return _run_timed(seconds, batch)


def _ingress_engine(seconds: float) -> int:
    packet = PublishPacket(
        topic=TOPIC,
        payload=PAYLOAD_64,
        qos=QoS.AT_MOST_ONCE,
        retain=False,
        dup=False,
    )
    batch_wire = packet.encode(MQTTProtocolVersion.MQTTv5) * 100
    engine = ProtocolEngine(
        EngineConfig(client_id="profile-ingress", protocol=MQTTProtocolVersion.MQTTv5)
    )
    engine.state = ConnectionState.CONNECTED

    def batch() -> int:
        decoder = IncrementalDecoder()
        decoder.feed(batch_wire)
        count = 0
        while packets := decoder.drain_packets(limit=100):
            for raw in packets:
                engine.handle_raw(raw)
                count += 1
            engine.take_effects()
        return count

    return _run_timed(seconds, batch)


def _matcher(seconds: float) -> int:
    matcher = TopicMatcher()
    for index in range(250):
        matcher[f"site/{index}/device/+/reading"] = index
        matcher[f"site/{index}/#"] = index + 10_000
    matcher["site/+/device/+/reading"] = "generic"
    matcher["site/#"] = "all"
    topics = [f"site/{index % 250}/device/{index}/reading" for index in range(1_000)]

    def batch() -> int:
        matches = 0
        for topic in topics:
            matches += len(tuple(matcher.iter_match(topic)))
        if matches < len(topics):
            raise RuntimeError("matcher profile produced incomplete matches")
        return len(topics)

    return _run_timed(seconds, batch)


def _sqlite(seconds: float, *, batched: bool) -> int:
    with tempfile.TemporaryDirectory(prefix="mqttnext-profile-") as directory:
        with SqliteInflightStore(Path(directory) / "profile.db") as store:
            records = [
                OutboundMessage(
                    mid=mid,
                    topic=TOPIC,
                    payload=PAYLOAD_64,
                    qos=QoS.AT_LEAST_ONCE,
                    retain=False,
                    state=OutboundQoSState.WAIT_PUBACK,
                )
                for mid in range(1, 501)
            ]

            def cycle() -> int:
                context = store.batch() if batched else _NoopContext()
                with context:
                    for record in records:
                        store.put_out(record)
                    for record in records:
                        record.dup = not record.dup
                        store.update_out(record)
                    for record in records:
                        if store.pop_out(record.mid) is None:
                            raise RuntimeError(f"missing record mid={record.mid}")
                return len(records) * 3

            return _run_timed(seconds, cycle)


class _NoopContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False


async def _broker(
    seconds: float,
    *,
    host: str,
    port: int,
    qos: int,
    payload_size: int,
    window: int,
    cafile: str | None,
) -> int:
    import ssl

    context = ssl.create_default_context(cafile=cafile) if cafile else None
    client = AsyncClient(
        client_id=f"profile-{qos}-{os.getpid()}-{time.time_ns()}",
        max_outbound_inflight=window,
        reconnect=ReconnectPolicy(enabled=False),
    )
    await client.connect(host, port, ssl=context, timeout=10.0)
    payload = b"x" * payload_size
    pending: deque = deque()
    operations = 0
    deadline = time.perf_counter() + seconds
    try:
        while time.perf_counter() < deadline:
            for _ in range(500):
                receipt = await client.publish(TOPIC, payload, qos=qos)
                operations += 1
                if qos:
                    pending.append(receipt)
                    if len(pending) >= window:
                        await pending.popleft().wait()
            if qos:
                while len(pending) > window // 2:
                    await pending.popleft().wait()
        if qos:
            await asyncio.gather(*(receipt.wait() for receipt in pending))
    finally:
        await client.disconnect()
    return operations


def _write_tracemalloc(path: Path) -> None:
    snapshot = tracemalloc.take_snapshot()
    rows = []
    for stat in snapshot.filter_traces(
        (tracemalloc.Filter(True, "*/mqttnext/*"),)
    ).statistics("traceback")[:40]:
        rows.append(
            {
                "size_bytes": stat.size,
                "count": stat.count,
                "traceback": [str(frame) for frame in stat.traceback],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario",
        choices=(
            "codec_encode",
            "codec_decode",
            "ingress_engine",
            "matcher",
            "sqlite_batch",
            "sqlite_autocommit",
            "broker",
        ),
    )
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11883)
    parser.add_argument("--qos", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--payload-size", type=int, default=64)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--cafile")
    parser.add_argument("--tracemalloc-output", type=Path)
    args = parser.parse_args()
    if args.seconds <= 0 or args.payload_size <= 0 or args.window <= 0:
        parser.error("seconds, payload-size and window must be positive")
    return args


def main() -> None:
    args = parse_args()
    if args.tracemalloc_output:
        tracemalloc.start(25)
    started = time.perf_counter()
    cpu_started = time.process_time()
    if args.scenario == "codec_encode":
        operations = _codec_encode(args.seconds)
    elif args.scenario == "codec_decode":
        operations = _codec_decode(args.seconds)
    elif args.scenario == "ingress_engine":
        operations = _ingress_engine(args.seconds)
    elif args.scenario == "matcher":
        operations = _matcher(args.seconds)
    elif args.scenario == "sqlite_batch":
        operations = _sqlite(args.seconds, batched=True)
    elif args.scenario == "sqlite_autocommit":
        operations = _sqlite(args.seconds, batched=False)
    else:
        operations = asyncio.run(
            _broker(
                args.seconds,
                host=args.host,
                port=args.port,
                qos=args.qos,
                payload_size=args.payload_size,
                window=args.window,
                cafile=args.cafile,
            )
        )
    elapsed = time.perf_counter() - started
    cpu_seconds = time.process_time() - cpu_started
    if args.tracemalloc_output:
        _write_tracemalloc(args.tracemalloc_output)
    print(
        json.dumps(
            {
                "scenario": args.scenario,
                "operations": operations,
                "elapsed_seconds": elapsed,
                "cpu_seconds": cpu_seconds,
                "ops_per_s": operations / elapsed,
                "cpu_utilization_one_core": cpu_seconds / elapsed,
                "max_rss_mib": _rss_mib(),
                "qos": args.qos if args.scenario == "broker" else None,
                "payload_size": args.payload_size if args.scenario == "broker" else None,
                "window": args.window if args.scenario == "broker" else None,
                "transport": "tls" if args.cafile else "tcp",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
