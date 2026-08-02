# Audit de correctness — mqttnext (post phase 3)

Date : 2026-08-01  
Périmètre : `mqttnext/src`, tests unitaires/intégration, benches comparatifs  
Méthode : relecture ciblée + reproduction de bugs + correctifs minimaux + re-bench

## Verdict

Le cœur protocolaire (`ProtocolEngine`) et le client async sont **utilisables**
pour du pub/sub QoS 0/1/2 sur TCP, avec une perf QoS0 clairement au-dessus de
gmqtt/paho. L’audit a toutefois trouvé plusieurs **bugs de correctness réels**
(pas des nits) ; les plus graves ont été corrigés dans le même passage.

**85 tests** verts après correctifs.

Ce n’est **pas** encore une référence production-hardened : WebSocket non branché,
façade Paho partielle, SQLite « best effort », et plusieurs gaps protocolaires
MQTT 5 restent ouverts (voir « Dette restante »).

## Bugs confirmés et corrigés

| ID | Sévérité | Problème | Correctif |
| --- | --- | --- | --- |
| C1 | Critique | `PUBACK`/`PUBCOMP` acceptés hors état attendu (ex. PUBACK sur QoS 2 → fausse completion) | Validation `OutboundQoSState` avant mutation |
| C2 | Critique | Toute coupure transport échouait les receipts **avant** reconnect | Préserver receipts/`messages()` si reconnect actif |
| H4 | Haute | Drain plafonné à 100 paquets/read → frames orphelines si peer pause | Boucle jusqu’à buffer vide |
| H3 | Haute | Payload ≈ 1 MiB + header > `max_outbound_bytes` → deadlock enqueue | Autoriser un item oversized dans une file vide |
| H10 | Haute | Alias entrant accepté si `topic_alias_maximum=0` | Rejet si `alias > max` (0 inclus) |
| H2 | Haute | Callback/`messages()` bloquaient l’émission des ACK | Flush `SEND` d’abord ; `on_message` via `create_task` |
| H7 | Haute | Échec writer sans fermer le transport | `close()` transport pour débloquer le reader |
| M7 | Moyenne | `foo/#` ne matchait pas `foo` | Match `#` à zéro niveau restant |
| SQLite | Haute | Replay `QUEUED`/`PUBREL` sans bytes ; MID non réservés ; `user_acked` non persisté | Rebuild wire, `reserve()`, `update_in()` |
| Flow | Moyenne | Slot Receive Maximum tenu jusqu’au PUBCOMP | Libération à PUBREC (MQTT 5 § Receive Maximum) |
| Keepalive | Moyenne | `_force_close` pouvait s’annuler lui-même | Ignorer `current_task()` |
| Backoff | Basse | `stable_after` jamais respecté | Reset backoff seulement après stabilité |

## Over-engineering / simplicité

| Élément | Jugement | Action |
| --- | --- | --- |
| WebSocket maison incomplet | Trop tôt pour « DoD » ; non branché sur `AsyncClient` | Roadmap annotée : transport bas niveau seulement |
| `SqliteInflightStore` | Utile mais pas production-hardened (props binaires JSON, pas de cache identité) | Annoté « best effort » ; correctifs de base seulement |
| Batch writer 64 + drain coalesce | Justifié par les benches QoS | Conservé |
| Compat Paho | Couche additive OK ; signatures/deadlocks callback sync incomplets | Documenté ; pas d’expansion premature |

Principe retenu : **corriger le moteur**, ne pas ajouter de couches.

## Dette restante (mise à jour post-hardening)

Corrigé depuis : flags fixed-header, MID=0, DISCONNECT reasons, Clean Start
resume, inbound Receive Maximum, offline vs negociation, receipts/reconnect,
façade Paho VERSION2, CI Mosquitto, deadlock writer `drain()`.

Encore ouvert :

1. Spin-out dépôt dédié (hors ce fork)
2. SCRAM / plugins AUTH concrets (l’API `auth_handler` est en place)
3. Audit externe / fuzz longue durée (jalon E)

### Livré depuis l’audit initial

- AUTH MQTT 5 : `AuthPacket`, `EngineConfig.accept_auth`, `AsyncClient.auth_handler` / `auth()`
- WebSocket branché : `AsyncClient.connect_ws`, ping→pong, `write_many`
- SQLite : sérialisation props taguée (bytes / tuples / user_property)
- Jalon D : `tests/unit/test_compat_lib_subset.py` (miroir comportemental tests/lib)

### Choix perf QoS 2

La fenêtre locale (`FlowControl`) est conservée jusqu’au **PUBCOMP** (pas
libérée au PUBREC). MQTT 5 autorise la libération au PUBREC, mais la libération
anticipée provoquait des stalls intermittents (file outbound / accumulation
`WAIT_PUBCOMP`). Correct et stable ; documenté ici plutôt que « smart ».

## Benchmarks (après correctifs)

Broker : Mosquitto `127.0.0.1:11883`, Python 3.12, VM cloud agent.

### Comparatif libs (médiane harness `compare_libs.py`)

| Scénario | mqttnext | gmqtt | paho | vs gmqtt | vs paho |
| --- | ---: | ---: | ---: | ---: | ---: |
| encode QoS0 small | 1,09M/s | 1,06M/s | 212k/s | ≈1,0× | **5,2×** |
| e2e QoS0 p64 | 181k msg/s | 96k | 71k | **1,9×** | **2,5×** |
| e2e QoS1 p64 | 23,0k | 227† | 18,9k | — | **1,2×** |
| e2e QoS2 p64 | 8,2k | 1,2k | 11,9k | **6,9×** | 0,7× |

† gmqtt : Receive-Maximum-as-MID → batches de 10 (pipelining détruit).

### Micro baseline mqttnext

| Opération | Débit |
| --- | ---: |
| `publish_encode_qos0_small` | ≈1,08M ops/s |
| `ingress_decode_10x_qos0_small` | ≈84k batch/s |

### Lecture perf

- **Force** : firehose QoS 0 et encode — clairement devant paho, devant ou à égalité de gmqtt.
- **QoS 1** : au niveau / légèrement devant paho sur completion réelle.
- **QoS 2** : derrière paho (~0,7×) sur cette machine ; correct (PUBCOMP vrai) et nettement devant gmqtt.
- Variance VM : QoS0 était ~222k sur un run antérieur ; 181k ici — même ordre de grandeur.

## Couverture tests

- 85 unitaires + intégration Mosquitto (si broker présent)
- Nouveaux : `tests/unit/test_audit_regressions.py` (ACK hors séquence, matcher `#`, alias, SQLite replay, drain >100)

## Recommandations

1. Spin-out : licence Apache-2.0 déjà posée ; extraire `mqttnext/` tel quel.
2. Brancher un `auth_handler` SCRAM réel derrière l’API AUTH pour les brokers qui l’exigent.
3. Élargir le jalon D vers davantage de scénarios `tests/lib` si la façade sync croît.
