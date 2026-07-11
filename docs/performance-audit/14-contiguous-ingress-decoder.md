# 14 - Contiguous Ingress Decoder

## Analysis

Project 09 removed most kernel reads from small inbound bursts, but the packet
parser still consumes the private read-ahead buffer through separate logical
reads for the command byte, Remaining Length, and packet body. Each completed
packet therefore crosses `_sock_recv_read_ahead()` several times and creates
small slices even when all bytes are already contiguous in memory.

The built-in loop can instead parse MQTT framing directly from a bounded byte
arena. A cursor can locate the command, decode the one-to-four-byte Remaining
Length, verify that the full packet is present, and dispatch a view of its body.
Only data that must outlive dispatch, notably `MQTTMessage.payload`, needs an
owned copy.

The public `loop_read(max_packets)` path has a separate issue: its argument is
currently overwritten by the number of tracked QoS messages. A caller asking
for a larger batch therefore still processes one packet in a QoS 0 workload.
This existing argument can be honored without enabling read-ahead that could
strand prefetched bytes outside the external event loop's readiness model.

## Preparation

- Preserve the current packet-at-a-time parser as the reference implementation
  during paired measurements.
- Add a brokerless contiguous-stream source that exposes 1, 10, 100, and 1,000
  MQTT v3 and v5 PUBLISH packets in one receive buffer.
- Add local socketpair TCP-equivalent and TLS scenarios with partial reads of
  1, 2, 7, 128, and 65,536 bytes.
- Measure `loop_read(1)`, `loop_read(100)`, and the private built-in batch path
  separately.
- Record parser calls, buffer slices/copies, `recv()` calls, CPU, allocations,
  throughput, p50, and p95 latency.
- Keep WebSocket framing out of this project; project 21 owns that transport.

## Expected Gain

Priority: P0.

- 15 to 30 percent higher small-PUBLISH throughput after project 09.
- Lower allocation and function-call counts per packet.
- At least 20 percent higher external-loop burst throughput when callers use
  the already-existing `max_packets` argument.
- Neutral behavior for isolated packets and large payloads.

## Acceptance Criteria

- At least 15 percent higher throughput for 1,000 small TCP/Unix PUBLISH
  packets in the built-in loop.
- At least 10 percent higher throughput for the equivalent TLS burst.
- At least 20 percent higher throughput and 80 percent fewer readiness
  callbacks for `loop_read(100)` versus `loop_read(1)`.
- No regression above 2 percent for 64-KiB payloads.
- No p95 latency regression above 5 percent for one isolated message.
- The default `loop_read(1)` preserves the current effective QoS behavior; the
  effective limit is `max(requested, tracked QoS work, 1)`.
- Remaining Length overflow, non-minimal/truncated encodings, partial packets,
  reconnect buffer reset, TLS `pending()`, and the 100-packet fairness ceiling
  remain correct.
- Retained arena capacity is bounded by the largest active packet plus a
  64-KiB read window, and historical traffic cannot grow it indefinitely.

## Before Measurement

Pending. Measure current HEAD before any production edit, with 2 warmups and 7
runs for exploration, then 15 runs for the accepted comparison.

Required baseline rows:

| Scenario | Throughput | p95 | Allocations | `recv` / parser calls |
| --- | ---: | ---: | ---: | ---: |
| Built-in TCP, 1,000 small v3 PUBLISH | pending | pending | pending | pending |
| Built-in TLS, 1,000 small v3 PUBLISH | pending | pending | pending | pending |
| External `loop_read(1)` | pending | pending | pending | pending |
| External `loop_read(100)` | pending | pending | pending | pending |
| Built-in TCP, 64-KiB PUBLISH | pending | pending | pending | pending |

## Implementation

Planned prototype:

- Add a private contiguous ingress arena with start/end cursors and thresholded
  compaction.
- Decode fixed headers directly from the arena and dispatch complete packet
  bodies through a short-lived read-only view.
- Release all views before compacting or extending a `bytearray`.
- Keep payload ownership and all public `MQTTMessage` types unchanged.
- Retain the existing exact-read parser for public external-loop calls, but
  honor a larger `max_packets` request.
- Reset all arena state on close, reconnect, protocol error, and reinitialise.
- Remove the prototype completely if any primary threshold fails.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Separate gains caused by fewer Python calls/copies from gains caused
by external-loop batching. Report TCP, TLS, Unix, small-packet, and large-packet
results independently.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
