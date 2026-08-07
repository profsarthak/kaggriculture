# Decision log

Newest last. One entry per change that altered the agent or a conclusion, with the evidence
that justified it. This file plus `docs/0*.md` is the methodology record the competition rules
require of winners.

---

## 2026-08-05 — Baseline agent (v1): parallel wheat loop

**What.** Hire 8 hands each morning, assign each worker its own tile in the starting quadrant,
run plant → water → harvest on wheat, sell the shed each turn, buy the second quadrant at
$4,000.

**Why.** Wheat has the shortest cycle in the game (first yield day 2, max yield day 4) and its
`above_func` is `log`, so oversupply barely moves the price. Chosen as a floor to beat, not as
a strategy.

**Result.** vs `random`: 5,906 – 0. vs `starter`: 6,704 – 3,491. Single games each, so this is
directional only.

**Known gaps.** No animals, no fertilizer, never plants the land it buys, ignores
`town["unlocked_shops"]`, dumps the whole shed in one order.

---

## 2026-08-05 — A1: market model verified

**What.** `analysis/market.py` recomputes the sell-side depth and town regeneration for all 9
products from the installed interpreter.

**Gate result.** PASSED. All 9 resources reproduce the README's published `P(I0−T)`,
`P(I0+T)`, `P(I0+2T)` checkpoints exactly. Downstream conclusions are safe to act on.

**Findings that change strategy** (detail in [01-market.md](01-market.md)):

1. Wheat and egg are the only unbounded income streams (`log` decay). Egg averages $34.6/unit
   over 20,000 units vs wheat's $17.6.
2. Fertilizer is the only pool with *zero* regeneration — $25,045 fixed, shared, and free to
   produce from animals. Sharpest edge found.
3. Melon regenerates only 140/season against 158 depth: ~300 units exist for the entire game
   across both players.
4. Premium crop value is contingent on random shop unlocks; shallow pools should be sold at
   the town's drain rate rather than in bulk.

**Correction to an earlier assumption.** Base price is a bad guide to product value.
Strawberry's entire season pool is $3,809 — less than a day of egg production — despite a
$120 base.

**Next.** A2 (labour accounting). The binding constraint is still unknown; if it's worker-turns
rather than market depth, the shallow-pool analysis matters less than it currently appears.

---

## 2026-08-05 — A2: labour accounting; the binding constraint is land

**What.** `analysis/labour.py` derives actions-per-unit for every crop and animal, and compares
labour capacity against land capacity. Detail in [02-labour.md](02-labour.md).

**Answer to the open question from A1.** **Land binds, not labour** — but only if you hire
properly. Labour binds below ~10 hands; land binds above. The crossover is at nine or ten
hands, costing $143/day, which is noise. So: hire to ~10, buy all three expansions ($7,000),
and the ceiling is ~44 geese on 100 tiles.

**This invalidates the v1 baseline's design.** It hires 8 hands and works 25 tiles — labour
-saturated on a quarter of the board it could own. Expansion is not a late-game luxury here;
it is the constraint.

**Correction to how A1's findings should be read.** I added a capacity column, because
`$/action` alone is actively misleading. Sheep are the best per-action row in the game
($63.72) and the whole wool pool is 44 sheep-days — one and a half sheep for a season. Melon
is $92.56 and 26 plants exhaust it. Only wheat and geese have unbounded capacity; everything
else is a bounded raid, and should be planned as an opening move rather than an engine.

**Also.** Fertilizer's zero-regenerating pool is a 16-animal problem: past ~16 animals,
`COLLECT_FERTILIZER` is a wasted action and animal economics drop to product-only. The
$/action figures above include fertilizer and should be re-read without it for larger fleets.

**Next.** A3 (allocation LP). First thing it must settle: grow feed wheat or buy it. Buying
frees ~1.25 tiles per goose but drains inventory along wheat's steep below-`I0` `sqrt` curve.

---

## 2026-08-05 — Verification of A1 and A2; one model error found and fixed

**What.** `analysis/verify.py` drives real episodes with scripted agents and checks predictions
against the interpreter. A1's gate had only compared three published price points; A2 had never
been run at all. 7/7 checks now pass.

**Model error found — A2 undercounted animal labour.** Every worker's inventory is emptied into
the shed at the end-of-day refresh, so feed does not survive the night. A worker that skips the
morning `PICKUP` silently no-ops its `FEED`, and the animal starves after two unfed days. My
first goose script did exactly that and the animal escaped on day 2, which is how this surfaced
— the failure is completely silent in the observation.

