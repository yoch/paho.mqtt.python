# Compatibilité Paho — notes (phase 3)

La façade `mqttnext.compat.paho` n’est **pas** implémentée en Phase 0.
Ce document fige le contrat cible pour éviter de polluer le cœur.

## Mapping prévu

| Paho | mqttnext |
| --- | --- |
| `Client(CallbackAPIVersion.VERSION2, ...)` | Adaptateur sync/thread au-dessus d’`AsyncClient` |
| `connect` / `loop_start` | Thread avec event loop dédiée |
| `publish` → `MQTTMessageInfo` | Wrap de `PublishReceipt` |
| `on_*` callbacks VERSION2 | Dispatch vers callbacks Paho |
| `message_callback_add` | `TopicMatcher` |
| helpers `publish` / `subscribe` | Réécrits sur AsyncClient |

## Écarts volontaires

1. Pas de republication QoS>0 non conforme sur `clean_session=True` — suivre le
   standard ; documenter la migration.
2. `connect_async` historique reste synchrone côté compat ; l’API native utilise
   `await connect()`.
3. WebSocket / proxy : parity progressive, imports différés.

## Tests de non-régression

Réutiliser un sous-ensemble de `tests/lib` du dépôt Paho via une couche
d’adaptation, sans modifier le monolithe `src/paho`.
