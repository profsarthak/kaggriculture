# Sweeping the priority table

The task priority ordering was hand-set from "irreversible things first" reasoning in the very
first agent and never measured. `prio(key, cfg)` now routes every lookup through a per-config
override so each entry can be swept; passing nothing reproduces the table exactly (null test:
paired margin +0).

## Results

Against the current defaults, 4 seeds each unless noted:

| change | from → to | paired margin |
|---|---|---:|
| **`PLACE`** | 75 → **90** | **+967** (10 seeds, 20/20, CI [+939, +996]) |
| `HARVEST` | 80 → 70 | +438 |
| `BUILD` | 55 → 85 | +241 |
| `BUILD` | 55 → 95 | −2,130 |
| `PLACE` | 75 → 95 | −300 |
| `DIG` | 50 → 75 | −730 |
| `PLANT` | 60 → 72 | −667 |
| `PLANT` | 60 → 85 | −3,129 |
| `WATER_BONUS` | 70 → 80 | −896 |
| `CARE` | 72 → 85 | −3,035 |
| `HARVEST` | 80 → 90 | −7,929 |
| `FERT` | 30 → 65 | **+0 (inert)** |

**Adopted `PLACE` = 90.** A structure standing empty is a tile earning nothing *and* a bought
animal idling in the shed — two wasted investments at once — so placing it beats almost anything
else on the board.

## The small wins do not stack

| combination | margin |
|---|---:|
| `PLACE=90` alone | **+967** |
| `PLACE=90, HARVEST=70` | +78 |
| `PLACE=90, HARVEST=70, BUILD=85` | −2,241 |

Each of the three is individually positive and together they are negative. Priorities are
*relative*, so raising several at once changes the ordering differently from raising any one —
a reminder that these cannot be treated as independent knobs and that combinations need testing
in their own right rather than being assumed additive.

## `FERT` is inert, like `goose_target` and `fertilizer_quota`

Changing it from 30 to 65 does nothing at all. That is the third inert knob found: fertilizer
collection is already bounded by something else entirely (the quota, which is itself bounded by
the flock, which is bounded by the labour budget). Worth remembering before spending time on it
again.

## Reading

The table was, on the whole, right — nine of twelve tested changes are neutral or harmful, and
the one real gain is small next to the structural changes (routing +6,405, cows +11,673, hire-to-
demand +3,370). Hand-reasoning from "irreversible first" produced a near-optimal ordering.

That is a useful negative result: **priority tuning is close to exhausted** and is not where
remaining value sits.