Animal daily actions now include a share of one morning feed pickup (amortised over
`ANIMALS_PER_WORKER = 5`). Effect: goose $/action 25.60 → 24.38, cow 44.33 → 41.93, sheep
63.72 → 60.11.

**Conclusion unchanged.** The labour/land crossover moves from ~9–10 hands to ~10, so land still
binds and the A2 headline stands.

**Finding worth exploiting in Phase B.** `CARE` banks +1 per fed-and-cared day and pays the
whole bank out on the *next* scheduled production, capped at `max_held`. Caring for an animal
through its pre-production growth days therefore front-loads a bonus onto the first harvest:
+1 egg for a goose, and more for cows and sheep whose longer intervals accrue a bigger bank.

**Verified correct as modelled:** wheat 4 units, carrot 3, melon 6 under the cheapest surviving
watering schedule; goose steady state exactly 2 eggs/day fed+cared; 1 free fertilizer/animal/day;
buy-then-sell round trip nets exactly zero.

**Also verified — the information structure the whole plan rests on.** The opponent's `farms`
entry exposes their crop *and* `planted_day`, and their money; their shed, seeds and carried
inventories stay private. So premium commitment really is observable ~10 days ahead, and A4's
anti-coordination argument is sound.

---

## 2026-08-05 — A3: allocation LP. Corrects A2's binding-constraint conclusion.

**What.** `analysis/allocate.py` maximises season revenue over tiles-per-crop and animal counts
subject to land, labour, market depth, shed cap, and the wheat feed balance. Concave revenue is
piecewise-linearised, so it stays an LP. Detail in [03-allocation.md](03-allocation.md).

**Correction to A2 — labour binds at the optimum, not land.** A2's capacity arithmetic was
right (labour binds below ~10 hands, land above) but its implication was wrong. It assumed
you'd hire past the crossover. The LP prices two things A2 didn't: hire cost is Fibonacci *and
charged daily* (the 12th hand is $9,024 across a season), and marginal revenue per worker
collapses once the shallow pools are drained. The optimum stops at 6–9 hands with labour
saturated and 6–11% of the land idle.

**Correction to A2 — do not buy the third land expansion.** It costs $4,000 and returns $1,378.
Buy the first two ($1,000 + $2,000) and stop. A2's "buy land aggressively, $7,000 for 4× the
ceiling" was wrong for the same reason: once labour binds, land is nearly worthless.

**Answered: grow feed, don't buy it.** The LP buys zero wheat. Wheat's below-`I0` curve is
`sqrt` at target 0.80, so purchased feed escalates faster than the land it frees is worth.

**Movement turned out not to matter.** Between 0% and 50% travel overhead the optimum moves
1.7% of revenue and three hires, with essentially the same allocation. This was the largest
unmodelled gap after A2; it does not need pathfinding in Phase B.

**Shape of the answer.** A diversified raid, not a monoculture: drain every finite pool to near
its cap (melon 143/158, fertilizer 451/493, wool 50/59) and run geese for the unbounded
remainder. The animal count is set by the *fertilizer* pool — 20 animals × 24 days ≈ the 493
units available — not by egg economics.

**Upper bound, not a plan.** ~$96k assumes capital is on hand; you start with $3,000 and the
allocation needs ~$7,000 of livestock. Bootstrapping is a sequencing problem the LP cannot
answer, and it is the first thing Phase B has to solve.

**Next.** A4: how the melon and fertilizer pools divide against a contesting opponent. The LP
above drains them to near their caps with no competition, so this is where its numbers are
most fragile.

---

## 2026-08-05 — A4: contested pools. Corrects A3; finds the largest single decision in the game.

**What.** `analysis/pools.py` replays the interpreter's lockstep settlement for two simultaneous
sellers, builds payoff matrices over commitment levels, and solves each as a zero-sum game.
Payoffs are (my revenue − theirs), net of the uncontested egg alternative at $14.72/worker-turn.
Detail in [04-pools.md](04-pools.md).

**Biggest finding in Phase A: the melon first-mover premium is $12,790.** Eleven melon tiles
each, harvesting simultaneously, pays $13,366 a side. The same eleven tiles selling into an
untouched curve pays $26,156 against $459. Melon needs 10 days to first yield, so this is
settled in the first day or two of the season and cannot be recovered afterwards. It is larger
than any other single decision found in Phase A.

