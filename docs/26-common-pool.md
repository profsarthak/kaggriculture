# The shared pool is a prisoner's dilemma, and mirror self-play cannot see it

The project opened by modelling this game as *single-agent scheduling ⊗ a depletable-common-pool
quantity game on the sell side*, structurally Cournot. That framing sat in `docs/00-model.md` for
the whole project without ever being measured. It is now measured, and it changes how to read every
mirror self-play number we have taken.

## Revenue is hostage to a random shop unlock

The milk pool is drained by three of the eight shops (`PIZZA_SHOP`, `ICE_CREAM_SHOP`,
`SMOOTHIE_SHOP`), and shops unlock one every three days in a **random order**. Same agent, same
strategy, three seeds:

| seed | first milk shop | milk sold | realised price | milk revenue |
|---:|---:|---:|---:|---:|
| 0 | day 3 | 255 | $260.5 | 66,439 |
| 1 | day 3 | — | — | — |
| 2 | **day 9** | 249 | **$95.5** | **23,786** |

Milk's base is 160. On seed 2 the town is not draining milk while we produce it, the pool goes into
glut, and the price falls to $95.5 — the same 250-odd units earn **29,000 less**. That single seed
is most of why our final scores range from 45,593 to 90,984.

`docs/00-model.md` predicted exactly this — "premium pools are shallow but shop-fed, so their value
is contingent on a random unlock order... observable, and currently ignored" — and it is still
ignored. `obs["town"]["unlocked_shops"]` is in every observation we receive.

## Splitting the herd looks excellent and is a trap

If one pool floods, sell into two. On a 3-seed mirror screen, trading 2 cows for 4 geese looked
clearly better: mean 79,496 against the shipped build's 72,934, with far lower variance (the
shipped build's disastrous seed-2 45,593 disappears — 12 cows and 4 geese scores 78,254 there, with
milk back at $238 and eggs adding 6,123).

Head-to-head it measures **−9,160, 0/24.**

Both numbers are correct. They measure different games.

## The payoff matrix

Four configurations, 4 seeds, both seats, our own mean score:

| | opponent floods | opponent restrains |
|---|---:|---:|
| **we flood** (14 cows) | 75,747 | **80,195** |
| **we restrain** (12 cows + 4 coops) | 71,755 | 79,096 |

Flooding **strictly dominates** — better against a flooder (75,747 vs 71,755) and better against a
restrainer (80,195 vs 79,096). Yet mutual restraint pays both players more than mutual flooding
(79,096 against 75,747).

That is a prisoner's dilemma on the milk pool, and there is no mechanism in this competition to
reach the cooperative cell: opponents are anonymous, matched once, and cannot be signalled.

## The methodological consequence

**Mirror self-play only ever samples the diagonal of that matrix.** It compares (restrain,
restrain) against (flood, flood) and reports 79,096 against 75,747 — which recommends the dominated
strategy. Any measurement of a change that touches a shared pool, taken in mirror, is measuring the
cooperative outcome and will point the wrong way.

This retro-justifies `ab.py`'s design: paired *head-to-head* with seat swapping is the honest
instrument, and it is what every adoption in this project has actually used. But it condemns the
quick mirror screens used for triage — including several taken today on the compact build, where
splitting the herd into two pools scored 71,340 against 47,656. That number is the cooperative
outcome and overstates the case.

**Rule going forward: never triage a pool-touching change on mirror self-play.** The shipped
`bench.py` self-play figure has the same defect and should not be quoted as a progress metric for
anything downstream of the market.

## What it says about the shipped build

The shipped build already plays the dominant strategy. Its 14 cows flood milk, and that is correct
against opponents who cannot be coordinated with — restraint loses 9,160.

It also reframes what the field's strongest builds are doing. Eight cows and six sheep is **not**
restraint: it is fourteen animals across two pools, flooding both. They are not producing less, they
are using more total pool capacity than we can reach. Our attempts to match them by *expanding* also fail:

| change | margin | h2h |
|---|---:|---:|
| restrain — 12 pastures + 4 coops | −9,160 | 0/24 |
| expand — 14 pastures + 4 coops | −4,022 | 2/24 |
| expand — 18 pastures + 5 sheep | +577 (inconclusive) | 8/20 |

The labour budget clamps `pasture_target` above 14, and raising the budget loses on its own
(`hands_target=12` −3,726, `labour_headroom=0.45` −3,034). Neither direction is available.

So the position is a real local optimum: **we cannot expand, because labour binds; and we should not
restrain, because it is dominated.** The remaining gap to the top of the field is that they service
15 animals and 11 melon tiles on roughly 34 worked tiles where we need 62 — an execution difference
in the assignment layer, not a strategy difference.

## Withholding supply is dominated too — and by timing, not just quantity

The herd result says producing less is dominated. The natural follow-up is to produce everything
and *time the sale* instead: hold stock whose price has fallen below its base, and let the town's
drain lift it before selling. That is not restraint in the usual sense — output is unchanged — and
the interpreter prices each unit at the inventory standing before it, so waiting genuinely recovers
price rather than deferring a loss.

Implemented as `price_floor` in `sell_quantity`, with two overrides for failure modes we have
already measured: always liquidate over the final days, since unsold stock scores nothing, and
always sell when the shed nears its cap, since the end-of-day refresh discards the overflow.

On a mirror screen it looks like the best idea of the project. Seed 2 — the seed where one milk
shop opens late and milk collapses to $42 — goes from 45,593 to **69,352**, with milk realising
$235 instead of $95.5. Across three seeds the mean rises 74,536 → 81,662.

Head-to-head:

| | mirror mean | paired margin | h2h |
|---|---:|---:|---:|
| `price_floor = 1.0` | +2,509 | −153 | 11/24 |
| `price_floor = 1.2` | **+7,126** | **−8,571** | **0/24** |

The same trap, from a completely different direction. Holding stock while the opponent sells hands
them the pool, and what we held is worth less when we finally sell it.

**The general statement is stronger than the herd result on its own: any form of supply restraint
loses to an opponent who does not restrain — whether you restrain by producing less or by selling
later.** Two independent mechanisms, same conclusion, both invisible to mirror self-play.

Worth recording that this doc's own warning did not stop me running the mirror screen first and
being encouraged by it. It did stop me adopting on it.

## Why the unlock signal is probably not worth reading after all

`obs["town"]["unlocked_shops"]` is still unread, and it is tempting to adapt the herd to it. The
dominance argument says not to bother. Whatever the drain rate, more cows earn more than fewer
cows — a slow drain makes the pie smaller, not someone else's. Conditioning the *quantity* on the
signal is still restraint, just restraint with better timing, and restraint is dominated.

The arithmetic agrees. On a flooded seed a cow earns 1.24 units/day at $95 = $118/day; a goose
earns 2 eggs/day at $55 = $110/day. Swapping is a wash even in the case the signal is supposed to
catch, and it costs the higher price the remaining cows would have got.

Recorded as reasoned-against rather than untested. If the signal is worth anything it is on the
*crop* side, where we choose freely and pools differ more — strawberry is drained by four of the
eight shops and we have never grown it.

## Where this leaves the build

The shipped agent is at a genuine local optimum on herd composition, and now for a stated reason
rather than as an observation: **we cannot expand, because labour binds, and we should not
restrain, because it is dominated.**

The gap to the top of the field is not strategy. They service 15 animals and 11 melon tiles on
about 34 worked tiles; we need 62 tiles for 14 animals and 8 melon. That is the assignment layer —
how many useful actions a worker gets per turn — and it is where any remaining gain has to come
from.
