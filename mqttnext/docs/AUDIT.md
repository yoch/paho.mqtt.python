# Auto-audit — livraison Phase 0

Date : 2026-08-01  
Branche : `cursor/mqtt-next-from-scratch-6c02`

> Une seconde passe d'audit (planification pré-implémentation) a été menée le
> même jour — voir la section « Audit de planification » en fin de document.

## Périmètre audité

Code sous `mqttnext/src/mqttnext` + tests `mqttnext/tests/unit`.

## Checklist correctness

| Point | Statut | Notes |
| --- | --- | --- |
| QoS 2 out : MID conservé jusqu’à PUBCOMP | OK | Test `test_qos2_outbound_keeps_mid_until_pubcomp` ; contraste gmqtt |
| QoS 2 in : dédup / pas de redeliver | OK | Test `test_qos2_inbound_dedup` |
| Receive Maximum ≠ espace MID | OK | `FlowControl` vs `PacketIdPool` ; test dédié |
| Decoder fragmentation + multi-paquet | OK | Tests codec |
| Limite taille paquet | OK | `PacketTooLargeError` |
| `memoryview` non exposé à l’API | OK | `RawPacket.remaining` est `bytes` |
| session_present replay + DUP | OK | Test replay |
| Exhaustive switch effects | OK | branche `Never` dans `AsyncClient._flush_effects` |
| Imports en tête de module | OK | règle workspace |

## Risques connus (assumés Phase 0)

| Risque | Mitigation prévue |
| --- | --- |
| MQTT 5 properties non implémentées | `NotImplementedError` explicite ; phase 1 |
| Pas de keepalive timer dans AsyncClient | phase 1 |
| Pas de reconnect / backoff | phase 1 |
| SUBACK/UNSUBACK non awaitables | phase 1 futures |
| `queue_publish` offline QoS>0 sans borne d’ordre reconnect complexe | tests + ROADMAP |
| Pas de TLS / WS | phase 1–2 |
| Licence TBD | avant spin-out |
| Façade Paho absente | phase 3 |
| Engine `handle_raw` table dict (pas `match`) | OK perf ; exhaustive via KeyError path |

## Non-régressions vs leçons Paho

| Leçon audit | Appliquée ? |
| --- | --- |
| Decoder contigu / buffer borné | Oui (base) |
| Empty props fast path | Oui (octet `0x00`) |
| dict ordonné inflight | Oui |
| Callback hors engine | Oui (effects → API) |
| Pas d’alias auto / cache topic | Oui (non implémenté) |
| Read-ahead batch | Partiel (`drain_packets(limit=100)`) |
| Segmented large payload | Non (phase 2) |

## Non-régressions vs bugs gmqtt

| Bug gmqtt | Traité ? |
| --- | --- |
| PUBCOMP no-op / free MID sur PUBREC | Oui |
| Pas de dédup inbound QoS2 | Oui |
| Receive Maximum → max MID | Oui (séparé) |
| Parser `buf +=` quadratique | Évité (`bytearray` + offset) |
| write sans drain | `TcpTransport.write` appelle `drain()` |

## Vérification exécutée

```bash
cd mqttnext && pip install -e ".[dev]" && python3 -m pytest -q
# 22 passed in 0.03s
```

## Verdict auditeur

**GO pour Phase 0** en tant que fondation / plan exécutable.  
**NO GO production.** Ne pas publier sur PyPI tant que Phase 1 (properties,
keepalive, reconnect, TLS) et la matrice QoS reconnect ne sont pas vertes.

---

# Audit de planification pré-implémentation (2e passe)

Objectif : vérifier que les pistes (ANALYSIS/DESIGN/ROADMAP) sont correctes,
cohérentes entre elles et avec le code phase 0, et **suffisantes pour qu'un
agent implémente les phases suivantes sans se tromper**.

## Verdict global

Les orientations (cœur sync + I/O async, leçons GO/NO GO Paho, corrections
gmqtt) sont **correctes et cohérentes**. En revanche la planification était
**insuffisamment spécifiée** pour une implémentation sans erreur (items de
roadmap en une ligne, contrats MQTT 5 / keepalive / reconnexion absents), et
la passe a révélé **trois défauts de correction réels** dans le code phase 0.
Tous sont corrigés dans cette livraison ; les lacunes doc sont comblées par
[`IMPLEMENTATION-GUIDE.md`](IMPLEMENTATION-GUIDE.md).

## Défauts de code trouvés et corrigés

