# 18 - Segmented Outbound Payloads

## Analysis

`_send_publish()` currently builds one contiguous `bytearray` and copies the
entire payload into it. For large immutable `bytes` payloads this duplicates
memory even though plain TCP and Unix sockets can send an MQTT header and the
original payload as separate iovecs.

The public API promises snapshot-like behavior for mutable `bytearray` input,
so mutable payloads must still be copied. TLS and WebSocket also require a
contiguous plaintext/frame buffer in the current architecture and remain on
their existing path unless a separate profile proves otherwise.

## Preparation

- Build TCP/Unix scenarios for 1, 16, 64, and 256 MiB immutable payloads.
- Add equivalent `bytearray` scenarios that mutate the source immediately
  after `publish()`.
- Measure QoS 0 and QoS 1, immediate sends, blocked/partial sends, connection
  loss before drain, and replay.
- Record time to first byte, throughput, allocations, peak `tracemalloc`, RSS,
  queue-resident bytes, and retained source-object lifetime.
- Keep small payloads from 16 B through 4 KiB as strict regression guards.

## Expected Gain

Priority: P1/P2, focused on large-payload publishers.

- At least 50 percent lower temporary/queue memory for a 64-MiB immutable
  payload.
- Earlier first-byte transmission and potentially 10 percent higher throughput.
- No gain expected for mutable payloads, TLS, WebSocket, or small messages.

## Acceptance Criteria

- At least 50 percent lower peak additional memory at 64 MiB on TCP/Unix.
- At least 10 percent higher throughput, or throughput within 2 percent while
  the memory criterion is met.
- No regression above 2 percent below 1 KiB.
- `bytearray` mutation after `publish()` cannot alter transmitted bytes.
- Immutable source lifetime ends after packet completion, failure, reconnect
  cleanup, or client reinitialisation.
- Partial writes across header/payload boundaries update positions correctly.
- QoS callbacks, `MQTTMessageInfo`, ordering, DUP, and replay remain unchanged.
- Platforms without vector I/O and TLS/WebSocket retain the contiguous path.

## Before Measurement

Pending. Measure project 16's accepted writer, if any, as the baseline so this
project reports only the additional effect of segmentation.

Required baseline rows:

| Transport/input | Payload | Throughput | Peak RSS delta | First byte |
| --- | ---: | ---: | ---: | ---: |
| TCP `bytes` | 1 MiB | pending | pending | pending |
| TCP `bytes` | 64 MiB | pending | pending | pending |
| Unix `bytes` | 64 MiB | pending | pending | pending |
| TCP `bytearray` | 64 MiB | pending | pending | pending |
| TCP `bytes` | 128 B | pending | pending | pending |

## Implementation

Planned prototype:

- Build a small immutable MQTT header segment containing fixed header, topic,
  MID, and MQTT v5 properties.
- Retain an immutable `bytes` payload as a second segment until completion.
- Copy `bytearray` payloads into immutable storage before queueing.
- Extend only the private writer representation needed by project 16; do not
  revive the rejected dict-compatible `_OutPacket` class from project 02.
- Keep contiguous fallback packets for unsupported transports/platforms.
- Release all segment references on every completion and cleanup path.
- Remove the segmented representation if memory savings are not accompanied by
  neutral small-message and partial-write behavior.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Separate memory retained by the application source from additional
memory allocated by Paho, and report throughput independently from RSS gains.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
