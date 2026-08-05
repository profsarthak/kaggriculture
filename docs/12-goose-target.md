# Does the ladder data say anything about `goose_target`?

## The question

`goose_target` is inert in self-play: raising it from 16 to 20 or 24 changes the outcome by
**exactly +0**, because the flock is capped by the layout's labour budget rather than by the
target. That establishes the knob does nothing *in our agent* — but not whether a bigger flock
would be worth having if we could afford one.

## What the field says: animals matter, a lot

`analysis/correlate.py` treats every opponent appearance as an independent choice of build.
31 player-appearances, day-12 build against final score:

| build variable | correlation with score | range | field mean |
|---|---:|---:|---:|
| **animals** | **+0.61** | 0–13 | 2.5 |
| structures | +0.62 | 0–16 | 3.9 |
| quadrants | +0.20 | 1–4 | 2.0 |
| melon tiles | −0.04 | 0–35 | 9.6 |
| **wheat tiles** | **−0.43** | 0–23 | 3.8 |

Banded, the animal relationship is monotonic and large:

| animals at day 12 | n | mean score |
|---:|---:|---:|
| 0 | 14 | 31,492 |
| 1–2 | 6 | 33,976 |
| 3–5 | 6 | 51,346 |
| 6–9 | 3 | 57,834 |
| **10+** | 2 | **73,199** |

Melon is a clean inverted-U, which independently corroborates A4 and our tuning:

| melon tiles | n | mean score |
|---:|---:|---:|
| 0 | 6 | 20,915 |
| 1–5 | 6 | 52,798 |
| **6–11** | 6 | **57,080** |
| 12–19 | 9 | 34,782 |
| 20+ | 4 | 43,732 |

Both zero melon and heavy melon are worse than a moderate commitment. Our 9 sits in the best
band, arrived at independently by paired A/B.

## But the implied change does not work

The obvious reading — buy more animals by spending less on wheat — was tested directly:

| variant | paired margin |
|---|---:|
| `feed_ratio=1.5` (from 2.0) | −16,120 |
| `feed_ratio=1.3` | −17,308 |
| `max_extra_wheat=2` | −7,699 |
| `max_extra_wheat=6` | **+0** |
| `feed_ratio=1.5, max_extra_wheat=6` | −16,120 |

Two things follow. **Wheat is not over-allocated**: capping surplus wheat at 6 tiles changes
nothing, so we already carry no more than that. And **the feed margin is load-bearing**: 1.25
wheat tiles per animal is break-even, and dropping from 2.0 toward it starves the flock rather
than growing it.

## Conclusion

The flock is correctly sized for the labour we have. `goose_target` is genuinely inert and
should stay where it is — the path to more animals is **more throughput, not reallocation**.
Every reallocation route has now been closed by measurement:

- more hands → worse (`hands_target=9` −16,056)
- more land per worker (`labour_headroom` 0.5) → worse (−16,338)
- less wheat per animal → worse (−16,120)
- buying feed instead of growing it → worse (−24,800, `docs/08-field-study.md`)

This is the third time a field-derived parameter has failed to transfer, and the pattern is now
consistent enough to state as a finding in its own right: **the field's builds are not
portable because they encode a different execution efficiency.** Opponents running 10+ animals
can service them; we cannot, and reallocating toward a flock we cannot tend makes things worse,
not better.

The correlation is also observational — strong players differ in many ways at once, so +0.61
is not evidence that animals *cause* the scores. What it does establish is that the ceiling is
much higher than where we sit, and that the binding constraint is worker throughput.

## What would actually move it

Throughput, again. Travel is still ~51% of worker turns after the routing rework. Halving it
again would fund roughly twice the flock without touching a single allocation knob — and unlike
every reallocation above, it does not trade one need against another.
