# How the strong builds spend their worker turns — and the ceiling we put on ourselves

The last open question was throughput: the top opponents service 15 animals and 11 melon tiles on
roughly 34 worked tiles where we need 62. Replays record the opponent's **full action stream**, not
just the board, so the attribution `analysis/travel.py` runs on us can be run on them.
`analysis/opponents.py` does that.

## Their routing is worse than ours

Aggregated over the top 8 opponent performances (8 distinct players), against our own play in the
same games:

| per game | them | us |
|---|---:|---:|
| **peak crew** | **~15** | ~9.6 |
| move | 50.5% | 46.2% |
| work | **38.7%** | 33.1% |
| idle | **10.8%** | 20.6% |
| actions per tile visit | 1.59 | **1.80** |
| total work actions | **21,666** | 16,691 |

They move *more* and get *fewer* actions per visit. Every efficiency measure we have been trying to
improve, they are worse at. They win on **crew size** — about 15 workers doing 30% more total work.

That also explains our 20.6% idle against their 10.8%: our farm runs out of jobs, theirs does not.

## A ceiling we imposed on ourselves

Setting `hands_target` above 10 changed nothing, and the reason is ours, not the game's. The
hour-0 hiring block built one `HIRE` order per wanted hand and then returned
`orders[:MAX_MARKET_ORDERS]` — **silently discarding every hire past the tenth, and never trying
again that day.** The crew was hard-capped at 10 hands plus the farmer whatever the config said.

`hires_today` persists through the day and the n-th hire costs `fib(n)` whenever it happens, so
splitting the request across the first hours costs nothing. `hire_hours` does that, and the crew
reaches 16.

Note the earlier audit reported "0 orders truncated past the 10/turn cap". That measured the
*interpreter's* truncation. We were truncating our own list before submitting it, so the
interpreter never saw the overflow — a silent failure hiding inside a check for silent failures.

## But a bigger crew does not pay

| | seed-0 money |
|---|---:|
| shipped (crew 10) | **90,984** |
| crew ramped to 16 | 53,762 |
| crew ramped to 16, gentler gate | 71,587 |

Head-to-head the ramped crew measures **−14,755, 0/20**.

A k-hand crew costs `fib(k+2)−1` per day — 88 at nine hands, 376 at twelve, **1,596 at fifteen** —
and the whole crew is re-hired every morning. That is trivial against a late-season bank and ruinous
against an early one, and hiring settles before the livestock order, so an over-large crew eats the
herd. The deeper problem is that the extra hands have nothing to do: our idle was already 20.6%.
Their crew pays because their farm generates the work for it.

## What does transfer: the early half of the ramp

Their crew is not flat. It is **smaller than ours early and larger late** — about 5.5 hands through
day 6 against our 9.4, then 14.6 by day 22 against our flat 9.6.

The early half transfers on its own. `hire_budget_frac` caps the daily hire bill at a fraction of
the bank, so the crew starts smaller while capital compounds hardest:

| | crew d0/2/4/6/10/16/24 |
|---|---|
| shipped | 7/7/7/10/10/10/10 |
| `hire_budget_frac = 0.03` | 7/7/7/**8/8**/10/10 |
| top opponents | 6/5/6/6/10/11/15 |

| sample | margin | 95% CI | h2h |
|---|---:|---|---:|
| 20 games | +971 | [+244, +1,699] | 11/20 |
| panel mirror, 16 games | +762 | [−91, +1,614] | 8/16 |
| **48 games** | **+392** | **[+3, +781]** | **21/48** |

**Not adopted.** The margin converges toward zero as the sample grows and the win rate is 44% over
48 games. This is the same shape as `assign_swap` (+1,639 → +1,362 → +734, 20/48) and the fourth
time a small early positive has evaporated under a larger sample. The panel worst case never
cleared zero either.

The lesson is about the instrument as much as the change: **at these effect sizes a 16-game read is
not evidence.** Anything under about 1,500 coins needs 48 games before it means anything, and the
first reading will usually flatter it.

## What this closes

Throughput was the last question with a concrete method, and the answer is that **their advantage is
not execution.** Their execution is worse than ours on every measure. They field a bigger crew,
which works for them because they have more animals and more melon to service — and we cannot add
either, because the shared pool is a prisoner's dilemma in which we are already playing the dominant
strategy (docs/26-common-pool.md).

The bug is real and worth keeping fixed. The gap it appeared to explain, it does not.
