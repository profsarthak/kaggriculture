
# Iteration cadence

## The 5/day cap is not the binding constraint

The rule that actually sets the pace is different: **only the latest two submissions are
scored** (Evaluation page). Those two slots are a champion/challenger pair. Submit a third and
you displace the champion, discarding the comparison you were trying to make.

So the currency being spent is not submissions — it is *time in the matchmaking pool*. A
submission earns episodes by sitting there. Five submissions in one day means three of them
stop accruing episodes almost immediately and you learn nothing about any of them.

**Use at most one challenger at a time.** The champion keeps accumulating while the challenger
catches up, and the rating gap between them is a controlled comparison on the same ladder
against the same bracket.

## How long is long enough

Set by effect size, because rating moves on win/loss only:

| true win rate vs the bracket | episodes to distinguish from 50% |
|---:|---:|
| 70% | ~50 |
| 60% | ~200 |
| 55% | ~800 |

This is why the cadence should start fast and slow down, and it is not a matter of taste:

- **Early changes are large.** Opponent-awareness is worth up to $20,702 in A4's matrix; the
  watering fix addresses 13.5 weeds/episode. Effects that size resolve in ~50 episodes.
- **Later changes are small.** Parameter tuning moves win rate a couple of points, which needs
  hundreds of episodes to see at all.

At the accrual rates typical of a fresh submission, ~50 episodes is roughly a day and ~800 is
one to two weeks. So: **daily while the changes are structural, weekly once it is tuning.**
`ladder.py` measures the real accrual rate rather than assuming one, and reports how many more
days a given effect size needs.

## Win rate stops being the metric

Matchmaking pairs you against similarly-rated bots, so a *successful* agent converges toward a
50% win rate by construction. A win rate near 50% at a high rating is the target state, not a
failure — the wrong reading would be to keep churning submissions chasing a number that cannot
go up.

Once rating stabilises, the comparison that matters is the **rating gap between champion and
challenger**, which is what `ladder.py` reports. It treats a gap under 50 points as too close to
call and recommends holding rather than submitting again.

## Current policy

| | |
|---|---|
| Data pull | every 6 hours, Task Scheduler → `KaggricultureLadder` |
| Submissions | ≤1 challenger at a time; hold until the gap resolves or ~50 episodes accrue |
| Phase | structural changes → daily; tuning → weekly |
| Never | submit a third while a champion/challenger comparison is live |

## First live datapoint

Submission 55270084 passed validation and seeded at rating 600. Its first opponent ran **12
melon tiles** at day 12 — so the field does contest melon, and A4's assumption that it would
was not misplaced. Against an opponent at 12 tiles, A4's best response is our current 8. One
episode proves nothing; it is recorded here because it is the first evidence either way.
