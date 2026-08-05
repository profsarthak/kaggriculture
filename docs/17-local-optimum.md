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

The model's numbers are requirements and are right to be. The 4.20 against 2.17 gap measures how
far short we fall — it is a diagnostic, not an error to fix.

## What is left

Parameter tuning is exhausted; remaining value is structural. Untried:

1. **Opponent-aware melon.** A4 built a best-response table indexed on the opponent's melon
   tiles and the agent has never used it. Lower value now that melon is only 5 tiles.
2. **Margin-conditioned risk.** The payoff is `sign(M_i − M_j)` and both players' money is
   public, so late-season risk should depend on which side of the line we are on. Never
   implemented, and the hardest of these to operationalise.
3. **Closing the animal service gap.** Animals get 2.17 of the ~4 actions a day they want. That
   gap is the single clearest inefficiency left, and unlike every reallocation tried, closing it
   does not trade one need against another.
