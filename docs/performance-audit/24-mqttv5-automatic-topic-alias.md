# 24 - Automatic MQTT v5 Topic Alias Management

## Analysis

Project 12 rejected an implicit topic-encoding cache because its dictionary
lookup regressed a 1,000-topic publisher by about 14 percent. MQTT v5 Topic
Alias has a different potential benefit: after establishing an alias, repeated
PUBLISH packets can omit the topic from the wire entirely.

Automatic aliasing is still risky because it introduces a lookup on every v5
publish, retains topics, changes wire representation, and must reset correctly
on reconnect. The prototype must therefore be smaller and stricter than a
general cache and must be removed if high-cardinality CPU regresses.

## Preparation

- Configure a local MQTT v5 broker with Topic Alias Maximum values 0, 1, 8, 16,
  and 1,000.
- Test one repeated topic, 2/8/16 recurring topics, 17 topics, 1,000 topics,
  and all-distinct streams.
- Use topic lengths 8, 32, 128, and 1,024 bytes with payloads 16 B through
  4 KiB.
- Measure public `publish()` CPU, packets/s, bytes on wire, allocations, retained
  memory, alias hits, table saturation, and reconnect behavior.
- Include user-supplied `TopicAlias`, empty-topic publishes, rich properties,
  QoS replay, and brokers advertising zero support.

## Expected Gain

Priority: P2.

- At least 20 percent fewer wire bytes for long recurring topics.
- At least 5 percent end-to-end throughput gain in a bandwidth- or
  framing-bound repeated-topic scenario.
- No measurable cost when the broker advertises no aliases.
- No high-cardinality churn or retained-memory growth.

## Acceptance Criteria

- Activate only after a successful CONNACK with `TopicAliasMaximum > 0`.
- Bound the table to `min(server limit, 16)` entries and 64 KiB of topic bytes.
- Never evict or replace entries after saturation.
- Reset all aliases on every network connection/reconnection.
- The first use sends full topic plus alias; later uses may send an empty topic
  plus alias.
- User-supplied `TopicAlias` and explicit empty-topic behavior bypass automatic
  management, and user `Properties` are never mutated.
- At least 20 percent fewer wire bytes in the primary repeated-topic scenario.
- Require either at least 5 percent end-to-end improvement or at least 30
  percent fewer wire bytes with CPU regression below 1 percent.
- No throughput regression above 2 percent for 1,000/all-distinct topics.
- No protocol/state regression across QoS 0/1/2, reconnect, replay, properties,
  broker limit changes, or table saturation.

## Before Measurement

Pending. Use the accepted post-project-16 writer as baseline and retain project
12's high-cardinality scenario unchanged as the main regression guard.

Required baseline rows:

| Topics | Topic length | Payload | msg/s | Wire bytes/msg | Retained bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 repeated | 128 | 16 B | pending | pending | pending |
| 8 recurring | 128 | 16 B | pending | pending | pending |
| 16 recurring | 128 | 16 B | pending | pending | pending |
| 17 recurring | 128 | 16 B | pending | pending | pending |
| 1,000 distinct | 128 | 16 B | pending | pending | pending |

## Implementation

Planned prototype:

- Store a private fixed-capacity topic-bytes-to-alias mapping and next alias id.
- Populate the first available entries without eviction; stop admission at 16
  entries or 64 KiB.
- Record the broker's CONNACK limit without modifying callback properties.
- Inject an encoded Topic Alias into the private packed-property path without
  mutating the user's `Properties` object.
- Use the full original topic whenever an alias is first assigned or the table
  has been reset.
- Clear the table on close, failed connection, reconnect, and reinitialise.
- Remove all production alias code if the project 12 high-cardinality
  regression guard fails.

## After Measurements

Pending implementation and paired measurement.

## Results Analysis

Pending. Treat CPU and bytes-on-wire as separate dimensions and explicitly
explain why any accepted result does not reopen the rejected encoding cache.

## Verdict

**Pending.** Final decision must be `GO`, `GO with conditions`, or `NO GO` at
the explicit evaluation checkpoint before commit.
