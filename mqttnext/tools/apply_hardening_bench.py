from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).lstrip())


def main() -> None:
    write(
        "benchmarks/compare_libs.py",
        r'''
        """Comparable MQTT publisher benchmarks.

        Micro results are only shown where libraries expose equivalent isolated APIs.
        QoS 1 compares mqttnext and Paho with the same sliding window and waits for
        PUBACK. gmqtt is reported as N/A because the pinned public API has no
        equivalent per-publish completion contract.
        """

        from __future__ import annotations

        import argparse
        import asyncio
        import json
        import statistics
        import threading
        import time
        from dataclasses import asdict, dataclass
        from pathlib import Path

        import paho.mqtt.client as mqtt
        from gmqtt import Message as GMessage
        from gmqtt.mqtt.constants import MQTTv311 as G_MQTTv311
        from gmqtt.mqtt.package import PublishPacket as GPublish
        from gmqtt.mqtt.utils import IdGenerator

        from mqttnext.api import AsyncClient
        from mqttnext.codec.buffer import IncrementalDecoder
        from mqttnext.enums import QoS as MqQoS
        from mqttnext.packets import PublishPacket as MqPublish
        from mqttnext.protocol.reconnect import ReconnectPolicy


        BROKER = ("127.0.0.1", 11883)
        WINDOW = 100


        @dataclass
        class Sample:
            name: str
            library: str
            ops_per_s: float | None
            unit: str
            notes: str = ""


        def median_ops(fn, iterations: int, runs: int = 7, warmup: int = 200) -> float:
            for _ in range(warmup):
                fn()
            rates = []
            for _ in range(runs):
                started = time.perf_counter()
                for _ in range(iterations):
                    fn()
                rates.append(iterations / (time.perf_counter() - started))
            return statistics.median(rates)


        class GProto:
            def __init__(self) -> None:
                self.proto_ver = G_MQTTv311
                self.id_generator = IdGenerator()


        def micro_encode() -> list[Sample]:
            topic = "bench/sensors/temp"
            payload = b'{"t":21.5,"h":40}'
            packet = MqPublish(
                topic=topic,
                payload=payload,
                qos=MqQoS.AT_MOST_ONCE,
                retain=False,
                dup=False,
            )
            proto = GProto()
            message = GMessage(topic, payload, qos=0)
            return [
                Sample(
                    "publish_encode_qos0_small",
                    "mqttnext",
                    median_ops(packet.encode, 20_000),
                    "msg/s",
                ),
                Sample(
                    "publish_encode_qos0_small",
                    "gmqtt",
                    median_ops(lambda: GPublish.build_package(message, proto), 20_000),
                    "msg/s",
                ),
                Sample(
                    "publish_encode_qos0_small",
                    "paho",
                    None,
                    "msg/s",
                    "N/A: no isolated public codec API",
                ),
            ]


        def micro_decode() -> list[Sample]:
            wire = MqPublish(
                topic="bench/sensors/temp",
                payload=b'{"t":21.5}',
                qos=MqQoS.AT_MOST_ONCE,
                retain=False,
                dup=False,
            ).encode()
            blob = wire * 50

            def decode() -> None:
                decoder = IncrementalDecoder()
                decoder.feed(blob)
                while decoder.next_packet() is not None:
                    pass

            return [
                Sample(
                    "ingress_decode_50x_qos0_small",
                    "mqttnext",
                    median_ops(decode, 3_000),
                    "batch/s",
                ),
                Sample(
                    "ingress_decode_50x_qos0_small",
                    "gmqtt",
                    None,
                    "batch/s",
                    "N/A: decoder is coupled to the client protocol",
                ),
                Sample(
                    "ingress_decode_50x_qos0_small",
                    "paho",
                    None,
                    "batch/s",
                    "N/A: decoder is coupled to the network loop",
                ),
            ]


        async def mqttnext_puback(count: int, payload: bytes) -> float:
            client = AsyncClient(
                client_id=f"mn-{time.time_ns()}",
                max_outbound_inflight=WINDOW,
                reconnect=ReconnectPolicy(enabled=False),
            )
            await client.connect(*BROKER, timeout=5.0)
            pending = []
            started = time.perf_counter()
            for _ in range(count):
                pending.append(await client.publish("bench/mqttnext", payload, qos=1))
                if len(pending) >= WINDOW:
                    await pending.pop(0).wait()
            await asyncio.gather(*(receipt.wait() for receipt in pending))
            elapsed = time.perf_counter() - started
            await client.disconnect()
            return count / elapsed


        def paho_puback(count: int, payload: bytes) -> float:
            connected = threading.Event()
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"paho-{time.time_ns()}",
            )
            client.max_inflight_messages_set(WINDOW)
            client.max_queued_messages_set(WINDOW * 2)

            def on_connect(
                _client, _userdata, _flags, reason_code, _properties
            ) -> None:
                if reason_code == 0:
                    connected.set()

            client.on_connect = on_connect
            client.connect(*BROKER, keepalive=60)
            client.loop_start()
            if not connected.wait(5.0):
                client.loop_stop()
                raise TimeoutError("Paho did not connect")

            pending = []
            started = time.perf_counter()
            for _ in range(count):
                info = client.publish("bench/paho", payload, qos=1)
                if info.rc != mqtt.MQTT_ERR_SUCCESS:
                    client.loop_stop()
                    raise RuntimeError(f"Paho publish failed rc={info.rc}")
                pending.append(info)
                if len(pending) >= WINDOW:
                    pending.pop(0).wait_for_publish(timeout=30.0)
            for info in pending:
                info.wait_for_publish(timeout=30.0)
            elapsed = time.perf_counter() - started
            client.disconnect()
            client.loop_stop()
            return count / elapsed


        async def e2e(count: int) -> list[Sample]:
            payload = b"x" * 64
            rates = {"mqttnext": [], "paho": []}
            orders = (("mqttnext", "paho"), ("paho", "mqttnext"), ("mqttnext", "paho"))
            for order in orders:
                for library in order:
                    if library == "mqttnext":
                        rate = await mqttnext_puback(count, payload)
                    else:
                        rate = await asyncio.to_thread(paho_puback, count, payload)
                    rates[library].append(rate)
            name = f"publisher_puback_qos1_p64_w{WINDOW}"
            return [
                Sample(
                    name,
                    "mqttnext",
                    statistics.median(rates["mqttnext"]),
                    "msg/s",
                    f"count={count}; sliding window={WINDOW}",
                ),
                Sample(
                    name,
                    "gmqtt",
                    None,
                    "msg/s",
                    "N/A: no equivalent public per-publish completion contract",
                ),
                Sample(
                    name,
                    "paho",
                    statistics.median(rates["paho"]),
                    "msg/s",
                    f"count={count}; sliding window={WINDOW}",
                ),
            ]


        def markdown(samples: list[Sample]) -> str:
            rows: dict[str, dict[str, Sample]] = {}
            for sample in samples:
                rows.setdefault(sample.name, {})[sample.library] = sample
            lines = [
                "| Scenario | mqttnext | gmqtt | paho | mqttnext/paho |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
            for name, row in rows.items():
                values = {
                    library: row.get(library, Sample(name, library, None, "")).ops_per_s
                    for library in ("mqttnext", "gmqtt", "paho")
                }
                ratio = (
                    values["mqttnext"] / values["paho"]
                    if values["mqttnext"] is not None and values["paho"]
                    else None
                )

                def fmt(value: float | None) -> str:
                    if value is None:
                        return "n/a"
                    return f"{value:,.0f}" if value >= 1000 else f"{value:,.2f}"

                lines.append(
                    f"| `{name}` | {fmt(values['mqttnext'])} | "
                    f"{fmt(values['gmqtt'])} | {fmt(values['paho'])} | "
                    f"{fmt(ratio)}× |"
                )
            return "\n".join(lines)


        async def main() -> None:
            parser = argparse.ArgumentParser()
            parser.add_argument("--count", type=int, default=8_000)
            parser.add_argument("--output", type=Path, required=True)
            args = parser.parse_args()

            samples = [*micro_encode(), *micro_decode(), *(await e2e(args.count))]
            table = markdown(samples)
            payload = {
                "broker": list(BROKER),
                "window": WINDOW,
                "samples": [asdict(sample) for sample in samples],
                "table_md": table,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(payload, indent=2))
            print(table)


        if __name__ == "__main__":
            asyncio.run(main())
        ''',
    )

    write(
        "benchmarks/realworld.py",
        r'''
        """Fresh-process confirmed-delivery MQTT benchmark.

        A real ``mosquitto_sub`` process validates every payload. Publisher ACK
        throughput and subscriber delivery throughput are reported separately.
        """

        from __future__ import annotations

        import argparse
        import asyncio
        import json
        import os
        import resource
        import statistics
        import struct
        import subprocess
        import sys
        import threading
        import time
        from dataclasses import asdict, dataclass
        from pathlib import Path

        import paho.mqtt.client as mqtt

        from mqttnext.api import AsyncClient
        from mqttnext.protocol.reconnect import ReconnectPolicy


        HEADER = struct.Struct("!QQ")
        WINDOW = 100


        @dataclass
        class Result:
            library: str
            transport: str
            payload_bytes: int
            count: int
            publisher_ack_msg_s: float
            delivered_msg_s: float
            latency_p50_ms: float
            latency_p95_ms: float
            latency_p99_ms: float
            cpu_seconds: float
            max_rss_mib: float


        def percentile(values: list[float], fraction: float) -> float:
            ordered = sorted(values)
            index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
            return ordered[index]


        def start_subscriber(host: str, port: int, topic: str, count: int, cafile: str | None):
            command = [
                "mosquitto_sub",
                "-h", host,
                "-p", str(port),
                "-t", topic,
                "-q", "1",
                "-C", str(count),
                "-F", "%p",
            ]
            if cafile:
                command.extend(["--cafile", cafile])
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            arrivals: list[tuple[bytes, int]] = []

            def read() -> None:
                assert process.stdout is not None
                for line in process.stdout:
                    arrivals.append((line.rstrip(b"\n"), time.monotonic_ns()))

            thread = threading.Thread(target=read, daemon=True)
            thread.start()
            time.sleep(0.35)
            if process.poll() is not None:
                assert process.stderr is not None
                raise RuntimeError(process.stderr.read().decode(errors="replace"))
            return process, arrivals, thread


        def make_payload(sequence: int, size: int) -> bytes:
            header = HEADER.pack(sequence, time.monotonic_ns())
            return header + b"x" * max(0, size - len(header))


        async def publish_mqttnext(host: str, port: int, topic: str, count: int, size: int, context) -> float:
            client = AsyncClient(
                client_id=f"real-mn-{os.getpid()}",
                max_outbound_inflight=WINDOW,
                reconnect=ReconnectPolicy(enabled=False),
            )
            await client.connect(host, port, ssl=context, timeout=10.0)
            pending = []
            started = time.perf_counter()
            for sequence in range(count):
                pending.append(
                    await client.publish(topic, make_payload(sequence, size), qos=1)
                )
                if len(pending) >= WINDOW:
                    await pending.pop(0).wait()
            await asyncio.gather(*(receipt.wait() for receipt in pending))
            elapsed = time.perf_counter() - started
            await client.disconnect()
            return elapsed


        def publish_paho(host: str, port: int, topic: str, count: int, size: int, cafile: str | None) -> float:
            connected = threading.Event()
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"real-paho-{os.getpid()}",
            )
            client.max_inflight_messages_set(WINDOW)
            client.max_queued_messages_set(WINDOW * 2)
            if cafile:
                client.tls_set(ca_certs=cafile)

            def on_connect(_client, _userdata, _flags, reason_code, _properties) -> None:
                if reason_code == 0:
                    connected.set()

            client.on_connect = on_connect
            client.connect(host, port, keepalive=60)
            client.loop_start()
            if not connected.wait(10.0):
                raise TimeoutError("Paho did not connect")
            pending = []
            started = time.perf_counter()
            for sequence in range(count):
                info = client.publish(topic, make_payload(sequence, size), qos=1)
                if info.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise RuntimeError(f"Paho publish failed rc={info.rc}")
                pending.append(info)
                if len(pending) >= WINDOW:
                    pending.pop(0).wait_for_publish(timeout=30.0)
            for info in pending:
                info.wait_for_publish(timeout=30.0)
            elapsed = time.perf_counter() - started
            client.disconnect()
            client.loop_stop()
            return elapsed


        def child(args: argparse.Namespace) -> None:
            import ssl

            topic = f"bench/real/{args.library}/{os.getpid()}/{time.time_ns()}"
            process, arrivals, thread = start_subscriber(
                args.host, args.port, topic, args.count, args.cafile
            )
            delivery_started = time.perf_counter()
            cpu_started = time.process_time()
            if args.library == "mqttnext":
                context = ssl.create_default_context(cafile=args.cafile) if args.cafile else None
                ack_seconds = asyncio.run(
                    publish_mqttnext(
                        args.host, args.port, topic, args.count, args.payload_bytes, context
                    )
                )
            else:
                ack_seconds = publish_paho(
                    args.host, args.port, topic, args.count, args.payload_bytes, args.cafile
                )
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            thread.join(timeout=2.0)
            if len(arrivals) != args.count:
                assert process.stderr is not None
                detail = process.stderr.read().decode(errors="replace")
                raise TimeoutError(
                    f"subscriber incomplete {len(arrivals)}/{args.count}: {detail}"
                )
            delivery_seconds = time.perf_counter() - delivery_started
            latencies = []
            for raw, arrived_ns in arrivals:
                if len(raw) < HEADER.size:
                    raise RuntimeError(f"invalid payload length {len(raw)}")
                _, sent_ns = HEADER.unpack(raw[: HEADER.size])
                latencies.append((arrived_ns - sent_ns) / 1_000_000)
            usage = resource.getrusage(resource.RUSAGE_SELF)
            result = Result(
                library=args.library,
                transport="tls" if args.cafile else "tcp",
                payload_bytes=args.payload_bytes,
                count=args.count,
                publisher_ack_msg_s=args.count / ack_seconds,
                delivered_msg_s=args.count / delivery_seconds,
                latency_p50_ms=statistics.median(latencies),
                latency_p95_ms=percentile(latencies, 0.95),
                latency_p99_ms=percentile(latencies, 0.99),
                cpu_seconds=time.process_time() - cpu_started,
                max_rss_mib=usage.ru_maxrss / 1024,
            )
            print(json.dumps(asdict(result)))


        def parent(args: argparse.Namespace) -> None:
            results = []
            scenarios = ((64, args.count), (4096, max(500, args.count // 3)))
            for payload_bytes, count in scenarios:
                for library in ("mqttnext", "paho"):
                    command = [
                        sys.executable,
                        __file__,
                        "--child",
                        "--library", library,
                        "--host", args.host,
                        "--port", str(args.port),
                        "--payload-bytes", str(payload_bytes),
                        "--count", str(count),
                    ]
                    if args.cafile:
                        command.extend(["--cafile", args.cafile])
                    completed = subprocess.run(
                        command,
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    result = json.loads(completed.stdout.strip().splitlines()[-1])
                    results.append(result)
                    print(
                        f"{library:8s} {payload_bytes:5d} B "
                        f"ack={result['publisher_ack_msg_s']:9.1f} msg/s "
                        f"delivered={result['delivered_msg_s']:9.1f} msg/s "
                        f"p95={result['latency_p95_ms']:8.2f} ms"
                    )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2))


        def parse() -> argparse.Namespace:
            parser = argparse.ArgumentParser()
            parser.add_argument("--child", action="store_true")
            parser.add_argument("--library", choices=("mqttnext", "paho"))
            parser.add_argument("--host", default="127.0.0.1")
            parser.add_argument("--port", type=int, default=11883)
            parser.add_argument("--cafile")
            parser.add_argument("--payload-bytes", type=int, default=64)
            parser.add_argument("--count", type=int, default=3_000)
            parser.add_argument("--output", type=Path, default=Path("/tmp/realworld.json"))
            return parser.parse_args()


        if __name__ == "__main__":
            arguments = parse()
            if arguments.child:
                child(arguments)
            else:
                parent(arguments)
        ''',
    )

    write(
        "docs/BENCHMARKING.md",
        r'''
        # Benchmarking contract

        Benchmark results are build artefacts, not source-code claims.

        - `perf_sprint.py` detects local implementation regressions.
        - `compare_libs.py` compares only equivalent public contracts. A library is
          reported as `N/A` instead of receiving artificial synchronization barriers.
        - `realworld.py` uses fresh publisher processes plus an independent
          `mosquitto_sub`, and reports broker ACK and confirmed delivery separately.

        Every result must record Python, broker, host, payload, QoS, inflight window,
        transport, library versions, CPU, RSS and latency percentiles. PUBACK confirms
        broker acceptance; it never proves consumer delivery.

        CI uploads JSON artefacts and never commits or pushes generated numbers.
        ''',
    )

    for relative in (
        "benchmarks/results/compare_libs.json",
        "benchmarks/results/compare_libs.md",
    ):
        target = ROOT / relative
        if target.exists():
            target.unlink()

    perf = ROOT / "docs/PERF-SPRINT.md"
    text = perf.read_text()
    start = text.index("Comparatif libs (post-sprint")
    end = text.index("\n---\n", start)
    replacement = """Comparaisons inter-bibliothèques : les anciens chiffres ont été retirés,
car les contrats de complétion et les barrières du harness n'étaient pas
équivalents. Le protocole actuel est décrit dans
[`BENCHMARKING.md`](BENCHMARKING.md). Les résultats sont produits comme
artefacts CI, sans affirmation permanente dans le dépôt.
"""
    perf.write_text(text[:start] + replacement + text[end:])

    workflow = REPO / ".github/workflows/mqttnext.yml"
    workflow_text = workflow.read_text()
    marker = "run: ruff check src tests"
    if workflow_text.count(marker) != 1:
        raise RuntimeError("mqttnext Ruff marker changed")
    workflow.write_text(
        workflow_text.replace(marker, "run: ruff check src tests benchmarks", 1)
    )

    (REPO / ".github/workflows/mqttnext-benchmarks.yml").write_text(
        textwrap.dedent(
            r'''
            name: mqttnext benchmarks

            on:
              workflow_dispatch:
              schedule:
                - cron: "17 2 * * *"

            permissions:
              contents: read

            jobs:
              benchmark:
                runs-on: ubuntu-24.04
                timeout-minutes: 25
                steps:
                  - uses: actions/checkout@v4
                  - uses: actions/setup-python@v5
                    with:
                      python-version: "3.12"
                  - name: Install dependencies
                    working-directory: mqttnext
                    run: |
                      pip install -e ".[dev]" paho-mqtt==2.1.0 gmqtt==0.7.0
                      sudo apt-get update -qq
                      sudo apt-get install -y -qq mosquitto mosquitto-clients openssl
                  - name: Start TCP and TLS broker
                    run: |
                      mkdir -p /tmp/mqttnext-bench
                      openssl req -x509 -newkey rsa:2048 -nodes \
                        -keyout /tmp/mqttnext-bench/key.pem \
                        -out /tmp/mqttnext-bench/cert.pem \
                        -days 1 -subj '/CN=localhost' \
                        -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
                      chmod 0644 /tmp/mqttnext-bench/key.pem /tmp/mqttnext-bench/cert.pem
                      cat > /tmp/mqttnext-bench/mosquitto.conf <<'EOF'
                      user root
                      persistence false
                      allow_anonymous true
                      listener 11883 127.0.0.1
                      listener 18884 127.0.0.1
                      cafile /tmp/mqttnext-bench/cert.pem
                      certfile /tmp/mqttnext-bench/cert.pem
                      keyfile /tmp/mqttnext-bench/key.pem
                      require_certificate false
                      EOF
                      mosquitto -c /tmp/mqttnext-bench/mosquitto.conf -d
                      sleep 1
                  - name: Comparable publisher benchmark
                    working-directory: mqttnext
                    run: python benchmarks/compare_libs.py --output /tmp/mqttnext-bench/compare.json
                  - name: Confirmed TCP delivery benchmark
                    working-directory: mqttnext
                    run: python benchmarks/realworld.py --port 11883 --output /tmp/mqttnext-bench/realworld-tcp.json
                  - name: Confirmed TLS delivery benchmark
                    working-directory: mqttnext
                    run: |
                      python benchmarks/realworld.py \
                        --host localhost \
                        --port 18884 \
                        --cafile /tmp/mqttnext-bench/cert.pem \
                        --count 1500 \
                        --output /tmp/mqttnext-bench/realworld-tls.json
                  - uses: actions/upload-artifact@v4
                    with:
                      name: mqttnext-benchmarks
                      path: /tmp/mqttnext-bench/*.json
                      retention-days: 30
            '''
        ).lstrip()
    )


if __name__ == "__main__":
    main()