Consequence for Phase B: melon goes in the ground immediately, and its harvest is sold on
arrival rather than stockpiled. Holding for a better price is how you hand the curve away.

**Corrects A3 — melon commitment 11 tiles → 8.** Eleven was the monopolist's answer. Against an
equilibrium opponent it loses $1,447: over-committing floods the pool and the extra labour would
have earned more on geese. Conceding entirely is far worse (−$20,702 against an 11-tile
opponent), so this is not a pool to sit out.

**Corrects A3 — fertilizer collection 20 animals → 8.** A3 set the animal count at 20 because
20 × 24 days ≈ the 493-unit pool. Contested, the equilibrium collection is ~8 animals' worth.
This does *not* mean keeping only 8 animals — eggs are unbounded and uncontested, so keep the
fleet and throttle the `COLLECT_FERTILIZER` action instead. Past ~8 animals it earns less than
the egg alternative and accelerates the flood.

**Best-respond, don't play the equilibrium.** Opponent crop and `planted_day` are public
(verified). The payoff matrix is a best-response table the agent should index by counting the
opponent's melon tiles. 8 tiles is correct against everything except an opponent who concedes
entirely, where 11 is better.

**Phase A is complete.** Next: Phase B, the agent portfolio. First problem it has to solve is
the one no analysis in Phase A can — bootstrapping from $3,000 to the ~$7,000 livestock
position A3 assumes, while getting melon planted on day 0.

---

## 2026-08-05 — Phase B: agent v2. 6,704 → 27,014.

**What.** `farmlib.py` holds the decision core parameterised by `Config`; `main.py` instantiates
it so Phase C can fork strategies without duplicating logic. `bench.py` scores over seeded
episodes *and* inspects the final board for silent breakage. Detail in [05-agent.md](05-agent.md).

**Result.** 15 seeded episodes vs `starter`: mean 27,014, 15/15 wins, stdev 1,052. Four times
the v1 wheat loop (6,704) and 7.7× the opponent (3,500).

**The health harness earned its keep three times.** Every one of these looked like "a slightly
lower score" and would have shipped:

1. *The entire goose engine never ran.* `PLACE` takes the animal from the acting worker's
   inventory; I only checked the shed. 14 empty coops/episode while the score sat at 12,728 and
   climbing.
2. *Hired hands never collected feed.* Inventories empty overnight, so `FEED` silently no-ops.
   My first fix ran the pickup at hour 0 — but hires are market orders settled *after* player
   actions, so hands don't exist yet at hour 0. Had to become a standing task.
3. *Coops built that could never be stocked*, wasting the build action and the tile.

**Corrects A3 — travel does matter, a lot.** A3 modelled it as a flat multiplier and found the
optimum moved 1.7% between 0% and 50% overhead. A real greedy assignment behaves nothing like
that: working every unlocked tile scatters tasks over 75 tiles and collapses throughput.
Restricting to a compact subset near the shed was the single largest change in Phase B
(7,778 → 19,518). A3's conclusion that *land is not binding* stands; its implication that the
agent can therefore ignore geometry does not.

**Corrects A3 — hands 6, not 6–9.** Twelve hands scores about half as much (11,586 vs 22,075)
despite a healthier board. Direction right, magnitude understated.

**Open, in rough order of expected value.** Watering is still behind (13.5 weeds/episode); only
6 animals get placed against A4's equilibrium of 8; the agent ignores A4's best-response table
entirely and plays a fixed 8 melon tiles regardless of what the opponent does; and there is no
margin-conditioned risk despite the payoff being `sign(M_i − M_j)`.

---

## 2026-08-05/06 — Overnight session: 27,014 → 68,826 self-play

Detail in [07-routine.md](07-routine.md), [08-field-study.md](08-field-study.md),
[09-ab-testing.md](09-ab-testing.md) through [16-panel-testing.md](16-panel-testing.md).

### Measurement came first, and twice invalidated earlier conclusions

**Paired, seat-swapped A/B (`ab.py`).** Every comparison before this ran the variant as player 0
against the baseline as player 1 and compared means. `HIRE` and `BUY_LAND` settle in player
order, so that partly measured the *seat*. Swapping seats and pairing dropped the per-seed stdev
to ~430, so **3 seeds now resolves a 500-coin effect** where the old method could not separate
29,065 from 28,577 over five. Several earlier "clearly worse" verdicts were unreliable.

**The agent is deterministic** — identical configs produce a paired margin of exactly 0 with 7 of
10 seeds ending in exact ties. Sample size means *distinct seeds* and nothing else.

