# The compact animal-first build — work in progress

A second strategy rather than a tweak, built because eight attempts to import single features from
the field's strongest profile all failed (docs/23, docs/24). Gated behind `compact = False`; the
shipped agent is byte-identical until this earns its way in.

**Status: functional but well behind. 47,656 against the current build's 90,984 on seed 0.**

## What the trajectory profiler changed

`analysis/field.py` extends `ladder.py`'s single day-12 fingerprint to a whole-season trajectory.
It immediately corrected the premise this work started from.

The herd gap closes. The top ten reach 15 animals by day 12 and freeze; we reach 13. By day 22 the
difference is **+2**, not the +5 the day-12 snapshot suggested. Meanwhile the money gap opens to
**+56,041** by day 28.

The difference is land use, and it is stark:

| at day 20 | top 10 | us |
|---|---:|---:|
| animals | 14 | 11 |
| melon tiles | 11 | 8 |
| wheat tiles | **6** | **28** |
| worked tiles, roughly | **34** | **62** |

**They make nearly twice the money on a farm half the size.** Our labour goes into growing feed.

## Where our money actually comes from

Revenue and spend by product, seed 0, instrumented at `_commit_unit`:

| | current build | compact build |
|---|---:|---:|
| MILK | **66,439** | 41,041 |
| MELON | 16,533 | 18,998 |
| FERTILIZER | 12,410 | 12,487 |
| WHEAT | 7,184 | 0 |
| **revenue** | **102,566** | 72,526 |
| spend on bought WHEAT | 2,710 | **15,310** |
| spend on livestock | 5,200 | 7,200 |
| **final** | **90,984** | 47,656 |

Milk is 65% of our income. The compact build loses 25,398 of it *despite carrying more animals*,
gives up 7,184 of wheat revenue, and pays 15,310 to buy the feed it stopped growing. Melon gains
only 2,465. That is the whole gap.

## Two mistakes made and fixed along the way

**A deadlock.** The first version gated feed buying behind the herd reaching 60% of target, to stop
feed purchases outbidding livestock. The herd reached 8, never hit the gate, was never fed, and
collapsed to zero — final money 10,634. A gate on herd size cannot work, because the herd cannot
grow without being fed.

The real problem was never a missing gate: **orders settle in sequence against one purse, so
position is priority**, and feed and seed were queued ahead of livestock. That is also why
`buy_feed` measured −32,625 in the first place — every animal stayed fed while animal-days fell
534 → 328. The compact build now splices livestock in ahead of feed. Herd holds at 14, 99% fed,
nothing starves.

**Building the whole quota ahead.** Allowing structures to be built ahead of the cash to stock them
is right — a structure costs an action, not money — but going all the way to the quota built 14 by
day 2 against a target of 5, taking fourteen tiles out of production with nothing to put in them.
Now a margin of 3.

## The finding that reproduced

Fixing the pickup waste inside the compact build does not convert into money:

| | money | PICKUP no-ops | PASS |
|---|---:|---:|---:|
| compact | 47,656 | 1,946 of 2,335 (83%) | 1,829 (19%) |
| + `shed_lock_aware` | 37,681 | 0 of 473 | 3,103 (32%) |
| + `shed_shared` | 49,574 | 20 of 575 (3%) | 3,311 (34%) |

Buying feed keeps the shed permanently stocked, so fetch tasks fire every turn onto shed tiles that
are mostly locked while we sit on one quadrant — 24% of all actions, almost all wasted. Removing
the waste turns it into **idle time, not work.**

This is the second time this has reproduced (the first was `shed_shared` in the current build,
−15,299). It is a real property: **the recovered actions have nothing better to do.** The compact
farm at 34 tiles is labour-*surplus*, which contradicts A3's founding conclusion that labour is the
binding constraint. That holds for the sprawling build and not for this one.

## Isolated: it was never production, it was price

The milk shortfall is not a production or harvesting problem. Instrumented at the daily refresh,
both builds produce **1.24 units per animal-day** and lose the same 7% to the `max_held` cap, with
100% of production days fed. The compact build produces *more* in total — 647 against 564.

The difference is entirely what the milk sells for:

| | units sold | realised price | revenue |
|---|---:|---:|---:|
| current build | 255 | **$260.5** | 66,439 |
| compact build | 274 | **$149.8** | 41,041 |

Milk's base is 160. The current build sells into a pool the town has drained *below* `I0`, so every
unit takes a scarcity premium. The compact build's larger herd pushes the same pool above `I0` and
collects a glut discount instead. **Nineteen more units sold, 25,000 fewer coins.**

## The pool split, and a correction to the sheep rejection

If the constraint is pool absorption rather than production, the fix is to sell into two pools.
Measured on the compact build at seed 0:

| | money | milk | wool |
|---|---:|---:|---:|
| 15 cows | 47,656 | 274 @ $150 | — |
| **9 cows + 6 sheep** | **71,340** | 120 @ **$281** | 132 @ $223 |
| 7 cows + 8 sheep | 41,862 | 57 @ $317 | 177 @ **$88** |

Splitting recovers 23,684. Over-splitting floods wool instead — its above-`I0` curve is `sq` with a
3.20 target, the steepest in the game, so it collapses from $223 to $88 between 132 and 177 units.
The optimum sits near sheep ≈ pastures ÷ 3, which is close to the field's own 8 cows and 6 sheep.

**This corrects docs/15's sheep entry.** Rejecting sheep at −13,489 was right for the build it was
tested on and wrong as a general claim. The sprawling build sells 255 milk at $260 — it never
floods the pool, so there is nothing for a second pool to relieve, and sheep only cost more per
animal. The value of an extra animal depends on which pool its output lands in.

Direct evidence on the current build, seed 0: **18 pastures of cows scores 66,431; the same herd
with 5 sheep scores 94,118.** Same animal count, opposite result.

## Where it stands

| build | seed-0 money |
|---|---:|
| current (shipped) | **90,984** |
| compact, buy feed, 15 cows | 47,656 |
| compact + 6 sheep | 71,340 |
| compact + 4 sheep, 12 pastures | 75,097 |
| compact + sheep, grow feed, land bought early | **82,369** |

The compact architecture is still behind, and the pieces that helped it most were the ones that
undid it — growing feed rather than buying it, and buying land on day 0. What survives is the pool
split, which is an insight about the market rather than about the layout.

Tested on the shipped build, the split measures **+577, CI [−1,787, +2,940], 8/20 — inconclusive**,
because that build already sits in the scarcity regime. (`pasture_target` clamps to the labour
budget above 14, so 17 and 18 are the same config; the two A/Bs returning identical statistics is
that, not a bug.)

## Open, in priority order

1. **The compact opening is not paying for itself.** Every variant that improved it moved it back
   toward the shipped build. Worth one more pass on melon count and crew size before calling it.
2. **Late wheat.** Their wheat ramps 6 → 24 between day 20 and day 28, planted when melon can no
   longer mature. We leave those tiles bare — `repurpose_melon` was rejected at −1,392 under the old
   layout and deserves a retest.
3. **Melon is also priced, not just produced.** It realises $244–254 against a 250 base, so it sits
   near equilibrium; more melon tiles may run into the same glut wall that milk did.
