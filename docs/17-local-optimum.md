# Reaching a local optimum

`tune.py` walks the config neighbourhood, adopting only changes whose confidence interval clears
zero. Three passes:

| pass | adopted |
|---|---|
| 1 | melon 9→7, pasture 3→4, hands 8→9 (+10,070 as a set) |
| 2 | melon 7→5, pasture 5→7, feed carry 4→3, travel weight 8→13 (+7,170 as a set) |
| 3 | **nothing clears zero — local optimum** |

Both sets were validated on the panel as well as the mirror (worst cases +9,994 and +8,314), so
they are not artefacts of self-play.

## Two strategic shifts

**Cows became the core of the strategy.** The herd has grown 2 → 3 → 5 → 7 pastures, each step
paying only after throughput improved enough to tend them.

**Melon fell from A4's derived 8 to 5.** A4 was right for the agent that existed when it was
derived. Melon and livestock compete for the same layout budget, so every improvement to the
animals makes the marginal melon tile worse. A derived equilibrium is a statement about a
particular agent's opportunity costs, not a fact about the game.

## Coupling makes single-parameter intuition worthless

`travel_weight` measured **−10,506 at 12** under an earlier config and **+3,046 at 13** now. Same
knob, opposite sign, because everything else moved underneath it. This is why the tuner re-walks
the whole neighbourhood after each adoption rather than sweeping once.

## The grid was the constraint before the config was

The first pass reported a local optimum with `pasture_target` at 4 — which was simply the largest
value in its list. Five measures +3,326 beyond it. **Ranges must extend past the current value in
both directions**, or the search reports the edge of its own search space as an optimum.

## The budget is saturated, and that is now the binding constraint

`pasture_target=9`, `goose_target=22` and `fertilizer_quota=20` all measure **exactly +0**: the
layout budget refuses them. So the accuracy of that budget is what limits the farm.

### A plausible correction that is exactly backwards

`analysis/tilecost.py` measures what each tile type actually consumes per day:

| role | measured | model | ratio |
|---|---:|---:|---:|
| MELON | 1.74 | 0.91 | 1.91 |
| WHEAT | 1.08 | 1.20 | 0.90 |
| COOP | 2.17 | 4.20 | 0.52 |
| PASTURE | 1.81 | 3.70 | 0.49 |

Read naively this says the model over-charges animals twofold, and correcting it should let us
afford the herd the budget keeps refusing. Substituting the measured values scores **−16,640**.

The reading was wrong. **Measured spend is what a tile *gets*, not what it *needs*.** The farm is
labour-constrained: a coop wants four actions a day and is receiving 2.17. Charging it 2.17 tells
the layout it can afford more animals, which makes the existing under-service worse.

The model's numbers are requirements and are right to be.

### ...and the gap is not what I said it was either

I first read the 4.20-vs-2.17 difference as animals receiving half the attention they need, and
called it the clearest remaining inefficiency. Measuring the animals directly says otherwise:

| | |
|---|---:|
| animal-days | 264 |
| FEED delivered | 262 (99%) |
| CARE delivered | 273 |
| COLLECT_FERTILIZER | 254 (96%) |
| HARVEST | 310 |
| **actions per animal-day** | **4.16** |

End-of-day shortfalls are 7% unfed, 3% uncared, 3% fertilizer left standing. **Animals are being
served essentially in full.**

`tilecost.py` averages over *structure* tile-days, and across an episode roughly 45% of those
have no animal in them — a coop is built days before it is stocked, and counts as a low-cost
tile until then. The 2.17 is a blend of ~4.16 while occupied and ~0 while empty.

So the real (and much smaller) opportunity is **shortening the gap between building a structure
and stocking it**, not tending the animals better. Raising `PLACE` priority to 90 was already a
step in that direction and measured +967.

Recorded at length because the same number supported two different wrong conclusions before the
direct measurement settled it: prefer measuring the thing you care about over inferring it from
an aggregate.

## What is left

Parameter tuning is exhausted; remaining value is structural. Untried:

1. **Opponent-aware melon.** A4 built a best-response table indexed on the opponent's melon
   tiles and the agent has never used it. Lower value now that melon is only 5 tiles.
2. **Margin-conditioned risk.** The payoff is `sign(M_i − M_j)` and both players' money is
   public, so late-season risk should depend on which side of the line we are on. Never
   implemented, and the hardest of these to operationalise.
3. **Shortening build-to-stock latency.** Animals themselves are fully served (4.16 actions per
   animal-day), but ~45% of structure tile-days have no animal in them. Getting coops stocked
   sooner is worth more than tending them better.
