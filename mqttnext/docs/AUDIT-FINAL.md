# Audit complet — mqttnext (stabilité, bugs, performance, sécurité)

Date: 2026-08-02  
Périmètre : `mqttnext/src/mqttnext` (~5k LOC), 4 audits parallèles (stabilité, correctness protocolaire, performance, sécurité) avec reproductions.  
Suite : **117 tests** verts après correctifs.

Ce document complète `AUDIT-CORRECTNESS.md` (audit précédent) et `PERF-SPRINT.md`.

## Verdict en une phrase

Le **cœur protocolaire** (engine sync, codec, pool d’IDs, machines QoS) est sain ;
l’essentiel du risque se concentrait dans la **couche de cycle de vie asyncio**
(orchestration des tâches, callbacks awaités, comptabilité des waiters) et dans
des **gardes d’état** manquantes (CONNACK dupliqué, SUBACK orphelins, MID pool).

## Correctifs appliqués (cette passe)

### Critiques / hautes

| ID | Problème | Fix |
| --- | --- | --- |
| B1 | `PacketIdPool.allocate` réémettait des MID réservés après hydratation SQLite | Skip des IDs réservés avant d’avancer `_next` |
| C1 | `on_connect` awaité inline dans le reader → deadlock si `await subscribe()` | `on_connect` schedulé en task (comme `on_message`) |
| C2 | Boucle reconnect mourait si la connexion retombait pendant `stable_after` | `continue` au lieu de `return` si déconnecté ; reader respawne si task `.done()` |
| C3 | Writer task + transport fuyaient sur déconnexion sans reconnect | Cancel writer + close transport dans le `finally` reader |
| C4 | `_last_disconnect` obsolète bloquait les reconnects futurs | Reset dans `_connect_once` |
| F4/M4 | Second CONNACK accepté → purge de session | Garde `_pending_connect` + `state == CONNECTING` |
| F5/H3 | SUBACK/UNSUBACK orphelins libéraient des MID arbitraires | Tracking `_pending_sub_mids` ; release seulement si connu |
| H1 | Waiters backpressure jamais réveillés à la mort définitive | `notify_all` dans le chemin `not will_reconnect` |
| H4 | Timeout SUBACK libérait le MID → cross-talk | Ne plus release au timeout (l’engine gère) |
| B2 | Replay différé renvoyait DUP=0 | `dup=True` + ré-encodage quand remis en queue |
| B3/F9 | PUBLISH topic vide sans alias accepté | `ProtocolError` après résolution d’alias |

### Moyennes / robustesse

| ID | Problème | Fix |
| --- | --- | --- |
| M1 | Fuite MID sur exception après `allocate()` | `try/except: release; raise` (publish + sub/unsub) |
| M6 | Pas de timeout sur la phase TCP/TLS/WS du connect | `wait_for` autour de la factory transport |
| M7 | Keepalive neutralisé par backpressure | PINGREQ en `nowait` (perdu > keepalive mort) |
| H5 | DISCONNECT broker ne fermait pas le transport | Close proactif → reader sort, reconnect/cleanup |
| F1/F2 | WebSocket : trame/handshake non bornés | `max_frame_size`, cap headers 64 KiB, timeout handshake |
| F3 | Ping/pong WS non bornés | Control ≤125, FIN requis, `_pending_control` borné |
| F10 | Handshake WS validé par sous-chaînes | Parse headers, `Sec-WebSocket-Accept` exact, subprotocol `mqtt`, Upgrade |
| B13/F11 | Fragmentation WS droppée | Réassemblage continuation frames |
| F13 | `TopicMatcher` récursif → RecursionError | Itératif (stack explicite) |
| F12 | Secrets dans `repr` | `password` / `will` en `field(repr=False)` |
| B5 | Props BYTE non validées 0/1 | `zero_one` sur PFI, RPI, RRI, retain/wildcard/subid/shared available |
| M2 | QoS1 manual_ack DUP gonflait inbound inflight | (documenté — voir dette restante) |

### Performance (confirmée, pas de régression)

| Métrique | Avant audit | Après correctifs |
| --- | ---: | ---: |
| encode QoS0 | ~1.32M | ~1.33M |
| decode QoS0 | ~520k | ~527k |
| e2e QoS0 | ~201k | ~230k |
| e2e QoS1/2 | ~40k / ~26k | ~41k / ~26k |

## Dette restante (connue, non bloquante)

1. **compat.paho** : `subscribe()` bloquant + garde `_in_callback` cassent l’idiome
   `on_connect → subscribe` (H6). À traiter si la façade sync doit être plus fidèle.
2. **QoS1 manual_ack DUP** : redelivery peut compter un slot inbound en trop (M2).
3. **Store SQLite** : erreurs non isolées dans `handle_raw` (M3) ; commit par op.
4. **FlowControl** : fenêtre outbound bornée par `min(broker, local)` (M10/B6) —
   conservateur, sémantiquement à revoir (paramètre séparé).
5. **Fuzz** : étendre au-delà du framing (engine, properties, WS) — jalon E.
6. **Reason codes normatifs** (0x93/0x94/0x95) au lieu de fermeture sèche (B4).

## Reproduire

```bash
cd /workspace
PYTHONPATH=mqttnext/src python3 -m pytest mqttnext/tests -q
PYTHONPATH=mqttnext/src python3 mqttnext/benchmarks/perf_sprint.py --tag audit
```
