# Phase B — Agent v2

`farmlib.py` holds the decision core, parameterised by `Config`; `main.py` instantiates it.
Phase C will fork strategies by varying the config rather than duplicating logic.

## Result

15 seeded episodes vs the built-in `starter`:

| | v1 (wheat loop) | v2 |
|---|---:|---:|
| mean score | 6,704 | **27,014** |
| win rate | — | 15/15 |
| stdev | — | 1,052 |
| opponent mean | 3,491 | 3,500 |

## What it does, and which finding drives it

| behaviour | source |
|---|---|
| Melon planted first, closest to the shed, sold the instant it lands | A4: first-mover premium $12,790 |
| 8 melon tiles, not 11 | A4: equilibrium against a contesting opponent |
| Geese as the engine; wheat grown, never bought | A1: only unbounded streams. A3: LP buys zero wheat |
| Two land purchases, not three | A3: third expansion returns $1,378 on $4,000 |
| `COLLECT_FERTILIZER` capped at 8 animals' worth | A4: past that it earns less than eggs |
| `CARE` every day | A2: banks a bonus paid in a lump on the next yield |
| Priorities put FEED and urgent WATER above all earning actions | starvation and weeding are irreversible |

## Three bugs the health harness caught

None of these would have shown up as an error. All three look like "a slightly lower score",
which is exactly why `bench.py` inspects the final board instead of trusting the number.

**1. The entire goose engine never ran.** `PLACE` takes the animal from the acting worker's
*inventory*; the agent only ever checked the shed. Geese were bought and left in storage — 14
empty coops per episode. Score at the time was 12,728 and rising, so this would have shipped.

**2. Feed collection never happened for hired hands.** Inventories empty into the shed
overnight, so every worker starts the day with no wheat and its `FEED` silently no-ops. My
first fix ran the pickup at hour 0 — but hires are *market orders*, settled after player
actions, so hands don't exist yet at hour 0. Feed collection had to become a standing task.

**3. Coops were built that could never be stocked**, wasting both the build action and the
tile. Now bounded by geese held plus geese affordable.

## Where the model was wrong

**A3 said travel barely matters** — between a 0% and 50% flat overhead the optimum moved 1.7%.
That is not what a real greedy assignment does. Working every unlocked tile scatters tasks over
75 tiles and collapses throughput; restricting to a compact subset near the shed was worth more
than any other single change (7,778 → 19,518). A flat multiplier cannot represent this, because
the cost is superlinear in how spread out the work is.

The lesson generalises: A3 correctly found *land is not binding*, but the agent still has to
choose **which** tiles to use, and "all of them" is badly wrong.

**A3 predicted 6–9 hands; measured optimum is 6.** Twelve hands scores roughly half as much
(11,586 vs 22,075) despite a healthier board — the extra hires cost ~$9,660 a season and earn
less. The direction of A3's reasoning was right and the magnitude understated.

## Measured tuning

Grid over 3 seeds, since `labour_headroom` is not derivable from Phase A:

| headroom | 5 hands | 6 hands | 8 hands |
|---:|---:|---:|---:|
| 0.20 | 21,852 | **27,965** | 22,075 |
| 0.30 | 24,288 | 26,491 | 22,075 |
| 0.35 | 6,203 | 23,647 | 22,075 |

Settled on headroom 0.25, 6 hands. The 6,203 cell is a bootstrapping failure, not noise in the
usual sense — at that configuration the agent cannot fund its opening. Worth investigating.

## Known remaining problems

1. **13.5 weeds and 11.9 thirsty plants per episode.** Watering is still behind; some plants
   die before harvest. Probably the largest remaining loss.
2. **Only 6 animals placed**, below A4's equilibrium of 8 and well below A3's 16. The tightened
   working area traded livestock for crop health. Whether that trade is right is untested.
3. **No opponent awareness.** A4 built a best-response table indexed by the opponent's melon
   tiles, and the agent ignores it — it plays a fixed 8 regardless. This is the clearest
   unclaimed gain and the whole reason the observability check in `verify.py` matters.
4. **No margin-conditioned risk.** The payoff is `sign(M_i − M_j)`, so late-game variance should
   depend on whether we're ahead. Currently it doesn't.
