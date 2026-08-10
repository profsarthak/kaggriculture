# The opening: they buy animals, we buy land

`docs/23-what-beats-us.md` left one question open. The strong builds carry 13.9 animals at day 12
against our 6.4, and neither a bigger crew, a bigger working area, nor a different animal mix gets
us there. So the difference had to be in the first two weeks, and the replays record it exactly.

## What the top five do

Money, animals, structures and quadrants over the opening. These are five different players, and
the first, second and fifth traces are nearly identical to one another — a shared approach, not
one agent.

| | day 0 | 2 | 4 | 6 | 8 | 10 | 12 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **opponent A** (193,918) | | | | | | | |
| money | 3,000 | **23** | 52 | 947 | 506 | 2,525 | 14,392 |
| animals | 0 | **4** | 5 | 6 | 10 | 12 | 14 |
| structures | 0 | **6** | 6 | 6 | 12 | 12 | 14 |
| quadrants | 1 | 1 | 1 | 1 | **2** | 2 | 3 |
| **opponent B** (179,245) | | | | | | | |
| money | 3,000 | 27 | 217 | 105 | 19 | 275 | 5,354 |
| animals | 0 | 3 | 3 | 4 | 5 | 9 | **20** |
| structures | 0 | 7 | 7 | 8 | 10 | 14 | **20** |
| quadrants | 1 | 1 | 1 | 1 | 2 | 2 | **4** |

The pattern is uniform: **spend the entire opening balance on livestock and structures inside two
days, run at near-zero cash, and buy the first quadrant around day 8 out of animal income.**

## What we do

Our own market orders over the same window:

```
day 0 hour  1   money 2,980   BUY_SEED MELON 5, BUY_SEED WHEAT 12, BUY_LAND
day 0 hour  3   money 1,460   BUY_SEED MELON 3
day 0 hour  5   money 1,220   BUY_SEED MELON 1
day 0 hour  7   money 1,140   BUY_SEED MELON 1, BUY_SEED WHEAT 2
...
day 4 hour 17   money   500   BUY_SEED WHEAT 3
day 5 hour  1   money   390   SELL WHEAT 81
day 5 hour  5   money 2,226   BUY_ANIMAL COW 1        <- first animal, day 5
```

Land on day 0. First animal on **day 5**, funded by the first wheat harvest. By the time our herd
starts, theirs has been producing for three days and has ten more head.

## Two things wrong, both in the opening

**Land is bought before anything else.** `BUY_LAND` fires whenever `money > price + 1500`, and
that is true at hour 1 of day 0. It takes 1,000 coins — two and a half cows — at the only moment
in the game where livestock cannot be bought any other way. The livestock order below it never
fires, because it counts *vacant built structures* and there are none yet.

**We buy seed for tiles that are already planted.** `wanted` counted every tile carrying a crop
role, not every tile that could be sown. A melon tile keeps its MELON role all season, so the
count never fell: we bought 5 seeds, planted them, saw an empty seed store and bought 5 more.
Those five sat unplanted for the rest of the game. **10 melon seeds for 5 tiles — 400 coins**,
spent on day 0. The same applies to wheat up to its cap of 12.

Together that is roughly 1,400 coins of the opening 3,000 committed to things that do not
compound, in the window the replays say decides the game.

Both are now switchable: `land_from_day` and `seed_to_demand`.

## Results: every version of their opening loses

| variant | margin | h2h |
|---|---:|---:|
| `seed_to_demand` (stop buying seed for planted tiles) | +239, CI [−632, +1,110] | 7/16 — inconclusive |
| `land_from_day=8` | **−52,005** | 0/16 |
| both together | −53,734 | 0/16 |
| `buy_feed` + `land_from_day=8` | −32,300 | 0/16 |
| `buy_feed` + `land_from_day=4` + `melon_tiles=3` | −26,349 | 0/16 |

The seed fix is real and worth almost nothing — 400 coins on day 0 does not measurably change the
season, which is itself worth knowing given how confident the opening-capital story sounded.

**Delaying land is a disaster, and the instrument says why.** One quadrant is 25 tiles. Our layout
wants 5 melon, 14 pastures and roughly 28 wheat for feed — 47 tiles. Restricted to NW, the wheat
is what gets cut, and the herd starves: animal-days fall 460 → 264, fed drops 98% → 80%, and **22
animals are lost**. The mechanic audit already established that missed feeds roughly halve an
animal's output, so this compounds.

Their build survives on one quadrant precisely because it does not grow feed — 5.5 wheat tiles for
13.9 animals. So the coherent version of their strategy is *compact plus animal-first plus bought
feed*, and that was tested too. It also loses, by 32,300.

## The conclusion

Eight A/Bs across two sessions have now tried to move our agent toward the field's strongest
profile — herd composition, animal mix, feed source, crew size, working area, land timing, and the
opening itself, alone and in combination. **One of them worked** (dropping geese, +4,078). Every
other one lost, most of them decisively.

The pattern is consistent enough to be the finding: **our strategy is internally coherent, and it
cannot absorb pieces of theirs.** Our layout planner, feed logic and build budget are all built
around a land-and-wheat farm. Their opening depends on machinery we do not have. Porting a knob
from their build into ours reliably breaks something load-bearing in ours.

That is not an argument that their approach is worse. They score 150,000 and we score 100,000 at
our best. It is an argument that **closing the gap means rebuilding around their strategy rather
than importing it** — a different agent, not a better-tuned one.

## What this says about the earlier conclusions

`docs/23-what-beats-us.md` concluded the herd is capital-bound rather than labour-bound. This
sharpens it: the herd is bound by capital **in the first five days specifically**. After day 12
money is not scarce — we reach 20,000 by day 20 and 70,000 by day 28 with the herd stuck at 13.
Every coin spent before day 5 buys an animal that produces for twenty-five days; the same coin on
day 20 buys almost nothing.

That also explains why raising `pasture_target`, `hands_target` and `labour_headroom` all failed.
They add capacity we cannot fill, because the constraint binds a fortnight earlier.
