# mqttnext — audit de solidité, correction et performance

Date : 2026-08-02  
Branche auditée : `cursor/mqtt-next-from-scratch-6c02`  
Branche de correction : `agent/mqttnext-hardening-audit`

## Objet

Ce document est le cahier de chantier exécutable pour durcir `mqttnext` avant une
première publication publique. Il doit être utilisé comme source de vérité par
l'agent de codage : chaque finding possède une sévérité, une proposition simple,
un critère d'acceptation et un statut.

Principe directeur : **préférer la correction locale la plus simple**. Toute
abstraction supplémentaire doit être justifiée par un invariant impossible à
garantir proprement autrement.

## Verdict

L'architecture fondamentale est bonne : moteur protocolaire synchrone séparé de
l'I/O asynchrone, writer unique, états QoS explicites, contrôle de flux séparé du
pool de packet identifiers, codec incrémental borné.

Le projet reste toutefois un prototype avancé. Les risques principaux sont :

1. orchestration `asyncio` non transactionnelle ;
2. reprise de session et persistance incomplètement cohérentes ;
3. parsers trop permissifs ;
4. façade sync qui contourne parfois le confinement à l'event loop ;
5. benchmarks comparatifs dont les sémantiques ne sont pas équivalentes.

## Règles du chantier

- Aucun changement de performance ne doit réduire la correction protocolaire.
- Toute correction de bug doit ajouter un test qui échoue sur le code précédent.
- Les exceptions d'entrée hostile doivent être des exceptions publiques
  `MQTTError`/`MalformedPacketError`/`ProtocolError`, jamais `IndexError` ou
  `struct.error`.
- Ne pas introduire d'actor framework, extension native, timer wheel, zero-copy
  complexe ou writer SQLite asynchrone sans mesure démontrant leur nécessité.
- Les lots P0 sont bloquants avant release ; P1 avant version stable ; P2 seulement
  après profilage.

---

# P0 — bloquant avant release publique

## P0.1 — Receipt QoS 1/2 terminé avant ACK dans `compat.paho`

**Sévérité : critique**  
**Statut : à corriger**

Dans le chemin `Client.publish()` appelé depuis un callback, le receipt QoS 1/2
est construit avec `_event=None`. `wait()` et `is_done()` le considèrent alors
terminé immédiatement, avant PUBACK/PUBCOMP.

### Correction

Créer obligatoirement un `asyncio.Event()` pour tout QoS supérieur à zéro, y
compris depuis un callback. Conserver `_event=None` uniquement pour QoS 0.

### Acceptation

- faux broker qui retarde PUBACK ;
- `is_published()` reste faux avant ACK ;
- `wait_for_publish()` bloque avant ACK puis termine après ACK ;
- `on_publish` n'est appelé qu'après ACK.

---

## P0.2 — Lifecycle de connexion non sérialisé

**Sévérité : critique**  
**Statut : à corriger**

Deux `connect()` simultanés peuvent ouvrir deux transports avant que le moteur ne
passe en `CONNECTING`, écraser `_transport`, `_outbound` et `_connack_fut`.
L'annulation de `connect()` peut laisser des tâches ou un transport ouverts.

### Correction

Ajouter un unique `_lifecycle_lock: asyncio.Lock` autour de la connexion,
déconnexion et phase critique de reconnexion. Toute sortie exceptionnelle,
y compris `CancelledError`, doit fermer le transport créé et annuler les tâches
créées par cette tentative avant de relancer l'exception.

### Acceptation

- deux connexions concurrentes : une seule tentative active ;
- annulation avant CONNACK : aucune tâche reader/writer et aucun transport restant ;
- reconnexion et déconnexion intentionnelle ne se chevauchent pas.

---

## P0.3 — Effets moteur extraits puis perdus sous annulation/backpressure

**Sévérité : critique**  
**Statut : à corriger**

`take_effects()` vide la liste avant les `await` de `_flush_effects()`. Une
annulation ou `FlowControlError` peut perdre des effets `SEND` alors que le MID,
le store et l'état QoS ont déjà été modifiés.

### Correction

Ajouter un unique `_engine_lock: asyncio.Lock` protégeant, dans la même section :

1. commande moteur ;
2. enregistrement receipt/future ;
3. transfert des effets `SEND` vers la queue.

Ne pas créer d'actor model. Si un enqueue est annulé, réinsérer les effets non
transférés ou ne les retirer du moteur qu'après transfert réussi.

### Acceptation

- annulation forcée sous backpressure : aucun effet perdu ;
- ordre FIFO conservé entre publications concurrentes ;
- aucun MID/store record sans paquet transféré ou explicitement échoué.

---

## P0.4 — Absence de rollback après acquisition MID/flow

**Sévérité : haute**  
**Statut : à corriger**

Si `_launch_outbound()` échoue pendant l'encodage, la validation ou le store, le
MID et le slot de flux peuvent rester réservés. `_drain_queue()` retire également
le message avant de savoir si son lancement réussira.

### Correction

Créer un helper transactionnel local qui :

- acquiert le slot ;
- lance le message ;
- sur erreur libère le slot, remet ou échoue le message et libère le MID selon
  son état ;
