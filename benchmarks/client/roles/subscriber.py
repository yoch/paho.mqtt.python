"""
Subscriber worker process.

Usage:
  python roles/subscriber.py --config /path/config.json
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
from pathlib import Path

ROLE_DIR = Path(__file__).resolve().parent
CLIENT_DIR = ROLE_DIR.parent
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))

from control import barrier_client_wait, configure_source_root, touch, write_json  # noqa: E402
from workloads import (  # noqa: E402
    HEADER_SIZE,
    decode_header,
    fleet_topics,
    single_topic,
    unicode_topic,
    wildcard_hash,
    wildcard_plus,
    deep_topic,
    long_topic,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    paho_file = configure_source_root(cfg["source_root"])
    import paho.mqtt.client as mqtt

    run_id = cfg["run_id"]
    qos = int(cfg.get("qos_subscribe", 0))
    duration_s = float(cfg.get("duration_s", 3.0))
    warmup_s = float(cfg.get("warmup_s", 1.0))
    drain_s = float(cfg.get("drain_s", 2.0))

    state = {
        "connected": threading.Event(),
        "subscribed": threading.Event(),
        "subscriber_delivered": 0,
        "delivered_in_window": 0,
        "delivered_during_drain": 0,
        "bytes_in_window": 0,
        "callback_invocations": 0,
        "sequences": [],
        "latencies_ns": [],
        "phase": "init",
        "lock": threading.Lock(),
        "sub_mids": set(),
        "granted_ok": True,
    }

    filters = _subscription_filters(cfg, run_id)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        rc = int(getattr(reason_code, "value", reason_code))
        if rc != 0:
            return
        state["connected"].set()
        for filt in filters:
            result, mid = client.subscribe(filt, qos=qos)
            if result == mqtt.MQTT_ERR_SUCCESS and mid is not None:
                state["sub_mids"].add(mid)

    def on_subscribe(client, userdata, mid, reason_code_list, properties=None):
        # reason_code_list may be ints (v3) or ReasonCode (v5)
        ok = True
        for item in reason_code_list:
            code = int(getattr(item, "value", item))
            if code >= 128:
                ok = False
        with state["lock"]:
            state["sub_mids"].discard(mid)
            state["granted_ok"] = state["granted_ok"] and ok
            if not state["sub_mids"] and state["granted_ok"]:
                state["subscribed"].set()

    def on_message(client, userdata, msg):
        now = time.perf_counter_ns()
        with state["lock"]:
            state["subscriber_delivered"] += 1
            state["callback_invocations"] += 1
            if state["phase"] == "measure":
                state["delivered_in_window"] += 1
                state["bytes_in_window"] += len(msg.payload or b"")
                payload = msg.payload or b""
                if len(payload) >= HEADER_SIZE:
                    try:
                        hdr = decode_header(payload)
                        state["sequences"].append(hdr["sequence"])
                        send_ns = hdr["send_ns"]
                        if send_ns:
                            state["latencies_ns"].append(now - send_ns)
                    except ValueError:
                        pass
            elif state["phase"] == "drain":
                state["delivered_during_drain"] += 1

    protocol = getattr(mqtt, cfg.get("protocol", "MQTTv311"))
    client_kwargs = {
        "callback_api_version": mqtt.CallbackAPIVersion.VERSION2,
        "client_id": cfg.get("client_id", f"sub-{run_id}"),
        "protocol": protocol,
    }
    if cfg.get("protocol", "MQTTv311") != "MQTTv5":
        client_kwargs["clean_session"] = not bool(cfg.get("session_persistent", False))
    client = mqtt.Client(**client_kwargs)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    # Local callback matching.
    callback_filters = int(cfg.get("callback_filters", 0) or 0)
    overlapping = bool(cfg.get("overlapping_callbacks", False))
    if callback_filters > 0:
        topics = fleet_topics(run_id, devices=min(1024, max(1, callback_filters // 4)))
        if overlapping:
            # Multiple callbacks match the same messages via overlapping filters.
            for i in range(callback_filters):
                filt = filters[0] if filters else wildcard_hash(run_id)

                def _cb(client, userdata, msg, _i=i):
                    with state["lock"]:
                        state["callback_invocations"] += 1

                client.message_callback_add(filt, _cb)
        else:
            # One disjoint filter per callback; traffic should hit exactly one.
            chosen = topics[:callback_filters] if len(topics) >= callback_filters else topics * (callback_filters // max(len(topics), 1) + 1)
            for i in range(callback_filters):
                filt = chosen[i % len(chosen)]

                def _cb(client, userdata, msg, _i=i):
                    with state["lock"]:
                        state["callback_invocations"] += 1

                client.message_callback_add(filt, _cb)

    if cfg.get("tls"):
        client.tls_set(ca_certs=cfg["ca_certs"])

    client.connect(cfg["host"], int(cfg["port"]), keepalive=int(cfg.get("keepalive", 60)))
    client.loop_start()
    if not state["connected"].wait(30):
        write_json(cfg["result_path"], {"ok": False, "error": "connect_timeout", "paho_file": paho_file})
        client.loop_stop()
        return 1
    if not state["subscribed"].wait(30):
        write_json(cfg["result_path"], {"ok": False, "error": "subscribe_timeout", "paho_file": paho_file})
        client.loop_stop()
        return 1

    touch(cfg["ready_path"], {"role": "subscriber", "paho_file": paho_file, "pid": os.getpid(), "filters": filters})
    barrier_client_wait(cfg["barrier_path"], "T0", timeout_s=float(cfg.get("barrier_timeout_s", 120)))

    gc.collect()
    state["phase"] = "warmup"
    time.sleep(warmup_s)
    with state["lock"]:
        state["delivered_in_window"] = 0
        state["delivered_during_drain"] = 0
        state["bytes_in_window"] = 0
        state["sequences"].clear()
        state["latencies_ns"].clear()
        state["callback_invocations"] = 0

    state["phase"] = "measure"
    t0 = time.perf_counter()
    time.sleep(duration_s)
    t1 = time.perf_counter()

    state["phase"] = "drain"
    time.sleep(drain_s)

    with state["lock"]:
        delivered = state["delivered_in_window"]
        during_drain = state["delivered_during_drain"]
        bytes_in_window = state["bytes_in_window"]
        sequences = list(state["sequences"])
        latencies = list(state["latencies_ns"])
        callback_invocations = state["callback_invocations"]

    client.disconnect()
    client.loop_stop()

    window = max(t1 - t0, 1e-9)
    result = {
        "ok": True,
        "role": "subscriber",
        "paho_file": paho_file,
        "pid": os.getpid(),
        "filters": filters,
        "qos": qos,
        "t0_s": t0,
        "t1_s": t1,
        "duration_s": window,
        "subscriber_delivered": delivered,
        "delivered_during_drain": during_drain,
        "msgs_per_s": delivered / window,
        "payload_bytes_in_window": bytes_in_window,
        "payload_bytes_per_s": bytes_in_window / window,
        "callback_invocations": callback_invocations,
        "sequences": sequences[:200000],
        "latencies_ns": latencies[:50000],
    }
    write_json(cfg["result_path"], result)
    return 0


def _subscription_filters(cfg, run_id):
    kind = cfg.get("subscription", "exact")
    if kind == "exact":
        topo = cfg.get("topic_topology", "single")
        if topo == "deep32":
            return [deep_topic(run_id, 32)]
        if topo == "long_topic_256":
            return [long_topic(run_id, 256)]
        if topo == "long_topic_1024":
            return [long_topic(run_id, 1024)]
        if topo == "unicode":
            return [unicode_topic(run_id)]
        return [cfg.get("topic") or single_topic(run_id)]
    if kind == "plus":
        return [wildcard_plus(run_id)]
    if kind == "hash":
        return [wildcard_hash(run_id)]
    if kind == "multi_exact":
        count = int(cfg.get("subscription_count", 16))
        topics = fleet_topics(run_id)
        return topics[:count]
    return [cfg.get("topic") or single_topic(run_id)]


if __name__ == "__main__":
    raise SystemExit(main())
