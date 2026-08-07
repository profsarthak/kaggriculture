# What the ladder can actually measure

## The probe's answer

The probe was built to lose: **−33,579 offline, 0/12 against every panel member.** It finished
**45 rating points** behind the build it ran against.

That is the finding it was designed to produce, and it is not the reassuring one.

## First, a correction to my own noise model

Throughout this project I used `16·√n` as the "standard error" on a rating and quoted it
repeatedly — ±62 at 15 episodes, ±110 on a difference, and so on. **That formula is wrong.**
`16·√n` describes how far a rating *drifts* under a fixed-K random walk. It grows without bound,
whereas the standard error of an estimate must *shrink* as evidence accumulates. Used as a noise
floor it gets the direction of the argument backwards, and it produced a nonsense table in which
larger effects needed *fewer* episodes to detect.

The replacement is empirical, from our own logged history. `data/ladder-log.jsonl` records each
submission's rating at every check, so the wander of a submission whose **code has not changed**
is a direct measurement of the noise:

| submission | readings | rating range | biggest single move |
|---|---:|---|---:|
| v5 | 7 | 588–690 | 84 |
| v6 | 6 | 653–700 | 32 |
| v7 | 3 | 580–607 | 26 |
| probe | 4 | 583–631 | 20 |
| v6-rebuild | 4 | 628–675 | 33 |

**Same code, no change: ratings move an average of 23 points between checks and as much as 107.**

## Against that bar, almost nothing we have measured is real

| comparison | offline margin | rating gap | clears 107? |
|---|---:|---:|:--|
| v5 vs v4 (cows) | +11,673 | −1.2 | no |
| **v6 vs v5 (routing, hiring)** | +16,000 | **+96.9** | **no** |
| v7 vs v6 (tuner pass 2) | +7,170 | −114.0 | marginally |
| probe vs v6-rebuild | −33,579 | −45.0 | no |

The one that clears is v7 — the comparison whose two candidate explanations were both refuted by
direct measurement, and which I concluded was noise anyway.

**This retracts a claim I made repeatedly.** I cited v6 vs v5's +96.9 as proof that offline gains
transfer to the ladder, and treated it as validating the whole measurement approach. It never
cleared the noise. It was suggestive and I reported it as settled.

## What the probe actually tells us

The largest offline difference we can construct — an agent that loses every single game to every
panel member by an average of 33,579 coins — moves the ladder **less than one submission's own
week-to-week wander.**

Every adoption in this project is far smaller than that gap.

The straightforward reading: **against a field of genuinely different opponents, the differences
between our own builds are small compared with the variation the opponents introduce.** All our
builds are the same architecture with different dials. From the ladder's point of view they are
nearly the same agent.

## Consequences

1. **Stop using ladder comparisons as verdicts.** At the episode counts a submission accrues in
   its lifetime, the ladder cannot distinguish our builds. It can tell us we are roughly
   competitive with the field; it cannot tell us which of two configurations is better.
2. **Offline measurement is the only instrument with the resolution** — but it is uncalibrated
   against the thing that pays, and the probe shows its scale is wildly compressed on the ladder.
3. **Further tuning has low expected value.** We are at a local optimum where an automated search
   finds nothing, and the ladder cannot see differences ten times larger than anything tuning
   would produce. What would move the needle is a qualitatively stronger agent, not better dials.
4. **The submission cadence policy in `docs/06-iteration.md` needs revising.** It was built on
   the wrong noise model and is too optimistic about what a comparison can resolve.

## The honest summary

We built a careful measurement apparatus, used it to make many small improvements, and can now
demonstrate that the ladder cannot confirm most of them. That is not an argument the work was
wasted — the agent went from 6,704 to ~75,000 offline, and we are at 96% of the field average
against 87% earlier. But it does mean **the confidence attached to individual adoptions was too
high**, and several conclusions in earlier documents were reported with more certainty than the
evidence supported.
