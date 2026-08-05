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
