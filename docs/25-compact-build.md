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

## Open, in priority order

1. **Milk per animal-day is 0.51 against the current build's 0.72**, with the same 99% fed and 99%
   cared and no starvation. Animal harvests run at one per 2.9 animal-days against 1.2. Workers are
   idle at the same time, so it is not a labour shortage — the harvest tasks are not being taken.
   Not yet isolated, and it is the single largest item: closing it is worth roughly 25,000.
2. **The farm needs more to do.** With PASS at 19–34% the compact build should either work more
   tiles (melon, animals) or hire fewer hands. `hire_to_demand` already cuts the crew to 6.
3. **Sheep, revisited.** The top builds run 8 cows and 6 sheep. Sheep lost by 13,489 in the
   sprawling build; the pool arithmetic may differ once milk is 65% of income and concentrated.
4. **Late wheat.** Their wheat ramps 6 → 24 between day 20 and day 28, planted when melon can no
   longer mature. We leave those tiles bare — `repurpose_melon` was rejected at −1,392 under the
   old layout and deserves a retest here.
