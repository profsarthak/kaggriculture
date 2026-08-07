# Two A1 predictions tested, both negative

Both of these follow directly from Phase A analysis, and both fail in practice. Recording them
because they look obviously correct on paper and would otherwise be retried.

## Metering sales into shallow pools — no effect

A1 established that milk floors after 76 units and wool after 59, against town demand draining
~20–26/day, and concluded: *"with an active shop, sell at the drain rate, not in bulk. Dumping
59 wool at once floors it; selling 20/day into 20/day of demand holds it near base
indefinitely."*

Implemented as a per-turn `sale_cap` on the shallow products:

| cap | paired margin |
|---:|---:|
| 1/turn | −72 |
| 2/turn | −60 |
| 4/turn | −30 |
| 8/turn | −4 |

Uniformly slightly negative, converging to zero as the cap loosens. **The reasoning is sound but
the premise does not hold at our production volumes.** Two cows produce 1.5 milk/day against a
drain of ~20/day, so we never accumulate enough to move the price at all — there is nothing to
meter. Metering would matter for a milk-heavy strategy; ours is not one, and A4's shallow-pool
logic already keeps it that way.

## Fertilising melon — a loss at every harvest timing

The agent collects fertilizer from the animals and sells all of it, never using any. A2 says
fertilizer doubles the per-day watering bonus for three days, which should take melon to its cap
of 6 at age 8 rather than 10 — two days off an 11-day cycle, on a tile earning far more per day
than the ~$50 the fertilizer sells for.

| variant | paired margin |
|---|---:|
| fertilise melon, harvest unchanged (day 10) | −4,861 (0/10) |
| fertilise melon, harvest day 9 | −13,043 |
| fertilise melon, harvest day 8 | −57,192 |

The first row is explicable: the cost is paid — a `PICKUP` trip plus the `FERTILIZE` action, plus
the forgone sale — and the days saved are thrown away waiting for the old harvest date.

The second and third rows are the real finding, and they falsify the premise. **Fertilizer only
doubles the bonus on days the plant is also watered**, and the cheapest surviving melon schedule
waters on *alternate* days through the early window (0, 2, 4, then daily from 6). So the cap is
not actually reached at age 8, and harvesting then collects a part-grown melon. Harvesting two
days early is catastrophic precisely because the yield is not there.

Making fertiliser pay would require watering melon every day from age 6, which costs more
worker-turns than the fertilizer saves — and worker-turns are the binding constraint
(`docs/13-throughput.md`).

Both stay as config switches (`sale_cap`, `fertilize_crops`) defaulting off, so the results are
reproducible rather than folklore.

## Ladder note: the cows build did not separate from v4

v5 (cows, +11,673 in self-play) versus v4: **605.2 against 606.4 after 15 episodes — a gap of
−1.2.** v5 led by +33.8 early and regressed to parity.

This is the clearest calibration point yet on how much offline margins are worth: a
+11,673 paired self-play gain has so far produced **no measurable ladder separation**. Self-play
is our own agent on both sides, so it rewards changes that beat *ourselves*, which is not the
same as beating the field. Worth holding in mind before treating any offline number as banked.

## Shed tile sharing — −15,299 (0/20)

Workers waste 466 PICKUP actions per episode standing on LOCKED shed tiles, 59% of all pickups.
`shed_lock_aware` filtered those tiles and measured −2,153; I blamed the lost parallelism and
proposed sharing an unlocked tile between several workers, which nothing in the interpreter
forbids. Implemented as `shed_shared`, it cut PICKUP no-ops from 58% to 12% and raised real
pickups, harvests and waterings — and measured **−15,299, CI [−19,752, −10,845], 0/20**.

Two explanations checked and both refuted: the action mix improves rather than degrades, and the
fetch loop is not starving either animal type. Herd mix shifts from 11 cows/4 geese to 8 cows/7
geese, which accounts for the size of the loss but not the cause. Left off. See
docs/21-mechanic-audit.md.

## Raising `pasture_target` to 10 — inconclusive, and inert

Cow count correlates +0.44 with final money, so the herd looked worth pushing. `pasture_target=10`
measured 7/16 with a per-seed stdev of 978 — inside ±700 of zero. `plan_layout` caps pastures at
`remaining // per_pasture` and the labour budget binds far below 10, so the knob does nothing.

## Feed strategy — three variants, three different failures

Prompted by the field profile: the top 25 opponents grow ~5.4 wheat tiles, we grow 36.4.

- **`max_extra_wheat=0`** — −544, CI [−2,294, +1,207], 6/16. Inconclusive. Only ~4 tiles are
  surplus; the rest are feed reserve. Free to drop, but worth nothing.
- **`feed_ratio=1.25`** (the steady-state break-even) — **−26,326, 0/16.** Instrumented: 24
  animals starve, only 84% of production days end fed. Wheat arrives in ~5-day batches while
  animals eat daily, so the theoretical ratio leaves no buffer, and a missed production day
  destroys the care bonus (docs/21-mechanic-audit.md).
- **`buy_feed=true`** — **−32,625, 0/16.** The implementation is fine: 100% fed, nothing starves.
  It loses because animal-days fall 534 → 328. Capital spent on wheat is capital not spent on
  animals.

The herd is capital-bound, not labour-bound. See docs/23-what-beats-us.md.
