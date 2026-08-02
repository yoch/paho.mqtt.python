# Fuzzing — mqttnext (jalon E)

Fuzzer **sans dépendance**, reproductible par seed, avec oracles d’invariants.

## Cibles

| Cible | Ce qui est fuzzé | Oracle |
| --- | --- | --- |
| `codec` | properties, PUBLISH, frames typées mutées | seules des `MQTTError`/`ValueError`/`struct.error` sortent |
| `engine` | séquences protocolaires à états (CONNACK dup, ACK storms, alias, reconnect, manual_ack) | invariants : flow borné, mids cohérents, pas de compteur négatif |
| `websocket` | headers de frames (longueurs 64-bit, contrôle, fragmentation) | bornes mémoire, `ConnectionError` sur dépassement |

## Deux harness complémentaires

| Harness | Fichier | Force |
| --- | --- | --- |
| Seedé, sans dépendance | `tests/fuzz/fuzz.py` | Reproductible (`--seed`), CI simple, invariants custom |
| Hypothesis (guidé + shrinking) | `tests/fuzz/test_hypothesis_fuzz.py` | Génération property-based, shrinking auto des cas d’échec |

## Lancer

```bash
cd /workspace
# Smoke (dans la suite pytest)
PYTHONPATH=mqttnext/src python3 -m pytest mqttnext/tests/unit/test_fuzz_smoke.py -q

# Seedé, borné
PYTHONPATH=mqttnext/src python3 mqttnext/tests/fuzz/fuzz.py --seed 1 --iterations 20000

# Hypothesis (profil CI par défaut)
pip install -e "mqttnext[fuzz]"
PYTHONPATH=mqttnext/src python3 -m pytest mqttnext/tests/fuzz/test_hypothesis_fuzz.py -q

# Hypothesis agressif (3000 exemples / test)
cd mqttnext && HYPOTHESIS_PROFILE=aggressive python3 -m pytest tests/fuzz/test_hypothesis_fuzz.py -q
```

## CI

Job `fuzz` dans `.github/workflows/mqttnext.yml` : fuzzer seedé (3×20k) **et**
hypothesis (profil `ci`).

## Reproductibilité

- Seedé : `--seed N` reproduit exactement la séquence.
- Hypothesis : tout échec est **shrinké** automatiquement et rejouable via la
  base d’exemples (`.hypothesis/`) ou `@reproduce_failure`.