| ID | Sévérité | Défaut | Correction | Test |
|---|---|---|---|---|
| B1 | Critique | **Course receipt/ACK** : `publish()` flushait le PUBLISH avant d'enregistrer le receipt ; un PUBACK traité par le task lecteur pendant le `drain()` rendait `wait()` infini | Receipt enregistré avant tout flush ; invariant documenté (guide §1.3) | `test_connect_publish_qos1_wait_disconnect`, `test_many_concurrent_publishes_complete` |
| B2 | Critique | **File offline perdue** : le reset clean-session sur CONNACK vidait `store` + `_queued` + pool, jetant silencieusement les publishes QoS>0 postés avant `connect()` | Le reset ne jette que les messages déjà transmis (`WAIT_*`, → `PUBLISH_FAILED` + `SessionDiscardedError`) ; les `QUEUED` jamais émis sont conservés et lancés | `test_offline_queue_survives_clean_connect`, `test_clean_reconnect_fails_inflight_keeps_queued` |
| B3 | Haute | **Entrelacement d'écritures** : `_flush_effects` écrivait sur le transport depuis plusieurs coroutines (publish + reader) ; deux lots pouvaient s'entrelacer sur le wire | Writer unique : les effets `SEND` alimentent une file FIFO drainée par un seul task (guide §1.1) ; corrige aussi le deadlock potentiel callback→publish | couvert par les tests client (fake transport) |
| B4 | Moyenne | `errors.TimeoutError` masquait le builtin | Renommé `MQTTTimeoutError` ; ajout `SessionDiscardedError` | — |
| B5 | Faible | `_queued.pop(0)` O(N) sur liste | `collections.deque.popleft()` | — |
| B6 | Faible | Table de handlers reconstruite à chaque `handle_raw` (hot path) | Précalculée dans `__init__` | — |
| B7 | Faible | `_read_loop` : un callback annulé pendant la fermeture pouvait sauter `_closed.set()` | Flush de fermeture isolé ; receipts orphelins échoués à la fermeture | — |

## Lacunes de planification comblées (IMPLEMENTATION-GUIDE.md)

| ID | Lacune | Où c'est fixé |
|---|---|---|
| G1 | Aucune table des propriétés MQTT 5 (IDs, types, paquets, multiplicité) — impossible d'implémenter la phase 1 sans relire la spec | guide §2 |
| G2 | Règles de négociation CONNACK non spécifiées (receive maximum, max packet size, max QoS, retain, alias, server keep alive) | guide §3 |
| G3 | Algorithme keepalive non défini (le point faible gmqtt « tout octet vaut pong » n'était pas explicitement proscrit) | guide §4 |
| G4 | Politique de reconnexion sans paramètres ni liste des reason codes terminaux v3/v5 | guide §5 |
| G5 | Timeouts par opération et libération des MID (fuite en cas de SUBACK perdu) non spécifiés | guide §6 |
| G6 | Règles de validation topics/filtres/`$share` absentes | guide §7 |
| G7 | Choix « deliver on PUBLISH vs on PUBREL » (QoS 2 entrant) non figé | guide §8 |
| G8 | Sémantique exacte de `PublishReceipt` (QoS 0, erreurs, annulation) ambiguë | guide §9 |
| G9 | Backpressure : bornes chiffrées et comportement (attendre vs lever) non définis | guide §10 |
| G10 | Encodage `SubscribeOptions` v5, will, AUTH non contractualisés | guide §11 |
| G11 | Matrice de tests « Definition of Done » par phase absente | guide §12–13 |

## Incohérences doc mineures corrigées

- `DESIGN.md` : la sémantique QoS 0 du receipt (« drain socket ») ne
  correspondait pas à l'architecture writer unique → aligné (« accepté en
  file writer »), la complétion réseau QoS 0 reste hors contrat.
- `ROADMAP.md` : items de phase 1 renvoient désormais aux sections du guide.
- gmqtt forçait `clean_session=False` à la reconnexion ; notre politique
  (guide §5) préserve le choix utilisateur — divergence désormais explicite.

## Vérification

```bash
cd mqttnext && python3 -m pytest -q
# 27 passed (22 phase 0 + 5 régressions d'audit)
```

## Verdict de la 2e passe

**GO pour lancer l'implémentation phase 1** : les pistes sont correctes,
cohérentes, et le guide fournit les contrats manquants. Points restant
**bloquants avant spin-out** (inchangés) : licence, nom définitif, décision
finale sur l'API `messages()` (sentinel vs polling).
