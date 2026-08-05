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
