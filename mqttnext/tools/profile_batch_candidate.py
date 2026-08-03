"""Audit-only prototype for a future publish_many API.

Uses the current private engine/client primitives to quantify the gain from
amortising the engine lock, effect collection and SQLite transaction boundaries.
It is not production code and is never imported by mqttnext.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

from mqttnext.api import AsyncClient
from mqttnext.api.models import PublishReceipt
from mqttnext.enums import QoS
from mqttnext.persistence.sqlite import SqliteInflightStore
from mqttnext.protocol.reconnect import ReconnectPolicy

TOPIC = "profile/batch/temperature"


def rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def run(args: argparse.Namespace) -> dict[str, object]:
    temp: tempfile.TemporaryDirectory[str] | None = None
    store = None
    if args.sqlite:
        temp = tempfile.TemporaryDirectory(prefix="mqttnext-batch-profile-")
        store = SqliteInflightStore(Path(temp.name) / "inflight.db")
    client = AsyncClient(
        client_id=f"batch-profile-{os.getpid()}-{time.time_ns()}",
        max_outbound_inflight=args.window,
        reconnect=ReconnectPolicy(enabled=False),
        store=store,
    )
    payload = b"x" * args.payload_size
    await client.connect(args.host, args.port, timeout=10)
    operations = 0
    started = time.perf_counter()
    cpu_started = time.process_time()
    deadline = started + args.seconds
    try:
        while time.perf_counter() < deadline:
            receipts: list[PublishReceipt] = []
            async with client._engine_lock:
                batch_factory = getattr(client._engine.store, "batch", None)
                transaction = batch_factory() if batch_factory is not None else nullcontext()
                with transaction:
                    for _ in range(args.batch_size):
                        handle = client._engine.queue_publish(
                            TOPIC,
                            payload,
                            qos=args.qos,
                        )
                        operations += 1
                        if handle.qos != QoS.AT_MOST_ONCE:
                            assert handle.mid is not None
                            receipt = PublishReceipt(
                                mid=handle.mid,
                                qos=handle.qos,
                                _event=asyncio.Event(),
                            )
                            client._receipts[handle.mid] = receipt
                            receipts.append(receipt)
                    client._collect_effects_locked()
            await client._drain_effects()
            if receipts:
                await asyncio.gather(*(receipt.wait() for receipt in receipts))
    finally:
        await client.disconnect()
        if store is not None:
            store.close()
        if temp is not None:
            temp.cleanup()
    elapsed = time.perf_counter() - started
    cpu = time.process_time() - cpu_started
    return {
        "scenario": "batch_publish_candidate",
        "qos": args.qos,
        "batch_size": args.batch_size,
        "sqlite": args.sqlite,
        "payload_size": args.payload_size,
        "operations": operations,
        "elapsed_seconds": elapsed,
        "cpu_seconds": cpu,
        "cpu_utilization_one_core": cpu / elapsed,
        "ops_per_s": operations / elapsed,
        "max_rss_mib": rss_mib(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11883)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--qos", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--payload-size", type=int, default=64)
    parser.add_argument("--sqlite", action="store_true")
    args = parser.parse_args()
    if args.seconds <= 0 or args.batch_size <= 0 or args.window <= 0:
        parser.error("seconds, batch-size and window must be positive")
    return args


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(parse_args())), sort_keys=True))
