# Kaggriculture agent

Entry for [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) (Kaggle + Google,
final submission 30 September 2026). Two-player farming sim, 720 turns, most coins wins.

**This repository is private until the competition closes.** Competition rules prohibit
privately sharing code outside a team; sharing is only permitted if made available to all
participants on the Kaggle forums.

## Objective

Prizes are flat — **1st through 10th each receive $5,000** — so the goal is to maximise the
probability of finishing top ten, not expected rank. Standing is decided by a Bradley-Terry
tournament over episodes played **1–15 October**, not averaged over the competition, so rating
before 30 September is feedback only. See [docs/06-iteration.md](docs/06-iteration.md).

## Layout

| path | what |
|---|---|
| `farmlib.py` | the agent — decision core, parameterised by `Config` |
| `main.py` | thin entry point; `build.py` flattens both into one submittable file |
| `ab.py` | **paired, seat-swapped A/B testing** — the instrument for accepting changes |
| `tune.py` | coordinate descent over the config using `ab` as the objective |
| `bench.py` | absolute scores plus a health report that catches silent breakage |
| `ladder.py` | pulls submissions, episodes and replays; reports whether to iterate |
| `analysis/` | Phase A model, plus diagnostics (`travel`, `diagnose`, `study`, `correlate`) |
| `docs/` | derivations, findings, negative results, decision log |

## How to change something

```bash
python ab.py --variant melon_tiles=10 --panel --n 3
```

**Adopt on the panel worst case, not the mirror margin.** Self-play rewards changes that beat
ourselves, which is not the same as beating the field. Three seeds resolves a ~500-coin effect
because seat-swapped pairing removes almost all variance.

Then verify and package:

```bash
python -m analysis.verify && python build.py && python verify_submission.py
```

`verify_submission.py` is not optional — Kaggle `exec`s the agent source, so `__file__` is
undefined there and a naive import fails the validation episode.

## Submitting

```bash
kaggle competitions submit kaggriculture -f submission.tar.gz -m "message"
```

Five per day, but **only the latest two are scored**, so they act as champion and challenger —
a third submission discards the comparison. Rating standard error is roughly `16·√n`, about
±62 points at 15 episodes, so differences under ~60 points at these sample sizes carry no
information.

## Where things stand

Self-play ~60,600 (from 6,704 for the first wheat-loop agent). The largest gains, in order:
cows (+11,673), route commitment (+6,405), hire-to-demand (+3,370), feed carry (+2,632),
finish-the-tile (+2,371).

Documented negative results worth not repeating: buying feed rather than growing it, the carrot
opening, fertilising melon, metering sales into shallow pools, angular worker zones, and copying
the field's parameters wholesale.
