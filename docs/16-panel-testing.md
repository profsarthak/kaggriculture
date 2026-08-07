# Testing against a panel, and how much ladder noise there is

## Why

The cows build won its self-play A/B by **+11,673** and then sat at 588.1 against the 606.4 of
the build it replaced. That looked like offline measurement failing to predict the ladder, which
would undermine every decision made this way.

`ab.py --panel` scores a variant against several genuinely different strategies rather than only
a mirror of itself. Panel members are built from what replays show opponents actually doing
(~10 melon tiles, few animals, 2 quadrants) plus deliberate extremes:

| member | build |
|---|---|
| mirror | the baseline itself |
| no-cows | `pasture_target=0` |
| field-like | 11 melon, no pastures, 6 geese, 1 land purchase, 6 hands |
| melon-rush | 20 melon, no pastures, 4 geese |
| goose-engine | no melon, 24 geese, 3 pastures |

It reports the worst case alongside the average, because a change that wins on average while
losing badly to one strategy is a liability on a ladder that matches you against everyone.

## Cows, re-examined

| opponent | margin | wins |
|---|---:|---:|
| mirror | +15,792 | 6/6 |
| no-cows | +15,792 | 6/6 |
| field-like | +22,056 | 6/6 |
| melon-rush | +26,176 | 6/6 |
| goose-engine | +23,395 | 6/6 |

**Average +20,642, worst case +15,792.** Cows beat every strategy we can construct, decisively.

> **Correction (see [19-calibration.md](19-calibration.md)):** the `16·√n` noise model used
> below is wrong — it describes random-walk drift, not the standard error of an estimate. The
> empirical figure from our own logged history is that an *unchanged* submission's rating wanders
> up to 107 points between checks. The conclusion here (that the gap was noise) still holds, and
> holds more strongly; the arithmetic supporting it does not.

## So the ladder gap was noise, and I misread it

The offline signal is not narrow, which was the hypothesis. The remaining explanation is sample
size. Ratings move roughly ±16 per game, so after *n* games the standard error on a rating is
about `16·√n` — **≈62 points at 15 episodes**. A gap of −18.3 is well inside one standard error.

`ladder.py` said exactly this ("too close to call, hold"), and the initial reading of "the cows
build is if anything worse" over-interpreted the number. Recorded because it is an easy mistake
to repeat: **rating differences under ~60 points at these sample sizes carry no information**,
and the tool's own threshold of 50 exists for that reason.

The practical consequence is that ladder comparisons are expensive. Resolving a genuine 50-point
difference needs a few hundred episodes, which at observed accrual is days rather than hours.
Offline panel testing resolves a 500-coin effect in ~1 minute. **The panel is the instrument for
iteration; the ladder is for occasional calibration**, not for adjudicating individual changes.

## What the panel cannot do

Every panel member runs *our* engine with a different `Config`. So the panel measures
robustness across strategies, but it cannot construct an opponent that plays **better than our
best configuration** — any such opponent would, by definition, be a config we should adopt.

That matters because the field is currently better than us: across the v4/v5 episodes we
average 38,322 against the field's 50,411. The strongest opponent seen, `PromptEngineer48`,
scored 79,254 with 29 melon tiles and 19 animals — a build our engine cannot service
(`docs/08-field-study.md`), so parameterising a panel member that way produces a weak opponent
rather than a strong one.

**The ladder is therefore the only source of information about genuinely stronger play**, and
it is slow and noisy. The practical split: panel for iteration, ladder for periodic calibration,
and no expectation that offline margins convert one-for-one into rating.

## Standing instruction

Adopt on the **panel worst case**, not the mirror margin. A change that helps against ourselves
and hurts against a melon-rush opponent is exactly the kind of thing self-play cannot see.

```bash
python ab.py --variant pasture_target=3 --panel --n 3
```
