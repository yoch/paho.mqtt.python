# 07 - WebSocket Transport

## Problem

The WebSocket transport adds a Python-level framing layer around MQTT packets.
The relevant code is `_WebsocketWrapper` in `src/paho/mqtt/client.py`.

Likely symptoms:

- WebSocket transport uses much more CPU than TCP for the same MQTT workload.
- `_create_frame()` masks payloads byte by byte in Python.
- `_recv_impl()` performs buffer slicing, bytearray mutation, and frame parsing
  on every read.
- Handshake parsing reads one byte at a time, though this is connection-time
  only and not a steady-state hot path.
- Send buffering copies data into `_sendbuffer`.

Common workloads:

- Browser-adjacent or proxy-constrained MQTT clients using WebSocket transport.
- Cloud broker connections where WebSocket is required.
- Small telemetry messages where framing overhead dominates payload size.

## Theoretical Rationale

WebSocket client masking is required by the protocol, but byte-by-byte Python
loops are expensive. Masking is a simple XOR pattern that CPUs execute quickly,
but Python loop overhead dominates. Reducing loop iterations, using chunked
operations, or minimizing copies can help.

The transport is P2 because not all deployments use WebSockets, but for users
who do, the overhead can be large relative to MQTT packet processing.

## Expected Gain

Priority: P2.

Conservative expected gain:

- 10 to 30 percent CPU reduction in isolated WebSocket frame masking benchmarks.
- 5 to 15 percent throughput improvement for small WebSocket MQTT messages.
- Little impact for raw TCP users.

The gain depends heavily on payload size and whether the workload is send-heavy
or receive-heavy.

## Before/After Measurements

Microbenchmarks:

- Create masked WebSocket frames for MQTT packet sizes 2, 16, 128, 1024, and
  65536 bytes.
- Receive/decode WebSocket frames for the same sizes.
- Measure partial-send behavior with `_sendbuffer`.
- Compare handshake parsing only as informational, not as a P2 acceptance
  target.

Broker scenarios:

- WebSocket QoS 0 publish throughput.
- WebSocket subscriber receiving small telemetry.
- WebSocket over TLS if a local test broker supports it.

Metrics:

- Frames per second.
- CPU per MiB framed.
- Allocations per frame.
- MQTT messages per second over WebSocket vs raw TCP.

## Implementation Guidelines

Allowed implementation directions:

- Optimize masking with chunked operations while staying pure Python and
  dependency-free.
- Avoid mutating caller-provided buffers in place unless the current behavior
  already guarantees isolation.
- Reduce temporary frame concatenations by extending one `bytearray`.
- Improve receive buffering to avoid full-buffer resets and copies when partial
  frames are read.
- Consider faster handshake parsing only if profiling shows connection churn is
  a real workload.

Risks:

- WebSocket masking correctness is protocol-critical.
- Partial frames and continuation frames are already delicate.
- Changing buffer ownership can corrupt retransmission or partial-send behavior.
- Large-payload optimizations must not slow small frames.

## Acceptance Criteria

Functional criteria:

- Existing WebSocket unit and integration tests pass.
- Add tests for masking correctness, partial sends, ping/pong handling, close
  frames, and continuation behavior covered by current support.
- Preserve public transport selection behavior.

Performance criteria:

- At least 15 percent faster frame creation for 128-byte payloads.
- At least 10 percent lower CPU in WebSocket small-message broker scenario.
- No regression above 2 percent for raw TCP benchmarks.

Documentation criteria:

- Record WebSocket vs raw TCP overhead before and after.
- Document which frame sizes benefit.

## Verdict

GO with conditions.

Justification: the optimization target is clear, but WebSocket affects a subset
of users and protocol edge cases are easy to break. Proceed after P0/P1 work or
when WebSocket-heavy users provide profiles.
