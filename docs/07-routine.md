# Phase B.2 — Gameplay routine and the watering fix

## Diagnosis first

`analysis/diagnose.py` instruments one episode and attributes every worker turn. The result
ruled out two of my three hypotheses:

| | v2 | v3 |
|---|---:|---:|
| turns spent **working** | 23.2% | **29.2%** |
| turns spent **moving** | 71.5% | 65.1% |
| turns idle | 5.3% | 5.7% |
| mid-journey direction reversals | 4.4% of moves | — |

Watering was not losing to a priority inversion, and thrashing was marginal at 4.4%. **Workers
were simply walking three turns for every turn of work.** Nothing else mattered until that did.

## What worked, and what didn't

**Angular zones: tried, worse, reverted.** Giving each worker a wedge radiating from the shed
made travel *worse* — 71.5% → 76.7%, score 28,419 → 26,543. A wedge is long and thin, so its
owner is usually at the wrong end of it, and hard territory blocks a nearer free worker from
helping. Recorded because the idea is intuitive and wrong.

**Charging tasks for the walk: worked.** Rank tasks by `priority − travel_weight × distance to
the nearest free worker`, rather than by raw priority. Ranking by priority alone hands the most
urgent task in the world to the nearest worker, then the next, and so on — which scatters
everyone. Sweeping `travel_weight`: 0 → 29,447, 3 → 28,626, 5 → 29,868, **8 → 30,659**, 12 →
29,832.

**CARE was effectively never happening.** It fired **3 times in an entire episode** at its old
priority (below `PLANT`), despite A2 showing it doubles goose output for one action. Raised
above `WATER_BONUS`: now 141 firings, and `FEED` went 47 → 125.

## The layout bug, and why the earlier tuning was misleading

Sweeping `labour_headroom` upward produced scores of ~1,283 — *below the $3,000 starting bank* —
with **zero variance across seeds**. Zero variance is the tell: this was not bad luck, it was
the same deterministic failure every time.

Cause: the layout filled melon, then every coop, then wheat with whatever budget remained. Tight
budgets left wheat with **no tiles at all**. No wheat means no feed, so the animals starve, and
no early income either. Totally silent.

This is the same failure as the 6,203 cell flagged in `docs/05-agent.md` and left as "worth
investigating" — now confirmed and fixed. The layout now sizes the flock against the wheat
needed to feed it (a coop costs its own 4.2 actions plus 2 wheat tiles behind it), then spends
what is left on more wheat.

**Fixing it reversed the tuning answer.** Before the fix, tight working areas looked best
(headroom 0.25). After, the optimum is 0.65 — far fewer, far better-tended tiles:

| headroom | before fix | after fix |
|---:|---:|---:|
| 0.25 | 31,415 | 31,415 |
| 0.40 | 7,966 (sd 8,128) | 15,630 |
| 0.55 | 1,298 (sd 0) | 26,016 |
| 0.65 | 1,283 (sd 0) | **35,844 (sd 316)** |

Hand count re-swept at the new headroom: 5 → 32,478, 6 → 35,844, **8 → 36,901**, 10 → 26,294.
So A3's original 6–9 range was right after all; v2's measured "6" was an artifact of the broken
layout.

## Result

15 seeded episodes vs `starter`:

| | v2 | v3 |
|---|---:|---:|
| mean | 27,014 | **36,522** |
| median | 27,077 | 37,011 |
| stdev | 1,052 | 1,371 |
| animals placed | 6.0 | 10.3 |
| animals ending unfed | 0.3 | 0.8 |
| empty coops | 0.1 | **0.0** |

## Caveat: the weed count is partly noise

18.4 weeds/episode looks unchanged, but it is not measuring what it appears to. Weeds spawn
randomly on *any* empty unlocked tile at 0.5%/day. v3 deliberately works fewer tiles, so it
leaves ~50 unlocked-but-idle tiles: 50 × 0.005 × 30 ≈ **7.5 weeds/episode are spontaneous**, not
agent failure. The metric conflates "a plant died" with "grass grew on land we chose not to
farm", and gets *worse* precisely when the agent correctly shrinks its footprint.

Not fixed yet. It needs `health_report` to know the intended layout so it can count only weeds
on tiles we meant to farm. Until then, treat the weed number as directional only — and do not
tune against it.

## Still open

- The agent still ignores A4's best-response table and plays a fixed 8 melon tiles. First live
  opponent ran 12, so the table is applicable right now.
- No margin-conditioned risk, despite the payoff being `sign(M_i − M_j)`.
- Travel is still 65% of worker turns. Better routing (visiting tiles in a tour rather than
  re-deciding each turn) is the obvious next structural gain.
