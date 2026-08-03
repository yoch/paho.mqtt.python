"""Audit-only real-broker subscriber profiling workload."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import subprocess
import sys
import time

from mqttnext.api import AsyncClient
from mqttnext.api.models import Message
from mqttnext.protocol.reconnect import ReconnectPolicy


def rss_mib() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


_PUBLISHER = r'''
import asyncio
import collections
import sys
import time
from mqttnext.api import AsyncClient
from mqttnext.protocol.reconnect import ReconnectPolicy

async def main():
    host, port, topic, count, qos, payload_size, window = sys.argv[1:]
    client = AsyncClient(
        client_id=f"subscriber-profile-publisher-{time.time_ns()}",
        max_outbound_inflight=int(window),
        reconnect=ReconnectPolicy(enabled=False),
    )
    await client.connect(host, int(port), timeout=10)
    payload = b"x" * int(payload_size)
    pending = collections.deque()
    try:
        for _ in range(int(count)):
            receipt = await client.publish(topic, payload, qos=int(qos))
            if int(qos):
                pending.append(receipt)
                if len(pending) >= int(window):
                    await pending.popleft().wait()
        if pending:
            await asyncio.gather(*(receipt.wait() for receipt in pending))
    finally:
        await client.disconnect()

asyncio.run(main())
'''


async def run(args: argparse.Namespace) -> dict[str, object]:
    topic = f"profile/subscriber/{os.getpid()}/{time.time_ns()}"
    client = AsyncClient(
        client_id=f"subscriber-profile-{os.getpid()}-{time.time_ns()}",
        message_delivery=args.delivery,
        max_pending_messages=max(args.count, 1024),
        max_pending_callbacks=max(args.count, 1024),
        reconnect=ReconnectPolicy(enabled=False),
    )
    received = 0
    done = asyncio.Event()

    def accept(message: Message) -> None:
        nonlocal received
        if message.topic != topic or len(message.payload) != args.payload_size:
            raise RuntimeError("subscriber received unexpected message")
        received += 1
        if received == args.count:
            done.set()

    iterator_task: asyncio.Task[None] | None = None
    if args.delivery == "callback":
        client.on_message = accept
    await client.connect(args.host, args.port, timeout=10)
    await client.subscribe(topic, qos=args.qos)
    if args.delivery == "iterator":
        async def consume() -> None:
            async for message in client.messages():
                accept(message)
                if received == args.count:
                    return
        iterator_task = asyncio.create_task(consume())

    started = time.perf_counter()
    cpu_started = time.process_time()
    publisher = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _PUBLISHER,
            args.host,
            str(args.port),
            topic,
            str(args.count),
            str(args.qos),
            str(args.payload_size),
            str(args.window),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        await asyncio.wait_for(done.wait(), timeout=args.timeout)
        return_code = await asyncio.to_thread(publisher.wait, 30)
        if return_code:
            error = publisher.stderr.read() if publisher.stderr is not None else ""
            raise RuntimeError(f"publisher failed with {return_code}: {error}")
    finally:
        if publisher.poll() is None:
            publisher.terminate()
            await asyncio.to_thread(publisher.wait)
        await client.disconnect()
        if iterator_task is not None:
            await iterator_task
    elapsed = time.perf_counter() - started
    cpu = time.process_time() - cpu_started
    return {
        "scenario": "real_broker_subscriber",
        "delivery": args.delivery,
        "qos": args.qos,
        "payload_size": args.payload_size,
        "count": received,
        "elapsed_seconds": elapsed,
        "cpu_seconds": cpu,
        "cpu_utilization_one_core": cpu / elapsed,
        "delivered_msg_s": received / elapsed,
        "cpu_us_per_message": cpu * 1_000_000 / received,
        "max_rss_mib": rss_mib(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11883)
    parser.add_argument("--delivery", choices=("callback", "iterator"), default="callback")
    parser.add_argument("--qos", type=int, choices=(0, 1), default=0)
    parser.add_argument("--payload-size", type=int, default=64)
    parser.add_argument("--count", type=int, default=50_000)
    parser.add_argument("--window", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.count <= 0 or args.payload_size <= 0 or args.window <= 0:
        parser.error("count, payload-size and window must be positive")
    return args


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run(parse_args())), sort_keys=True))