- ne retire définitivement un élément de la queue qu'après lancement réussi.

### Acceptation

Tests avec propriétés invalides et store injecté levant une exception : compteurs,
MIDs et queue identiques à l'état attendu après l'erreur.

---

## P0.5 — Reprise QoS 2 corrompant le contrôle de flux

**Sévérité : critique**  
**Statut : à corriger**

Pendant `_replay_session()`, les `WAIT_PUBCOMP` sont envoyés même si
`flow.try_acquire()` échoue. Les PUBCOMP peuvent ensuite libérer des slots qui ne
leur appartiennent pas.

### Correction

Conserver la politique actuelle de comptage jusqu'à PUBCOMP, puisqu'elle a été
choisie après mesure, mais utiliser une unique queue de replay state-aware. Un
record n'est réémis que lorsqu'un slot local est réellement acquis.

Cette complexité est justifiée par l'invariant :

```text
flow.inflight == nombre de transactions sortantes comptées par la politique
```

### Acceptation

Reprise SQLite avec plus de transactions QoS 2 que la fenêtre ; vérification de
l'invariant après chaque PUBCOMP et absence de dépassement de fenêtre.

---

## P0.6 — Paquets acceptés dans un état de connexion invalide

**Sévérité : critique**  
**Statut : à corriger**

Le moteur peut dispatcher PUBLISH/PUBACK/SUBACK avant CONNACK ou après fermeture.

### Correction

Ajouter une table centrale `_ALLOWED_PACKETS_BY_STATE`. Pendant `CONNECTING`,
seuls CONNACK et AUTH MQTT 5 sont acceptés. Pendant `CONNECTED`, accepter les
paquets serveur valides. Tout autre paquet produit une erreur protocolaire unique.

### Acceptation

Tests PUBLISH, PUBACK, SUBACK avant CONNACK et après DISCONNECT.

---

## P0.7 — Double livraison callback + iterator pouvant bloquer le reader

**Sévérité : haute**  
**Statut : à corriger**

Chaque message est toujours ajouté à `_messages`, même si l'application utilise
seulement `on_message`. La queue finit par se remplir et bloque le reader.

### Correction

Rendre le mode explicite : `iterator`, `callback` ou `both`. Mode par défaut à
décider avant publication ; `both` doit être opt-in si l'on veut éviter les
surprises. Les helpers callback utilisent `callback`.

### Acceptation

Plus de `max_pending_messages` messages en mode callback-only sans blocage ni
croissance de la queue iterator.

---

## P0.8 — Tâches callbacks non suivies et illimitées

**Sévérité : haute**  
**Statut : à corriger**

Les callbacks sont lancés avec `create_task()` sans conservation ni collecte des
exceptions.

### Correction

Conserver les tâches dans un `set`, retirer chaque tâche à terminaison et récupérer
son exception. Annuler proprement les tâches lors de la fermeture. Ne pas créer de
pool sophistiqué avant mesure.

### Acceptation

- aucune erreur « Task exception was never retrieved » ;
- fermeture sans tâche callback survivante ;
- callback fautif n'arrête pas le reader.

---

## P0.9 — Décodeurs permissifs

**Sévérité : haute**  
**Statut : à corriger**

Plusieurs décodeurs ignorent des octets résiduels, acceptent des MID nuls ou des
Reason Codes impossibles.

### Correction

Ajouter des helpers simples :

- `require_end(pos, length, packet)` ;
- `require_nonzero_mid(mid, packet)` ;
- `require_reason_code(reason, allowed, packet)`.

Chaque décodeur doit consommer exactement le body.

### Acceptation

Corpus de paquets valides avec octet final ajouté, MID 0 et Reason Codes invalides :
tous rejetés avec `MalformedPacketError`.

---

## P0.10 — VBI non canonique accepté

**Sévérité : moyenne/haute**  
**Statut : premier correctif du chantier**

Le decoder accepte une valeur encodée sur plus d'octets que nécessaire.

### Correction

Comparer le nombre d'octets consommés à `vbi_len(value)` et lever
`MalformedPacketError` si l'encodage n'est pas minimal.

### Acceptation

Rejet de `b"\x80\x00"`, `b"\x81\x00"` et autres formes non minimales ; formes
canoniques inchangées.

---

## P0.11 — WebSocket trop permissif

**Sévérité : haute**  
**Statut : à corriger**

Frames serveur masquées, frames texte, bits RSV et opcodes inconnus sont acceptés
ou ignorés ; un nouveau message peut remplacer une fragmentation en cours ; PONG
peut être différé.

### Correction

Durcir la machine existante :

- frame serveur masquée => erreur ;
- RSV sans extension => erreur ;
- texte/opcode réservé => erreur ;
- nouveau message pendant fragmentation => erreur ;
- PONG envoyé immédiatement.

Aucune dépendance WebSocket supplémentaire n'est requise.

---

## P0.12 — Fuzzers masquant des bugs de parser

**Sévérité : haute pour la confiance**  
**Statut : à corriger**

`IndexError` et `struct.error` sont considérés comme acceptables.

