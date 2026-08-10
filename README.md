# Kaggriculture — my first agent

An entry for [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture), a Kaggle
simulation competition. It is the first autonomous agent I have written: a program that plays a
game on my behalf, thousands of times, while I am asleep.

This repository is the whole record — the agent, the instruments built to measure it, and
twenty-nine documents covering what worked, what didn't, and the several occasions I measured
something wrong and had to take it back.

> **Status:** frozen. Standing as of 11 August 2026: **rank 2075 of 3687**, rating 643.8, win rate
> **198/405 (49%)**. The competition closes 30 September 2026 and this repository stays private
> until then — the rules permit sharing code only if it is made available to every participant.

---

## The game

Two players run neighbouring farms for thirty in-game days. You plant crops, raise animals, hire
help, and sell what you produce. Whoever has more money at the end wins. That is the whole
victory condition — not profit, not efficiency, just *more than the other farm*.

You never play it yourself. You write a function, upload it, and Kaggle runs it against other
people's functions. Each turn your function receives the state of the board — where your workers
are standing, what is growing, what everything currently sells for — and returns what every
worker does next. It makes that decision **720 times per game, in under a second each time**.

A day is 24 turns and a worker does one thing per turn: take a step, plant, water, harvest, feed
an animal, carry something to the shed. So the real currency is not money, it is **worker-turns**,
and almost every interesting decision is about what not to spend them on.

Three details do most of the strategic work:

**Prices move when you sell.** Every product has an equilibrium stock level. Sell below it and you
get a scarcity premium; sell above it and you get a glut discount. Milk's base price is 160 — I
have seen the same 250 units of it fetch $260 each in one game and $95 in another.

**The market is shared.** Both farms sell into the same pools, and the town drains those pools on
a fixed schedule. So your neighbour's production affects your prices. This is the only part of the
game where the opponent exists at all — the two farms never touch otherwise.

**Both farms are public.** You can see the opponent's board every turn, including what they have
planted and when. Melon takes ten days to mature, so you can watch a commitment coming for a week
and a half before it reaches market.

---

## What I built

A greedy planner, roughly 1,500 lines, in three layers:

1. **Layout** — decide once per turn what each patch of land is for: pasture, melon, wheat, coop.
2. **Task generation** — walk the farm and emit every job that wants doing, each with a priority.
   Feeding an animal outranks watering a crop; both outrank planting.
3. **Assignment** — hand jobs to workers, discounting each job by how far the worker has to walk.

Around that sits the part I did not expect to spend most of my time on: **instruments.**

| tool | what it answers |
|---|---|
| `ab.py` | Is this change better? Paired, seat-swapped, head-to-head. |
| `analysis/audit.py` | Does the game actually work the way I think? (20 rules, driven against the engine) |
| `analysis/knobs.py` | Does this setting change *anything at all*? |
| `analysis/field.py` | What do the strong opponents build, day by day? |
| `analysis/opponents.py` | How do they spend their worker-turns? |
| `ladder.py` | What is happening on the live leaderboard? |

---

## What I actually learned

The agent is mid-table. The findings are the interesting part, and most of them are negative.

### Measuring is harder than building

Thirteen structural changes are documented as rejected. Two were adopted. The ratio is the point:
**almost everything that seemed obviously good turned out not to be.**

Worse, small positives kept evaporating. Four separate changes read positive at 16–20 games and
converged to nothing at 48:

| change | 20 games | 48 games |
|---|---|---|
| assignment as a matching | +1,639 | **+734, 20/48** |
| early hiring cap | +971 | **+392, 21/48** |

I now treat anything under ~1,500 coins as unmeasured until it has 48 games behind it, and the
first reading as systematically flattering.

### The obvious fix is usually not the fix

Workers were wasting **59% of all pickup actions** standing on locked shed tiles — a real,
verified bug. Fixing it properly cost **15,299 coins**. Twice more I recovered wasted actions and
twice more the score did not move. The agent was never action-limited: it already idled 14% of the
time, so recovered actions had nothing to do.

### The competition is a prisoner's dilemma, and my own testing was hiding it

Both farms sell into one pool, so producing less would keep prices high for both. Measured over
four configurations:

| our score | opponent floods | opponent restrains |
|---|---:|---:|
| **we flood** | 75,747 | **80,195** |
| **we restrain** | 71,755 | 79,096 |

Flooding wins whatever the opponent does, yet mutual restraint pays both more than mutual
flooding. There is no way to reach the cooperative cell — opponents are anonymous and matched once.

The methodological sting: I had been triaging ideas by playing the agent against *itself*, which
only ever samples the diagonal of that table. It compares mutual-restraint to mutual-flooding and
recommends the dominated strategy. Two separate good-looking ideas died on this — restraining
production, and holding stock for a better price. Both looked like the best idea of the project in
self-play and lost decisively head-to-head.

### The strong builds are worse at everything I was optimising

Reading opponents' full action streams out of the replays: they move more than I do (50.5% of
turns vs 46.2%), get fewer actions per visit (1.59 vs 1.80), and idle less only because they have
more to do. Their advantage is a bigger crew — about 15 workers to my 10 — which pays for them
because their farm generates the work for it, and doesn't for me because mine doesn't.

That closed the last open question. The gap is not execution.

### A bug hiding inside a bug check

An audit I wrote reported "0 market orders truncated past the 10-per-turn cap." It was measuring
the *engine's* truncation. My own code was trimming the list first — silently discarding every
hire past the tenth and never retrying, capping the crew at 11 however high I set the target. A
silent failure living inside a check for silent failures.

---

## Honest accounting

- **Adopted:** an end-of-season sweep (+3,301), a layout-planning fix (+3,305), removing coops
  entirely (+4,078).
- **Rejected with measurements:** thirteen structural changes, including a complete second
  architecture built over one day and abandoned the same day.
- **Retracted:** several claims I made confidently and later disproved with my own data — a noise
  model that grew when it should have shrunk, an explanation for a regression that my follow-up
  refuted, and a "strictly dominates" that rested on eight games.
- **Not reached:** top ten needs a rating around 3,080. I am at 643. That is not close, and no
  amount of the tuning I was doing would have closed it.

The competition awards $5,000 each to the top ten. I am not going to be one of them. What the
project produced instead is a way of working: build the instrument before trusting the number,
write down the failures, and check whether the thing you just "fixed" actually changed anything.

---

## Repository layout

| path | what |
|---|---|
| `farmlib.py` | the agent — decision core, parameterised by a 54-field `Config` |
| `build.py` | flattens it into one submittable file (Kaggle `exec`s the source, so imports break) |
| `ab.py` | paired seat-swapped A/B testing — the instrument every adoption had to clear |
| `tune.py` | coordinate descent over the config, using `ab` as the objective |
| `bench.py` | absolute scores plus a health report that catches silent breakage |
| `ladder.py` | pulls submissions, episodes and replays from the live competition |
| `analysis/` | the model of the game, and the diagnostic tools listed above |
| `docs/` | 29 documents: derivations, findings, negative results, decision log |

Start with [`docs/overview.md`](docs/overview.md) for the long-form plain-English version, or
[`docs/15-negative-results.md`](docs/15-negative-results.md) if you would rather go straight to
what didn't work.

## Running it

```bash
pip install kaggle-environments
python bench.py                  # play some episodes, print a health report
python ab.py --variant melon_tiles=8 --n 12    # is that change better?
python -m analysis.audit         # do the game's rules behave as documented?
```

## Licence

Code and documentation are released under [CC BY 4.0](LICENSE). Replay data is not included —
it contains other competitors' play, and the cached analysis in `data/` is anonymised.
