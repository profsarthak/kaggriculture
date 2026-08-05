# Kaggriculture agent

Entry for [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) (Kaggle + Google,
final submission 30 September 2026). Two-player farming sim, 720 turns, most coins wins.

**This repository is private until the competition closes.** Competition rules prohibit
privately sharing code outside a team; sharing is only permitted if made available to all
participants on the Kaggle forums.

## Layout

| path | what |
|---|---|
| `main.py` | submission entry point — must expose `agent(obs)` |
| `run.py` | local episode runner |
| `analysis/` | Phase A: the model, derived from the interpreter |
| `docs/` | derivations, findings, and the decision log |

## Approach

Three phases, in order:

- **A — Model.** Everything derivable without playing: market depth in closed form, labour
  accounting, an allocation LP, and analysis of the contested pools.
- **B — Agent portfolio.** Several genuinely different macro-strategies built from A.
- **C — Equilibrium.** Empirical game-theoretic analysis over that portfolio — round-robin
  simulation, empirical win-rate matrix, maximin solve.

The full game is not solvable: 720 stages, simultaneous moves, imperfect information, and an
enormous per-turn action space. "Equilibrium" here means the maximin mixture of a *restricted*
game whose pure strategies are our own. That limitation is stated wherever the result is used.

## Running

```bash
pip install -U kaggle-environments kaggle
python -m analysis.market      # A1: market depth and regeneration
python run.py starter          # one local episode vs the built-in baseline
```

## Submitting

```bash
kaggle competitions submit kaggriculture -f main.py -m "message"
```

Five submissions per day; only the latest two stay active and count for final scoring.