### Correction

N'autoriser que les exceptions publiques documentées. Renforcer les invariants :

```text
flow.inflight == count(states comptés)
packet_pool.used == outbound_mids U pending_sub_mids
```

Le test WebSocket « bounded » doit contenir une vraie assertion de borne.

---

# P1 — requis avant version stable

## P1.1 — SUBSCRIBE/UNSUBSCRIBE orphelins lors d'une perte réseau

Échouer immédiatement les opérations non rejouables lors de la perte du transport.
Ne pas les laisser attendre jusqu'au timeout et ne pas les rejouer implicitement.

## P1.2 — Persistance entrante non reconstructible

Ajouter `in_items()` à l'interface du store et reconstruire les états QoS 2
entrants. Interdire temporairement `manual_ack=True` avec un store durable, ou
ajouter une API publique `ack_mid()` et une récupération des messages en attente.

## P1.3 — Façade sync hors confinement event loop

Toute interaction avec le moteur/AsyncClient depuis `compat.paho` doit passer par
la loop dédiée. `subscribe()` et `unsubscribe()` ne doivent plus muter le moteur
depuis le thread appelant.

## P1.4 — Validation des paramètres

Valider une fois dans les constructeurs : keepalive, tailles, maxima, délais,
multiplicateur et limites de queue. Ne pas corriger silencieusement les entrées
invalides.

## P1.5 — Validation UTF-8 symétrique

Utiliser une validation partagée à l'encodage et au décodage. Les champs texte
MQTT acceptent `str`, les champs binaires `bytes`.

## P1.6 — AUTH MQTT 5

Vérifier la présence et la stabilité de `authentication_method`, les états et les
Reason Codes autorisés.

## P1.7 — Réutilisation du client après disconnect

Réinitialiser proprement la queue de messages et les sentinels lors d'une nouvelle
connexion explicite ; ne jamais supprimer silencieusement un message réel pour
insérer le sentinel.

## P1.8 — Capacités négociées périmées

Réinitialiser les capacités broker au début d'une nouvelle connexion. Pendant la
déconnexion, appliquer uniquement les limites locales ; valider les messages en
queue après le nouveau CONNACK et avant tout replay.

## P1.9 — Taille maximale locale annoncée

Donner une valeur explicite au maximum local et l'annoncer automatiquement en MQTT
5. Documenter la limite locale en MQTT 3.1.1.

## P1.10 — CI de qualité

Ajouter :

- Ruff ;
- type checker ;
- couverture ;
- tests TLS ;
- tests WebSocket ;
- tests reconnect/reprise SQLite ;
- matrice d'annulation et de concurrence.

---

# Performance — findings et actions

## PERF.1 — Comparaison micro non équivalente

Séparer : codec pur, enqueue API et remise au transport. Ne comparer que des
opérations de même sémantique.

## PERF.2 — Fenêtres inflight différentes

Exposer `max_outbound_inflight` dans l'API et forcer la même fenêtre pour toutes
les bibliothèques. Publier les courbes débit/latence pour plusieurs fenêtres.

## PERF.3 — Track D incorrect

Le benchmark varie `local_receive_maximum`, qui n'est pas la fenêtre sortante
après CONNACK. Utiliser `max_outbound_inflight` et assert la limite effective.

## PERF.4 — QoS 0 non mesuré de bout en bout

Mesurer séparément enqueue, drain transport et réception effective par un
subscriber de contrôle. Vérifier le nombre de messages reçus.

## PERF.5 — Environnement de bench

Randomiser l'ordre des bibliothèques, nouveau processus par run, médiane + IQR,
versions et paramètres complets enregistrés.

## PERF.6 — SQLite

Utiliser BLOB pour les payloads, ne mettre à jour que les colonnes mutables et
versionner le schéma. Conserver les commits synchrones tant qu'une garantie de
durabilité plus complexe n'est pas spécifiée.

## PERF.7 — Helpers publish

Borner le nombre de receipts simultanés par batch.

## PERF.8 — Zero-copy decoder

Ne pas introduire de vues à durée de vie complexe avant profilage démontrant que
la copie domine le coût total.

---

# Ordre d'exécution recommandé

1. P0.1 et tests de receipt compat.
2. P0.10 et durcissement immédiat du fuzzer codec.
3. P0.2 + P0.3 : sérialisation lifecycle/engine.
4. P0.4 : rollback transactionnel.
5. P0.5 + P1.2 : replay/persistance et invariants.
6. P0.6 + P0.9 : états et parsers stricts.
7. P0.7 + P0.8 : livraison et callbacks.
8. P0.11 : WebSocket.
9. P1.1, P1.3 à P1.9.
10. Réécriture des benchmarks seulement après stabilisation fonctionnelle.

# Définition de terminé

Un lot est terminé uniquement si :

- le bug est reproduit par un test rouge sur l'ancien code ;
- le correctif est local et documenté ;
- toute la suite existante reste verte ;
- les fuzzers n'acceptent pas d'exception Python interne ;
- les invariants associés sont vérifiés explicitement ;
- aucune optimisation non mesurée n'a été ajoutée.