**Panel testing (`ab.py --panel`).** Self-play rewards beating ourselves. A variant is now scored
against five strategies and adopted on the **worst case**.

### Adopted

| change | measured |
|---|---:|
| 5 cow pastures | +11,673 for the first two, then +3,326 at 5 |
| route commitment across turns | +6,405 |
| coordinate-descent config (melon 7, hands 9) | +10,070 as a set |
| hire to demand, floored at 6 | +3,370 |
| feed carry 6 → 4 | +2,632 |
| finish the tile you stand on | +2,371 |
| headroom 0.58 → 0.55 | +1,532 |
| end-of-season investment cutoffs | +1,066 |
| `PLACE` priority 75 → 90 | +967 |

### Rejected, with data

Carrot opening (−13,963), fertilising melon (−4,861, and worse at every earlier harvest date),
buying feed (−24,800), sale metering (no effect), angular worker zones (travel got *worse*),
copying the field's parameters wholesale (three separate failures).

### Three mistakes worth remembering

**Reading noise as signal.** v5 sat 18 points below v4 and I called it a failure to transfer.
Rating standard error is ~`16·√n` — about ±62 at 15 episodes — so a 18-point gap means nothing.
`ladder.py` said "too close to call" and was right.

**Searching to the edge of the grid.** The first tuner run reported a local optimum with
`pasture_target` at 4, which was simply the highest value in its list; 5 measures +3,326 beyond
it. Ranges must extend past the current value in both directions.

**Reasoning from static pool depth.** I justified capping the herd on milk's 76-unit depth, but
with shops unlocked the town drains ~680 milk a season. The pool refills; the raw depth is the
wrong number to plan against.

### Silent-failure signature

A parameter that changes nothing produces *identical* results, not a gradient. That signature
caught the dead carrot feature (flat −4,175 across every value), the layout bootstrapping bug
(~1,283 with zero variance), and three inert knobs (`goose_target`, `fertilizer_quota`, `FERT`
priority). Worth checking for whenever a sweep looks flat.

### Standing
v12 submitted, plus `goose_target = 0` queued (+4,078, panel worst case +4,078). Rank 1,389 of
2,748 at rating 695.8 against a field median of 701 — we are the median team, and the prize band
starts at 3,057.

**The architecture is at its ceiling, and the ceiling is not efficiency.** Three separate attempts
to convert wasted worker actions into score have failed — `shed_shared` (−15,299), the same change
inside the compact build (idle 19% → 34%, no score change), and `assign_swap` (+734, 20/48). Idle
already sits at 14.4%. The agent is not action-limited, so recovering actions buys nothing.

Nor is it a strategy gap that can be imported. Eleven A/Bs have now tried to move this agent toward
the field's strongest profile — herd composition and mix, feed source, crew size, working area, land
timing, the opening, and a full compact rebuild. Two worked (`layout_pinned` +3,305,
`goose_target=0` +4,078); the rest lost, most decisively.

And the herd cannot move in either direction: expanding measures −4,022 and restraining −9,160,
because the shared pool is a prisoner's dilemma in which flooding strictly dominates
(docs/26-common-pool.md).

What remains unexplained is throughput per tile: the strongest opponents service 15 animals and 11
melon tiles on roughly 34 worked tiles where we need 62, and none of the levers we have found
account for it.

### Layout drift — the knobs were not connected

`plan_layout` recomputed roles from a blank board every turn, on a tile ordering that shifts when
a land purchase widens `unlocked_quadrants`. The pasture window slid across 19 distinct tiles in
one season and built 11–12 pastures against a quota of 7, starving the coops. **`pasture_target`
and `goose_target` have been effectively inert for the whole project** — which is exactly the
"inert knob" signature already recorded above for `goose_target`, now explained rather than
filed as a curiosity. Four tuner passes swept them against a mechanism that ignored them.

`layout_pinned` counts existing structures against the quota. Honouring the *configured* 7/9
scores worse than the drift, because the drift was accidentally building a better farm than the
one we asked for. Retuned to 14 pastures / 3 coops: **+3,305 (26/36, CI [+1,122, +5,488])**,
panel worst case +2,708, beats every panel member. Adopted, submitted as v12.

Also fixed: `goose_target` was doubling as the cap on total structures in `build_budget`, so
lowering it to shift the herd starved the herd instead. Two screens run before I noticed measured
−26,585 and −41,606 — the cap biting, not a herd-mix verdict.
