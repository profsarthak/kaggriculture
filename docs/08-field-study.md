# Field study — first ladder data

## v3 beat v2 on the ladder

| submission | rating | local vs starter |
|---|---:|---:|
| v3 (travel weighting, CARE fix, feed-aware layout) | **551.8** | 36,522 |
| v2 | 441.5 | 27,014 |

+110 rating. The local improvement transferred, which is the first evidence that our offline
benchmark tracks the ladder at all — though see the caveat below about `starter`.

Standing after 9 scored episodes: win rate 3/9, us averaging 23,757 against a field averaging
35,648.

## What the strongest opponent does

The strongest opponent in that sample beat us 79,254 to 17,421.

| day | money | hands | quadrants | animals | crops |
|---:|---:|---:|---:|---:|---|
| 0 | 594 | 5 | 1 | 3 | **carrot 17** |
| 6 | 83 | 5 | 1 | 3 | melon 17 |
| 9 | 11 | 6 | 2 | 7 | melon 17 |
| 12 | 250 | 9 | 2 | 9 | **melon 29** |
| 15 | 12,023 | 10 | 2 | 13 | melon 19 |
| 21 | 39,600 | 11 | 2 | 16 | melon 19 |
| 29 | **79,254** | 9 | 2 | 19 | — |

Sell orders: fertilizer 34, wheat 31, milk 18, wool 15, melon 14. They bought **6 cows**.

Five differences from us: a **carrot opening** (3-day cycle, faster capital than wheat's 4),
a far larger **melon commitment** (29 tiles vs our 8), **cows and sheep** rather than only geese,
running at **near-zero cash** through day 12 — total reinvestment — and **19 animals on 2
quadrants**.

Worker efficiency: **36% working / 63% moving**, against our 29% / 65%.

## Copying their parameters does not work

Each variant played head-to-head against the current config, 5 seeds:

| variant | us | current config | wins |
|---|---:|---:|---:|
| `fertilizer_quota=25` | 29,065 | 28,577 | 1/5 |
| `melon_tiles=18` | 23,500 | 27,434 | 0/5 |
| `land_purchases=1` | 28,154 | 28,332 | 1/5 |
| `hands_target=10` | 21,423 | 31,819 | 0/5 |
| all three combined | 25,232 | 27,713 | 0/5 |

**Not one is an improvement, and melon 18 is a clear loss.** That is the informative result:
their configuration is not portable because our *execution* cannot support it. We cannot water
18 melon tiles — our weeds climb to 21 by day 29 and the melon count decays. They can, because
they spend 36% of turns working where we spend 29%.

The gap is throughput, not parameter choice. This is worth stating plainly because the obvious
next move — tune toward what the winner does — is measurably wrong.

## Negative result: buying feed

Hypothesis: animals pack 4 actions/day onto one tile where a wheat tile spreads 1.2 actions/day
across many, so buying feed should free both tiles and travel for a denser animal operation.

| variant | us | current | wins |
|---|---:|---:|---:|
| `buy_feed` | 6,053 | 30,850 | 0/5 |
| `buy_feed, goose_target=24` | 6,053 | 30,850 | 0/5 |
| `buy_feed, goose_target=30, melon 12` | 8,435 | 31,286 | 0/5 |

Identical scores across different flock sizes is the tell — a hard failure, not a gradient.
With feed bought, the layout spends its whole budget on coops and allocates **zero** wheat
tiles, so the flock depends entirely on purchases and starves whenever cash is tight. Wheat's
below-`I0` curve is `sqrt` at target 0.80, so ~400 units of purchased feed costs ~$14,000.

**A3's "grow feed, don't buy it" is validated under real test.** Kept as a config switch,
defaulting off, so the negative result stays reproducible.

## Where this leaves us

The current configuration is at a local optimum *for our agent's execution*. Further parameter
sweeps are not where the next gain is; travel is still 65% of worker turns and that is what
caps how much farm we can actually run.

Structural candidates, untested:

1. **Tour-based routing.** Workers re-decide every turn. Committing to a route that visits
   several adjacent tiles in sequence would cut the walk-back that the per-turn greedy causes.
2. **Carrot opening.** A 3-day cycle versus wheat's 4 compounds meaningfully over the early
   game, and the winner used it. Cheap to test.
3. **Cows and sheep.** We only run geese. Milk and wool have far higher base prices and the
   field averages 3.2 animals, so those pools are barely contested.
4. **Aggressive reinvestment.** We hold a cash floor and gate purchases at `money > 1500`; the
   winner ran at near zero through day 12 and bought everything immediately.
