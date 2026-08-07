# The layout planner has no memory, and it has been overriding our knobs

Chasing the one positive lead the mechanic audit produced — cow count correlates +0.44 with final
money — turned up something bigger than the lead itself: **the farm we build is not the farm we
configure.**

## The farm does not match the plan

`plan_layout` is called every turn. It takes the unlocked tiles, sorts them by distance to the
shed, and hands out roles in quota order: melon, then pastures, then coops, then wheat. With the
default config the quota is 5 melon, **7 pastures, 9 coops**.

The farm finishes with **11–12 pastures and 4–5 coops.**

Traced over one season, one farm:

| | |
|---|---:|
| tiles holding the PASTURE role at any one time | 7 (always) |
| **distinct tiles that held the PASTURE role at some point** | **19** |
| distinct tiles that held the COOP role at some point | 27 |
| tiles that held *both* roles at different times | 10 |

The plan is recomputed from a blank board every turn, and the tile ordering shifts whenever a land
purchase widens `unlocked_quadrants` — newly unlocked tiles interleave by distance rather than
appending. So the pasture window slides onto fresh ground, a second pasture gets built there, and
the first one still stands. `DIG` refuses to remove a stocked structure, so nothing ever
reconciles. Structures accumulate wherever the window has been.

Because pastures come first in the quota order, they win the accumulating race and the coops get
starved of `build_budget`.

## This explains an observation we had already recorded and not understood

`docs/decisions.md` lists `goose_target` among "three inert knobs" — parameters that produced the
silent-failure signature of identical results across a sweep. It was filed as a curiosity.

This is why. The knob sets a quota that the drift then overrides. The same applies to
`pasture_target`, which is why raising it to 10 measured inside ±700 of zero. **Two of the
parameters governing the core of our strategy have never actually been under our control**, and
four tuner passes were sweeping them against a mechanism that ignored them.

## A second bug found while fixing the first

`goose_target` was doing double duty: the coop quota *and* the cap on total structures, via

```python
build_budget = max(0, min(cfg.goose_target, animals_alive + stockable) - structures)
```

So lowering `goose_target` to shift the herd toward cows does not rebalance the herd — it starves
it. Two screens run before I spotted this measured **−26,585** and **−41,606**, both 0/8. Those
numbers are the structure cap biting, not a verdict on herd composition, and would have been
badly misleading if I had reported them as one. Under `layout_pinned` the cap is now the sum of
the two quotas.

## Fixing it makes the agent worse

`layout_pinned` counts structures that already exist against the quota. It does exactly what it
should — the farm finishes with 7 pastures and 9 coops, matching the plan for the first time.

| config | herd | seed 0 | seed 1 |
|---|---|---:|---:|
| current (drifting) | 11 cow, 3–4 goose | 82,042 | 87,017 |
| pinned, quota 7/9 | 6–7 cow, 9 goose | 69,702 | 77,661 |
| pinned, quota 12/5 | 11 cow, 4 goose | 77,657 | 82,577 |
| pinned, quota 14/3 | 13–14 cow, 2 goose | 84,541 | 79,908 |

Honouring the configured quota is **clearly worse**. The bug has been accidentally building a
better farm than the one we asked for, which is the same thing as saying our configured targets
are wrong and the drift has been hiding it.

Note the third row: quota 12/5 reproduces the drifting herd exactly — 11 cows, 4 geese — and still
scores below it. So the drift is not *only* a herd-composition effect. Pinning also removes
structure tiles from the pool the melon and wheat windows draw on, pushing those roles onto
further ground. That is a plausible cause and I have not established it; recorded as unexplained.

## Verdict

`layout_pinned=true, pasture_target=14, goose_target=3` — pin the quotas, then set them to what
the drift had been accidentally discovering, and a little further.

Paired mirror A/B, 6 seeds both ways: **10/12 = 83%**, variant better.

Panel, 8 seeds against each archetype:

| opponent | margin | 95% CI | wins |
|---|---:|---|---:|
| **mirror** | **+2,708** | [+68, +5,347] | 11/16 |
| melon-contest | +38,398 | [+35,927, +40,870] | 16/16 |
| no-cows | +47,288 | [+45,106, +49,470] | 16/16 |
| field-like | +52,572 | [+48,821, +56,324] | 16/16 |
| melon-rush | +55,878 | [+50,912, +60,844] | 16/16 |
| goose-engine | +51,907 | [+47,492, +56,321] | 16/16 |
| | **average +41,458** | | **worst case +2,708** |

Beats every panel member. The panel margins against the weaker archetypes are large but not very
informative — those are our own discarded builds. **The mirror is the number that matters, and it
is +2,708 with a lower bound of +68.** That clears zero by the project's adoption rule and not by
much, so it was confirmed on a larger mirror sample before the defaults changed.

Confirmation, 18 seeds both ways: **+3,305, 95% CI [+1,122, +5,488], 26/36 = 72%.**

Combined mirror evidence: **47/64 = 73%.** Adopted as the default:
`layout_pinned = True`, `pasture_target = 14`, `goose_target = 3`. Submitted as v12.

## What this means regardless of the A/B

Two things stand whatever the final measurement says:

1. **`pasture_target` and `goose_target` are not trustworthy knobs in the current build**, and any
   sweep over them — including the four tuner passes already run — was measuring a mechanism that
   partly ignored them.
2. **Any future work on layout has to fix this first.** A planner that re-derives roles from a
   blank board each turn, on a board whose tile ordering changes under it, cannot express a
   deliberate strategy. That matters more for architecture work than for tuning.
