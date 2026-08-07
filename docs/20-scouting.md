# Scouting public repositories — two corrections and a real gain

Prompted by hitting a local optimum: an automated search finds nothing, nine structural ideas
have been rejected, and we sit at a 49% win rate against matched opponents. That is an
architecture ceiling, not a tuning problem, so it was worth seeing what others had published.

`scout.py` collects public repositories mentioning the competition, tracks what is new since the
last run, and pulls descriptive files. **Read for approach, not to copy strategy code** — both on
principle and because winner obligations would require open-sourcing whatever we submit.

37 public repos found. Most carry the competition's own boilerplate README; roughly six describe
an actual approach.

## Correction 1: prices rise all season, so pool depth never binds

One repository claimed prices sit above base all game, because the town drains faster than a
single farm produces. **Verified in our own episodes:**

| day | WHEAT | EGG | MELON | MILK | FERTILIZER |
|---:|---:|---:|---:|---:|---:|
| base | 25 | 50 | 250 | 160 | 100 |
| 0 | 26 | 50 | 256 | 169 | 100 |
| 10 | 21 | 54 | 277 | 208 | 98 |
| 25 | **42** | **64** | **283** | **269** | **65** |

Milk finishes **68% above base**. Only fertiliser falls — the one product with zero town drain,
which both analyses independently identified.

**This corrects A1's headline.** The arithmetic there was right: pool depths are exactly as
computed, and `analysis/verify.py` confirms the price model. But it described a *static* market,
and the real one is drained continuously. At our production levels the depths never bind, so
"pool depth tells you almost everything" is wrong as stated — it is the right frame only for
fertiliser, and for a producer far larger than us.

Worse, A1's price table (used to rank every allocation in A2 and A3) priced milk at **$81**
against an actual **$160–269**, and melon at $168 against $256–283. Premium products were
understated two- to three-fold throughout.

The conclusion that survives, ironically strengthened: **cows are the core of the strategy** —
they are a perpetuity at a rising price, where crops are not.

Tested the obvious implication — spending melon's budget on livestock — and it fails: melon 0
scores −14,056, melon 2 −11,533, melon 3 −10,348. Melon stays at 5.

## Correction 2: the last day has no end-of-day refresh — adopted, +3,301

The same repository noted the agent acts on steps 0–718 and **day 29 has no end-of-day refresh**,
so anything still in a worker's hands at the end is simply lost.

Measured in our own play at day 29, hour 22: workers carrying **23 wheat, 15 fertiliser, 10 eggs
and 15 milk** — roughly **$6,600 at late-season prices, evaporating every game.**

Fixed with a final-day sweep: from `endgame_hour` on the last day, any worker holding anything
runs it into the shed with `DROP`, which empties the whole inventory in one action. Feed carried
at that point is worthless anyway — there is no refresh left to feed for.

| | |
|---|---:|
| mirror margin | **+3,301** (17/20) |
| panel worst case | **+4,682** |
| trigger hour | 8 (4–12 all within noise; 18 gives +929, 20 gives +445) |

Realised gain is below the $6,600 lost because the delivery trips cost actions, but it is one of
the larger single wins of the project and cost an afternoon of reading.

## What this says about the exercise

Two hours of scouting produced a correction to our foundational market analysis and a gain
larger than most of a week's tuning. Neither was reachable by optimising harder — one required
reading the interpreter differently, the other required knowing a timing detail we had never
checked.

Both were *verifiable*: we confirmed the price claim in our own episodes and measured our own
losses before fixing anything. Nothing was taken on trust.

## Other approaches noted, not yet tried

Several repositories describe **layered planners** — a strategic layer assigning tile roles once
per day, a tactical layer assigning worker actions per turn — which is close to what we already
do. Two mention **MCTS** or **reinforcement learning** as future work rather than implemented.
One reports the same finding we did about working a much smaller farm than the land allows,
having swept the equivalent of our `labour_headroom` to a similar conclusion.

Nothing seen so far suggests a fundamentally different architecture is being used successfully.
That is mild evidence that the ceiling we hit is the game's, not ours — but the leaderboard says
otherwise, so it is more likely that the strongest competitors simply have not published.
