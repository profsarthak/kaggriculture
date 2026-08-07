# Mechanic audit — driving every rule against the interpreter

The locked-shed-tile finding came out of scouting, not out of our own notes: half our shed
operations were silently failing and nothing in the repo knew it. That was luck. This is the
same search done deliberately — `analysis/audit.py` drives each rule the interpreter actually
implements and then counts what it costs us in real games.

Two parts, and the second is the one that matters:

- **Part 1** — scripted micro-episodes isolating one rule each. These say what the interpreter
  does. 20 checks, all passing.
- **Part 2** — instrumented full episodes of our own agent, counting what each rule destroys or
  blocks. A rule can be real and cost nothing.

That split exists because of the locked tiles: the mechanic was confirmed, the waste was
confirmed, and fixing it still measured −2,153. **Confirming a mechanic is broken is not the
same as confirming that fixing it helps.**

## Finding 1: feeding is not over-invested — the opposite

The hypothesis going in was that we over-feed. The interpreter adds `base = 1` on every
interval day *regardless of feeding* (kaggriculture.py:802); only the care bonus is gated on
`fed_today`, and the animal only leaves at `consecutive_unfed >= 2`. So alternate-day feeding
should keep the animal and its base yield at half the wheat and half the actions. We feed at
priority 100, second only to the endgame sweep, so the saving looked large.

Measured over 14 days, one animal, care on every fed day:

| | fed daily | fed alternate days | fed every 3rd day |
|---|---:|---:|---:|
| GOOSE | 24 eggs | **11 (46%)** | 0 — starved |
| COW | 15 milk | **4 (27%)** | 0 — starved |

Not 75%. The arithmetic missed line 806:

```python
bonus = tile.pop("pending_care_bonus", 0) if tile["fed_today"] else 0
tile["yield_units"] = min(a["max_held"], tile["yield_units"] + base + bonus)
tile["pending_care_bonus"] = 0        # <- runs even when the animal was not fed
```

An unfed production day **destroys** the banked care bonus rather than deferring it. For a goose
(interval 1, so every day is a production day) the bank is wiped the day after it is laid and can
never be claimed — alternate feeding collapses to exactly base 1/day, which is the 11 measured.

The cow is worse and for a second reason: at interval 2 its production days have a fixed parity
set by `placed_day`. Feeding on the opposite parity means it is *never* fed on a production day,
so it collects base only, forever. 4 milk against 15.

**Consequence: feeding daily is correct and FEED's priority is correct.** The lead is closed
against the direction I expected to find.

## Finding 2: the animal engine is already running at the mechanical ceiling

Having established feeding matters more than thought, the converse question is whether we are
missing feeds. We are not, at any margin worth chasing:

| | |
|---|---:|
| animal-days that ended fed | 1486/1562 = **95%** |
| animal-days that ended cared | 1542/1562 = **99%** |
| animal-days that banked a care bonus (fed *and* cared) | 1486/1562 = **95%** |
| **production days that ended fed** | 678/682 = **99%** |
| care bonus destroyed by an unfed production day | 2.7 units/episode |
| animals lost to starvation | **0** |

The number that matters is the fourth: 99% of the days that actually pay are paid in full. There
is no recoverable loss here.

## Finding 3: PICKUP wastes 59% of its actions, and fixing it costs 15,299

The broadest instrument in the audit counts every action that changed no state at all —
position, tile, inventory, shed, seeds. Per episode, both farms:

| op | issued | no-op | waste |
|---|---:|---:|---:|
| PICKUP | 788 | 466 | **59%** |
| DROP | 41 | 17 | 42% |
| everything else | 4,074 | 0 | 0% |

Every other action type is clean. Broken down by cause, the waste is almost entirely one thing:

| | per episode |
|---|---:|
| PICKUP standing on a LOCKED shed tile | 457 |
| DROP standing on a LOCKED shed tile | 17 |
| PICKUP where the shed had no WHEAT | 8 |

The four shed-access tiles sit one per quadrant, so one is locked from the start and stays locked
all game (we buy two quadrants of three). Workers walk to it and spend the turn on nothing.

`shed_lock_aware` filtered those tiles and measured −2,153, which I attributed to collapsing four
parallel fetch points to one and proposed a better fix: **also let several workers share an
unlocked shed tile**, keeping the parallelism without the dead trips. Nothing in the interpreter
limits a tile to one worker — `_set_farmer_position` has no collision check, and PICKUP/DROP act
on the worker's own inventory and the shared shed. The one-worker-per-position rule in `assign`
is ours, not the game's.

Implemented as `shed_shared` (which implies the filter). It does exactly what it was supposed to:

| | current | `shed_shared` |
|---|---:|---:|
| PICKUP no-ops | 442 (58%) | **64 (12%)** |
| real pickups | 324 | **464** |
| HARVEST | 622 | **690** |
| WATER | 1,326 | **1,445** |
| movement share | 46% | **44%** |

