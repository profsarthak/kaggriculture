# Routing rework

## The problem

Assignment was re-decided from scratch every turn. A worker three steps into a five-step walk
could be re-targeted before arriving, so the walk was wasted. Measured: **65.1% of worker turns
spent moving, 29.2% working**.

The earlier travel-weighted ranking (`priority − travel_weight × distance`) helped, but it only
changed *which* task got picked; it did nothing about the lack of commitment between turns.

## The fix

Three phases per turn, replacing the single global greedy:

1. **Urgent work, globally ranked, allowed to preempt.** Anything at or above `PREEMPT_ABOVE`
   (90) — `FEED`, `FETCH_WHEAT`, `WATER_URGENT`. Starvation and weeding are irreversible, so
   they outrank route locality.
2. **Honour routes in progress.** A worker walking to a tile keeps walking to it, unless the
   task has disappeared or become impossible.
3. **Idle workers take the nearest remaining work**, scored from *their own* position rather
   than by global rank — so finishing one tile chains into an adjacent one instead of sending
   the worker back across the farm.

Routes are held in the agent closure and cleared whenever worker identity could have changed:
hands are re-hired each morning and arrive as market orders *after* the hour-0 actions, so
indices only mean the same thing within a day and only once the day's hires have landed.

## Result

Isolated with `route_commit=false` as the control:

| | value |
|---|---:|
| paired margin | **+6,405** |
| 95% CI | [+6,212, +6,598] |
| head-to-head | 12/12 |
| per-seed stdev | 241 |

| worker turns | before | after |
|---|---:|---:|
| working | 29.2% | **32.1%** |
| moving | 65.1% | **51.1%** |
| idle | 5.7% | 16.8% |
| mid-journey reversals | 5.3% | **1.8%** |

## It unlocked more land

Cutting travel left workers idle 25.7% of the time — the farm had become too small for the
workforce. Re-sweeping `labour_headroom` (which sizes the working area against the labour
budget) moved the optimum from 0.65 to **0.58**: +5,761, 16/16, CI [+5,565, +5,957].

This is the second time a change has only paid off once a *different* parameter was re-tuned
behind it. Worth treating as the default expectation rather than a surprise: after any change
to throughput, re-sweep the size knobs.

Re-checked at the new setting, everything else holds: `hands_target=9` −5,568, `=10` −4,771;
`melon_tiles=11` −6,989. `goose_target` at 20 or 24 scores **exactly +0**, meaning the flock is
capped by the labour budget rather than by the target — the knob is currently inert.

## Where this leaves us

| | before | after |
|---|---:|---:|
| self-play | 30,548 | **38,997** (sd 1,148) |
| vs `starter` | 39,486 | **50,730** |

The self-play figure is the one that matters: **38,997 against a measured field average of
39,640**. On that comparison we are now at parity with the field, where we were at 67% before
this rework. That is a like-for-like comparison only insofar as self-play mimics a contested
market — it is still our own agent on both sides, so it is not proof of ladder parity, and the
ladder is the only real test.

Health: **zero animals ending unfed**, down from 3.6/episode. The 22 weeds/episode still
includes spontaneous spawns on unfarmed unlocked land (see `docs/07-routine.md`), so it remains
directional only.
