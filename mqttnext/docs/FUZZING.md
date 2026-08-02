# Fuzzing — mqttnext (jalon E)

Fuzzer **sans dépendance**, reproductible par seed, avec oracles d’invariants.

## Cibles

| Cible | Ce qui est fuzzé | Oracle |
| --- | --- | --- |
| `codec` | properties, PUBLISH, frames typées mutées | seules des `MQTTError`/`ValueError`/`struct.error` sortent |
| `engine` | séquences protocolaires à états (CONNACK dup, ACK storms, alias, reconnect, manual_ack) | invariants : flow borné, mids cohérents, pas de compteur négatif |
| `websocket` | headers de frames (longueurs 64-bit, contrôle, fragmentation) | bornes mémoire, `ConnectionError` sur dépassement |

## Lancer

```bash
cd /workspace
# Rapide (smoke, dans la suite pytest)
PYTHONPATH=mqttnext/src python3 -m pytest mqttnext/tests/unit/test_fuzz_smoke.py -q

# Complet (seedé, borné)
PYTHONPATH=mqttnext/src python3 mqttnext/tests/fuzz/fuzz.py --seed 1 --iterations 20000

# Ciblé
PYTHONPATH=mqttnext/src python3 mqttnext/tests/fuzz/fuzz.py --target engine --iterations 100000
```

## CI

Job `fuzz` dans `.github/workflows/mqttnext.yml` : 3 seeds × 20k itérations.

## Reproductibilité

Tout crash est reproductible via `--seed N`. Le fuzzer rapporte la **première**
failure (itération + traceback) pour investigation.

## Limites connues

- Pas de couverture guidée (pas d’atheris/hypothesis dispo dans l’env) — les
  mutations sont structurelles + aléatoires bornées, pas coverage-feedback.
- Un run « 24h » reste à brancher sur une CI dédiée si souhaité ; le harness
  est prêt (`--iterations` élevé, `--seed` variable).
