# What actually beats us, measured on 237 real games

Written after the mechanic audit and the layout fix both concluded that our remaining gap is not
mechanical. This asks the field instead of the interpreter.

## Where we stand

| | |
|---|---:|
| our rank | **1,389 of 2,748** |
| our rating | 695.8 |
| field median rating | 701 |
| 10th place (the prize band) | **3,057.2** |
| teams above 2,000 | 499 |
| teams above 3,000 | 27 |

We are, to two significant figures, exactly the median team. The 50% win rate was never a sign of
being underrated — matchmaking pairs us with our own class and we go even against it.

## Our losses are not close

Across 237 scored games against real opponents:

| | |
|---|---:|
| median losing margin | **−20,060** |
| median winning margin | +20,996 |
| games lost by under 2,000 | 6 (2.5%) |
| games lost by under 10,000 | 31 (13%) |

This killed a test before it was run. `risk_from_day` implements the one genuinely
game-theoretic idea in the original plan — take variance when behind, since the payoff is
`sign(M_i − M_j)` and not the margin. It has never fired because its trigger needs us to be
behind by 8,000 after day 20, which never happens in mirror play. But a variance strategy converts
close losses, and ours are not close. Not worth the compute at this margin distribution.

## The ceiling, and who is above it

| | us | opponents |
|---|---:|---:|
| min | 16,113 | 248 |
| median | **66,925** | 60,413 |
| p75 | 76,522 | 84,205 |
| max | **100,864** | **193,918** |

The field's 90th percentile is 100,824. Our best game ever is 100,864. **Our ceiling is their
routine.** In 23 of 237 games the opponent outscored our all-time best. Seven opponents have
scored above 120,000 and five above 150,000.

Reaching the prize band is not a matter of finding a few thousand coins. It needs roughly double
our output.

## What the strong builds look like

Day-12 snapshot, averaged. The top-10 group is **9 distinct players**, the top-25 group **24** —
this is a shared pattern, not one agent repeated.

| | top 10 (avg 153,800) | top 25 (avg 124,163) | middle 50% (61,571) | **us (62,801)** |
|---|---:|---:|---:|---:|
| wheat tiles | 5.5 | 5.4 | 3.6 | **36.4** |
| animals | 13.9 | 11.0 | 6.7 | 6.4 |
| — cows | 8.1 | 6.6 | 4.1 | 3.9 |
| — sheep | **5.8** | 4.3 | 2.1 | **0** |
| — geese | **0.0** | 0.1 | 0.5 | 2.5 |
| structures | 14.1 | 12.5 | 8.7 | 9.5 |
| melon tiles | 10.6 | 9.2 | 7.9 | 10.7 |
| quadrants | 3.1 | 2.8 | 2.3 | 2.9 |

Melon and land we already match. Three things separate us:

1. **They carry twice the herd by day 12** — 13.9 against our 6.4.
2. **They run sheep and no geese.** We run the reverse. Our agent cannot express a cow/sheep mix
   at all: `pasture_animal` is a single value for every pasture.
3. **They grow 5.5 wheat tiles. We grow 36.4.**

## The wheat difference is not what it looks like

Four A/Bs, each 16 games, and every one lost. The instrumented runs say why, and the reason is
different in each case.

| variant | margin | h2h | animal-days | fed | starved |
|---|---:|---:|---:|---:|---:|
| current | — | — | 534 | 97% | 0 |
| `max_extra_wheat=0` | −544 (inconclusive) | 6/16 | — | — | — |
| `feed_ratio=1.25, max_extra_wheat=0` | −26,326 | 0/16 | 468 | 79% | **24** |
| `buy_feed=true, max_extra_wheat=0` | −32,625 | 0/16 | **328** | 100% | 0 |

- **Surplus wheat is free to drop.** Only ~4 of the 36 tiles are surplus; removing them costs
  nothing measurable. The other 32 are feed reserve at `feed_ratio = 2.0`.
- **Cutting the feed reserve to its theoretical break-even starves the herd.** 1.25 tiles per
  animal is the steady-state ratio, but wheat arrives in batches every ~5 days while animals eat
  daily. At 1.25 the buffer is gone: 24 animals starve and only 84% of production days end fed.
  The mechanic audit already established that a missed production day costs the whole care bonus,
  roughly halving that animal's output, so the 2.0 margin is insurance and it is earning its keep.
- **Buying feed works perfectly and still loses.** 100% fed, nothing starves — the implementation
  is fine. It fails because **animal-days fall from 534 to 328**. Money spent on wheat is money
  not spent on animals.

That last line is the real finding. **Our herd is limited by capital, not labour.** A3 concluded
the farm is labour-bound and every allocation decision since has been made on that basis. It is
true of the *tiles*; it is not true of the *herd*.

So the 36 wheat tiles are not the disease. They are how we convert surplus labour into feed
without spending the capital that buys animals. The strong builds get to 14 animals by day 12
some other way, and finding out how is the open question — not copying their wheat count.

## Open

- **How do they finance 14 animals by day 12?** Roughly 5,600 in livestock plus land, from a 3,000
  start, before melon yields on day 10. Sheep reach first yield on day 6 against a cow's day 8,
  which is a partial answer and worth pursuing.
- **Cow/sheep mix.** Requires code: `animal_for` returns one animal per structure kind. This is
  the largest untested difference between us and the field.
- **`risk_from_day`** stays switched off and untested. Revisit only if the margin distribution
  tightens.
