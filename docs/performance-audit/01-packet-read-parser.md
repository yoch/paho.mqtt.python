# 01 - Packet Read Parser

## Problem

The receive path is a probable P0 bottleneck for high-rate IoT aggregation. The
hot code paths are `Client._packet_read()` and `Client._handle_publish()` in
`src/paho/mqtt/client.py`.

Likely symptoms:

- High CPU use while receiving many small PUBLISH packets.
- Allocation pressure from repeated packet-buffer growth and packet reset.
- Repeated dictionary lookups on `_in_packet` for every byte or packet field.
- Extra copies and `struct.unpack()` calls while splitting topic, packet id,
  properties, and payload.
- Per-message UTF-8 decode attempts for logging and callback topic access.

Common workloads:

- Thousands of sensors publishing small payloads to a single subscriber.
- MQTT v5 inbound messages with empty or small properties.
- TLS sockets where fewer large reads are preferable to repeated small reads.

## Theoretical Rationale

The fixed header and remaining length parser currently performs many operations
that are cheap alone but expensive at message scale:

- Reading command and remaining length one byte at a time increases Python call
  overhead and may increase socket wrapper overhead.
- `_in_packet` is a dictionary, so field access requires hashing and lookup on
  the hottest path.
- `self._in_packet['packet'] += data` can reallocate or copy as the packet grows.
- `struct.unpack()` with dynamically built format strings allocates temporary
  objects and copies slices.
- Slicing `bytearray` creates copies for topic, packet id, properties, and
  payload extraction.

Modern CPUs are fast at sequential memory access and branch-predictable loops,
but Python-level loops, dictionary lookups, and short-lived allocations dominate
for small messages. Reducing object churn and using index-based parsing should
lower interpreter overhead and improve cache locality.

## Expected Gain

Priority: P0.

Conservative expected gain:

- 10 to 25 percent CPU reduction for small inbound QoS 0 messages.
- 5 to 15 percent throughput improvement for inbound QoS 1 due to parsing cost
  plus ACK generation.
- Lower allocation count per received message, especially for MQTT v3 payloads
  with no properties.

The largest gain should appear when payloads are small, callbacks are lightweight,
and the client is CPU-bound rather than network-bound.

## Before/After Measurements

Microbenchmarks:

- Feed prebuilt MQTT v3 PUBLISH packets into a fake socket and call
  `_packet_read()` until all messages are consumed.
- Repeat for MQTT v5 PUBLISH packets with empty properties and with common
  properties.
- Measure isolated `_handle_publish()` using prepared `_in_packet` state.
- Test payload sizes: 0 bytes, 16 bytes, 128 bytes, 1024 bytes, 64 KiB.
- Test topic lengths: 8, 32, 128 bytes.

Broker scenarios:

- Local TCP subscriber receiving QoS 0 messages with a no-op callback.
- Local TCP subscriber receiving QoS 1 messages with auto ACK.
- TLS variant for payloads >= 1024 bytes.

Metrics:

- Messages per second.
- CPU time per 100,000 messages.
- `tracemalloc` allocations per message.
- p50 and p95 callback delivery latency if broker scenario supports timestamps.

Profilers:

- `cProfile` for call counts and cumulative time.
- `py-spy` if installed for low-intrusion sampling.
- Linux `perf` if available for syscall and CPU-cycle context.

## Implementation Guidelines

Allowed implementation directions:

- Replace `_in_packet` dictionary state with a small private class using
  `__slots__`, while preserving external behavior.
- Keep a reusable input buffer object and reset fields instead of replacing the
  entire dictionary for every packet.
- Parse topic length and packet id with direct byte indexing or cached
  `struct.Struct` objects instead of dynamic format strings.
- Avoid copying payload bytes until assigning `MQTTMessage.payload`; use
  `memoryview` internally only if the final public payload remains `bytes` or
  `bytearray` as today.
- Fast-path MQTT v3 PUBLISH without properties.
- Fast-path MQTT v5 PUBLISH with property length zero.
- Keep invalid UTF-8 behavior unchanged for public `message.topic`.

Risks:

- Changing buffer lifetime can accidentally expose mutable data through
  `MQTTMessage.payload`.
- MQTT remaining length validation must remain strict.
- Partial reads and non-blocking socket behavior must keep returning
  `MQTT_ERR_AGAIN` correctly.
- TLS `pending()` behavior must not regress.

Optional Python 3.12+ note:

- Newer CPython versions improve specialization of attribute access, which makes
  `__slots__` state more attractive, but the design must still work on Python
  3.7+.

## Acceptance Criteria

Functional criteria:

- Existing unit and integration tests pass.
- Add targeted tests for partial fixed header reads, partial remaining length
  reads, partial payload reads, invalid remaining length, empty MQTT v5
  properties, and invalid topic UTF-8 behavior.
- Preserve public `MQTTMessage.topic`, `payload`, `qos`, `retain`, `mid`, and
  `properties` behavior.

Performance criteria:

- At least 10 percent lower CPU time or 10 percent higher messages/s for the
  primary small QoS 0 inbound benchmark.
- No more than 2 percent regression for large payload benchmarks.
- At least 15 percent fewer allocations per small inbound PUBLISH message.

Documentation criteria:

- Record before/after benchmark commands, environment, Python version, and
  median results in this file or a linked result file.

## Verdict

GO with conditions.

Justification: this path is central to every receiving client, and the current
implementation shows multiple interpreter-level costs in the hot loop. Proceed
only with a staged prototype and strict partial-read tests because correctness
risk is high.
