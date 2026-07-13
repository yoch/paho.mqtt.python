# 26 - Ordered State Dictionaries

## Analysis

The client stores outgoing and incoming QoS state in two private
`collections.OrderedDict` instances. Every observed operation uses ordinary
mapping behavior plus insertion-order iteration: lookup, assignment, `pop`,
`clear`, membership, and iteration over `values()`. No call relies on
`move_to_end()`, `popitem(last=...)`, equality ordering, or another
`OrderedDict`-specific contract.

Insertion order is a language guarantee for `dict` on the actual Python 3.9
floor. Replacing only these two containers can therefore remove linked-list
bookkeeping and reduce retained memory without reopening the rejected ready
queue from plan 05 or changing the MQTT state machine.

## Preparation

- Inventory every `_out_messages` and `_in_messages` operation and add an
  explicit regression test if any ordering dependency is not already covered.
- Extend the inflight/reconnect benchmark to select `dict` or `OrderedDict`
  without changing the measured ACK and replay code.
- Measure 20, 100, 1,000, and 10,000 queued messages, including QoS 1 ACK,
  QoS 2 transitions, reconnect reset, and successful-CONNACK replay.
- Record container size, Python allocations, CPU time, throughput, and state
  order. Use two warmups and seven runs while tuning, then fifteen paired runs
  for final evidence, pinned to one CPU where sub-millisecond noise matters.
- Run the realistic fixed client harness as a guardrail rather than inferring
  end-to-end throughput from the isolated mapping benchmark.

## Expected Gain

Priority: P1.

An exploratory 100,000-operation insert/pop probe took 60.4 ms with
`OrderedDict` and 37.8 ms with `dict`, about 37 percent less time. At 10,000
entries, the shallow container size fell from 746 KiB to 295 KiB, about 60
percent. A dynamic prototype improved the isolated 1,000-message ACK path by
about 12.7 percent and reconnect reset by about 19.8 percent. These are
directional results only; the 10,000-message replay result was inconclusive.

The expected production benefit is lower CPU and memory for clients retaining
many QoS messages. Network traffic and protocol round trips are unchanged.

## Acceptance Criteria

- Improve ACK completion or reconnect reset/replay at 1,000 messages by at
  least 8 percent in the final paired measurement.
- Reduce shallow mapping memory at 1,000 and 10,000 entries by at least 20
  percent.
- Do not regress the 20-message case or relevant realistic workload by more
  than 2 percent.
- Preserve insertion, deletion, reinsertion, inflight promotion, reconnect
  replay order, QoS 1/QoS 2 states, DUP bits, callbacks, and locking behavior.
- Change only the two private state mappings; do not add a second queue or
  modify any public API.

## Before Measurement

The definitive baseline will be the committed Python 3.9 metadata checkpoint.
It will be recorded before production code changes with the same interpreter,
CPU affinity, benchmark inputs, and run count as the candidate.

Exploratory evidence motivating the plan:

| Probe | `OrderedDict` | `dict` | Indicative delta |
| --- | ---: | ---: | ---: |
| 100,000 insert/pop operations | 60.4 ms | 37.8 ms | -37.5% |
| Shallow size, 10,000 entries | 746 KiB | 295 KiB | -60.5% |
| ACK throughput, 1,000 messages | 35,530/s | 40,058/s | +12.7% |
| Reconnect reset, 1,000 messages | 7.94/s | 9.52/s | +19.8% |

## Implementation

Pending. The candidate will replace the two initial constructions and the
incoming-state reset construction with plain `dict` instances. The benchmark
and focused tests will be committed with the accepted implementation, or kept
with a removed prototype if the verdict is `NO GO`.

## After Measurements

Pending implementation and fifteen-run final measurement.

## Results Analysis

Pending. The analysis must distinguish mapping microbenchmarks, MQTT state
operations, and realistic broker results. A memory win alone is acceptable
only if the CPU guardrails and all ordering semantics pass.

## Verdict

**Pending.** Stop for explicit evaluation after the final paired results.
