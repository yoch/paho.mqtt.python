# 16 - Transport-Aware Batched Writer

## Analysis

`_packet_write()` already drains multiple queued packets, but each packet still
causes a separate `_sock_send()` call. This is expensive for four-byte ACKs and
small telemetry PUBLISH packets, and it prevents the socket, TLS layer, and
WebSocket wrapper from amortizing Python calls and framing work.

A transport-aware writer can submit only data that is already queued, without
waiting for a batch to fill. Plain POSIX sockets can use scatter/gather I/O;
TLS and WebSocket require bounded contiguous coalescence. Completion must still
be accounted per MQTT packet after partial writes.

## Preparation

- Add queue depths 1, 2, 8, 64, 100, and 1,000.
- Measure PUBACK/PUBCOMP and PUBLISH payloads of 16 B, 128 B, 1 KiB, and 64 KiB.
- Exercise TCP, Unix, TLS, WebSocket, and a fallback socket without `sendmsg()`.
- Add fake transports that accept 1 byte, cross exactly one packet boundary,
  cross several boundaries, return EAGAIN, and fail after a partial batch.
- Count Python send calls, kernel sends, TLS writes/records where observable,
  WebSocket frames, CPU, allocations, temporary bytes, throughput, and p95.

## Expected Gain

Priority: P0.

- At least 15 percent higher small-packet TCP throughput.
- At least 20 percent higher small-packet TLS throughput.
- At least 80 percent fewer network-write calls at queue depth 100.
- Lower frame and masking overhead for queued WebSocket packets.

## Acceptance Criteria

- At least 80 percent fewer calls to the underlying write primitive for 100
  queued small packets.
- At least 15 percent higher TCP/Unix throughput and 20 percent higher TLS
  throughput in their primary small-packet scenarios.
- No throughput regression above 3 percent for one isolated packet.
- No regression above 2 percent for 64-KiB PUBLISH packets.
- Temporary coalescing memory stays below 128 KiB per client.
- TCP/Unix `sendmsg()` batches are limited to 64 iovecs or 64 KiB, whichever
  comes first; TLS coalescence is limited to 16 KiB.
- No timer or delay is introduced to wait for more work.
- Partial-write positions, QoS 0 completion, callback order, `MQTTMessageInfo`,
  DISCONNECT close timing, EAGAIN, reconnect, and external write registration
  remain correct.
- Each transport may fall back independently if it fails its threshold.

## Before Measurement

Pending. Measure current one-send-per-packet behavior before changing the queue
or writer.

Required baseline rows:

| Transport | Packets | Size | Throughput | Underlying writes | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| TCP | 100 | 128 B | pending | pending | pending |
| Unix | 100 | 128 B | pending | pending | pending |
| TLS | 100 | 128 B | pending | pending | pending |
| WebSocket | 100 | 128 B | pending | pending | pending |
| TCP | 1 | 64 KiB | pending | pending | pending |

## Implementation

Planned prototype:

- Add a private writer backend selected from socket/transport capabilities.
- Use `socket.sendmsg()` for bounded TCP/Unix batches when available on the
  supported platform.
- Use bounded `bytearray` coalescence for TLS and, if profitable, fallback
  sockets.
- Pass a bounded concatenation to the WebSocket wrapper so multiple MQTT
  packets may share one legal binary frame.
- Maintain a private completion ledger mapping returned byte counts back to
  packet boundaries and existing `_OutPacket` positions.
- Apply all packet-completion side effects only after their final byte is sent.
- Preserve the current writer as the fallback and remove any backend that does
  not pass its transport-specific criteria.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Publish separate transport results and distinguish syscall reduction,
TLS/frame reduction, Python CPU, allocation cost, and isolated-message latency.

## Verdict

**Pending.** The final document may use `GO with conditions` when only a subset
of transports passes; otherwise use `GO` or `NO GO` at the checkpoint.
