# Carrot opening and livestock diversification

Both ideas came from the field study (`docs/08-field-study.md`). One failed, one was the largest
single gain in the project.

## Carrot opening — rejected

The strongest opponent opened on 17 carrot tiles, and the arithmetic looks favourable: carrot
harvests on day 3 against wheat's day 4 and pays 3 units at a $35 base against 4 at $25, so it
converts the starting bank to cash faster.

Measured, it loses monotonically:

| `carrot_until` | paired margin |
|---:|---:|
| 3 | −3,865 |
| 5 | −5,394 |
| 8 | −5,893 |
| 12 | −13,963 |

Carrot's market pool is only ~842 units against wheat's unbounded depth, and wheat doubles as
animal feed — so the longer carrot runs, the worse it gets, with the day-12 figure reflecting a
flock with nothing to eat. Kept as a switch defaulting to 0 so the result stays reproducible.

### Two bugs found on the way, both silent

**A name collision made the feature dead code.** The general-purpose crop role is *named*
`"WHEAT"`, and `planting_choice` early-returned on `role in CROP_INFO` — which `"WHEAT"`
satisfies. Carrot was never planted; the tiles simply sat empty for the configured window. The
signature was a **flat −4,175 across every value of `carrot_until`**, which is what tipped it
off: a parameter that changes nothing produces identical results, not a gradient.

**An unlisted product poisons the whole shed.** `market_orders` sold from a hardcoded list that
did not include carrot, so it accumulated to the 100-item cap — at which point *all* overflow is
discarded, not just carrot's. Forgetting one product does not cost that product's revenue, it
costs everything. The sell list is now derived rather than enumerated.

## Cows — adopted, +11,673

| variant | paired margin |
|---|---:|
| 1 pasture | +8,693 |
| **2 pastures (cow)** | **+11,673** (16/16, CI [+10,819, +12,527]) |
| 3 pastures | +9,178 |
| 4 pastures | +8,184 |
| 8 pastures | +6,875 |
| 2 pastures (sheep) | +1,037 |
| 4 pastures (sheep) | +5,477 |

Milk is worth $160 base against eggs at $50, and the field averages only 3.4 animals so it is
barely contested. But the milk pool is 76 units deep, so a third cow starts flooding it — the
peak at two is exactly the shallow-pool behaviour A1 predicted. Sheep lose badly at low counts
because wool's pool is shallower still (59 units).

This is A1's central claim confirmed from the other direction: **pool depth, not base price,
determines what a product is worth** — and the corollary is that the right move is a *small*
allocation to several shallow pools rather than a large one to any.

The refactor that made this possible generalises coops/pastures and per-worker animal
inventories. Verified behaviour-neutral: with `pasture_target=0` the paired margin against the
previous build is exactly +0.

## Result

| | before | after |
|---|---:|---:|
| self-play | 38,997 (sd 1,148) | **52,700 (sd 578)** |
| vs `starter` | 50,730 | **62,282** |
| animals ending unfed | 0.0 | 0.0 |

The variance halving matters as much as the mean: the ladder scores win/loss, so consistency is
what converts to rating.

Re-swept after adopting, every other knob holds: `labour_headroom` 0.5 −16,338 and 0.65 −11,229;
`melon_tiles` 7 −4,744 and 11 −15,465; `hands_target` 7 −8,101 and 9 −16,056.

For context, self-play now sits at 52,700 against a measured field average of 39,847 — but that
is our agent on both sides, and the field's figure comes from replays predating v4. The ladder
remains the only real test.