Strictly more productive work on every axis. And:

| | |
|---|---:|
| paired margin | **−15,299** |
| 95% CI | [−19,752, −10,845] |
| head-to-head | **0/20** |

Left off. I checked two explanations and both were wrong: the action mix is *better*, not worse
(above), and the fetch loop is not starving one animal type (COW fetch tasks emitted 102 vs 108).
What does change is herd composition — the same 15 animals, but 11 cows/4 geese becomes 8 cows/7
geese, and cows are the revenue core. The mechanism connecting shed sharing to herd mix is not
established, and I am not going to invent one; the measurement stands on its own.

**Two attempts, both negative, the second decisively.** The waste is real and is not recoverable
by these means. `shed_shared` stays in the config as a switchable false so the negative result is
reproducible.

### The herd-composition lead it threw off, and why it went nowhere

Across 8 seeds played both ways, cow count correlates **+0.44** with final money and goose count
**−0.31**, and the two within-seed splits both favour the cow-heavy side (seed 3: 12 cows/87,649
against 9 cows/74,915; seed 7: 11 cows/61,363 against 8 cows/53,827). Suggestive, and consistent
with cows being a perpetuity at a rising price where eggs are not.

It is not actionable through the obvious knob. `pasture_target=10` measured **inconclusive**,
7/16, with a per-seed stdev of 978 — a margin inside ±700 of zero. `plan_layout` sets
`pastures = min(cfg.pasture_target, remaining // per_pasture)`, and the labour budget binds well
below 10, so raising the target changes almost nothing. The observed herd variation is drift in
which tiles end up as pastures over a season, not something `pasture_target` controls.

Recorded as observational. If herd mix is worth chasing it needs a mechanism that actually moves
it, and that is a layout question rather than a tuning one.

## Finding 4: the shed cap binds, but cheaply

Peak occupancy reaches 100/100. What it costs:

| | per episode (both farms) |
|---|---:|
| units destroyed by the end-of-day refresh | 9.3 |
| units destroyed by DROP into a full shed | 0.0 |
| purchases refused because the shed was full | 0.0 |

Worth knowing that a full shed **blocks `BUY_PRODUCT` and `BUY_ANIMAL` outright** (`_commit_unit`
returns False at capacity) — that would be a silent failure to buy the wheat the animals eat. It
has never fired for us.

`DROP` deletes whatever does not fit (`del inv[item]` runs unconditionally); `PLACE` moves
`min(n, room)` and keeps the rest. The final-day sweep uses `DROP`, so it is exposed to this in
principle — measured at 0.0 units lost, because the shed is nearly empty by then. Recorded as a
known risk rather than fixed, since fixing it would cost an action per item type instead of one
for the whole inventory.

## Finding 5: rules confirmed with nothing to act on

- **The market order cap never binds.** 1,005 orders/episode, 0 truncated past the 10/turn limit.
  Orders are line items, not units, so `["SELL", "MILK", 30]` costs one slot — but each `HIRE` is
  its own order, so a 9-hand morning spends 9 of 10 slots. We have never crossed it.
- **The watering window holds.** Watering only adds yield inside
  `[(max_yield_day+1)//2, max_yield_day]`; outside it, it is pure survival. Three waterings inside
  WHEAT's 2–4 window yield 4 units, adding a fourth at age 1 yields the same 4. `CROP_INFO`
  already models this and the agent already waters on alternate days outside the window.
- **Planting day counts as unwatered** (`consecutive_unwatered = 1`), so a crop unwatered on its
  planting day weeds at the first refresh. Already handled by the urgent-watering rule.
- **Hire cost is `fib(hires_today)` and resets every day**: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89,
  144, 233. Nine hands cost 88/day — trivial. The 10th, 11th and 12th cost 55+89+144 = 288/day on
  top, or 8,640 a season, which is where it stops being trivial. `hands_target = 9` sits right at
  that knee.
- **Last acting step is `episodeSteps − 2`** (718 of 720 — day 29, hour 22) and the final day gets
  no end-of-day refresh, which is what the final-day sweep exists for. Unit actions resolve
  *before* the market in the same turn, so a `DROP` and a `SELL` issued together on the last turn
  both land.
- **SELL draws from the shed only.** Carried stock is unsellable.

## What the audit says overall

Twenty rules checked, twenty hold. One large waste found, already known, and now closed for the
second time with a much stronger measurement. The animal engine — the core of the strategy — is
running at 99% of its mechanical ceiling.

That is a real result and not a comfortable one: it says the remaining gap to the top of the
ladder is **not** mechanical. We are not leaking value to rules we misread. Whatever the stronger
agents are doing differently, it is a different plan, not a cleaner execution of ours.
