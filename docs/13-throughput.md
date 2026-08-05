# Throughput, round two

After the routing rework travel sat at 51% of worker turns. `analysis/travel.py` attributes it
rather than guessing again.

## Diagnosis

| | value |
|---|---:|
| moves that are commute (shed → first tile) | 16.1% |
| moves that are hops between tiles | **83.9%** |
| **actions per tile visit** | **1.40** |

Visit-depth distribution: 967 visits ended after **one** action, 273 at two, 135 at three, and
exactly **one** ever reached four.

That last number is the finding. An animal tile wants four actions — `FEED`, `CARE`, `HARVEST`,
`COLLECT_FERTILIZER` — and only one can be taken per turn, so a worker that leaves after one
pays the walk back. It was leaving because urgent watering (priority 95) outranks `CARE` (72),
pulling workers off mid-tile every single turn.

## Fixes

**Finish the tile you are standing on.** A phase before urgent assignment: any worker occupying
a tile with pending work takes it. Standing work costs no movement, so it is close to strictly
better than walking somewhere for work of similar value.

Measured: **+2,371, 12/12**, CI [+1,566, +3,175].

**A latent bug found alongside it.** `task_map` was built with a dict comprehension keyed on
position, so for a tile with four pending tasks it kept the *last appended* — which is the
lowest priority of the four. It now keeps the highest. This also affected route resumption in
phase 2, so workers resuming a route were targeting the least valuable action on the tile.

**Feed carry 6 → 4.** `PICKUP` costs one turn regardless of quantity, and a worker loaded with
feed it will not use is a worker that skipped a fetch it needed. Measured **+2,632, 20/20**,
CI [+2,017, +3,247].

## Result

| | before | after |
|---|---:|---:|
| work | 31.6% | **33.1%** |
| move | 51.2% | **44.5%** |
| idle | 17.2% | 22.4% |
| actions per visit | 1.40 | **1.76** |
| self-play | 52,700 | 53,472 |

## The idle is not convertible, and that is odd

Idle rose to 22.4%, which by the pattern established twice before should mean the farm is now
too small for the workforce. It does not:

| `labour_headroom` | paired margin |
|---:|---:|
| 0.54 | −6,720 |
| **0.58 (current)** | — |
| 0.50 | −3,177 |
| 0.45 | −10,175 |
| 0.40 | −5,576 |

Lowering it grows the farm as intended (0.58 → 48 tiles, 0.50 → 55, 0.45 → 62) but every
setting loses. So the spare worker turns cannot be spent on more land — presumably because the
marginal tiles are further from the shed and the extra coops compete for early capital with
melon.

This is worth flagging as unresolved rather than papering over: **we have ~22% of worker turns
idle and no measured way to use them.** The layout's cost model says labour is saturated when
observation says it is not, so the model is wrong somewhere. Finding out where is the most
likely source of the next real gain.

## Knobs re-swept and holding

`travel_weight` 8 (5 is −1,482 with the CI crossing zero, 12 is −10,506, 16 is −8,802);
`fertilizer_quota` **inert** at +0 for both 16 and 25, like `goose_target` — capped elsewhere;
`feed_carry` 2 is −365 and 10 is −3,654, so 4 is the peak.
