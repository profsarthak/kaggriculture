# A/B methodology — and why the earlier sweeps were unreliable

## The problem with how I was testing

Every comparison up to this point ran the variant as player 0 against the baseline as player 1
over 4–6 seeds and compared the means. Two flaws:

**Seat bias.** Market orders settle in player order for `HIRE` and `BUY_LAND`, and hired hands
spawn by a fixed NWSE preference. A fixed-seat comparison partly measures the seat rather than
the change. Self-play showed 1/6 wins for player 0 with near-identical means — exactly the
signature of a seat effect.

**Unpaired comparison.** Both agents play the *same* seed, and throwing that away wastes the
largest variance reduction available.

`ab.py` fixes both: every seed is played twice with the seats swapped, and A's margin is
averaged over the two orientations. That cancels the seat effect exactly and pairs the
comparison.

## How much this matters

| method | per-seed stdev of the margin | seeds to resolve 500 coins |
|---|---:|---:|
| unpaired, fixed seat | thousands | tens |
| paired, seat-swapped | **430–490** | **3** |

Three seeds (six games) now resolves a 500-coin effect. The old method could not separate
29,065 from 28,577 with five seeds — which is why several earlier "0/5, clearly worse" verdicts
should not be trusted.

## The agent is deterministic

Running the null test — identical configs against each other — produced a paired margin of
**exactly 0 with stdev 0**, and 7 of 10 seeds ended in *exact ties*.

The agent has no randomness: given a seed, it plays the same game every time. Seat-swapping an
identical pair produces a perfect mirror, so the pairing cancels to zero by construction. This
makes the null test degenerate as a noise-floor measurement — the floor has to be measured
against a genuinely different config instead.

It is useful to know for its own sake: re-running a configuration on the same seeds adds no
information. Sample size means *distinct seeds*, nothing else.

## First result: the earlier melon verdict was wrong

Under the old method, `melon_tiles=18` looked like a clear loss and 8 looked settled. Properly
paired:

| melon tiles | paired margin vs 8 | 95% CI |
|---:|---:|---|
| **9** | **+2,703** | [+2,365, +3,041] (8 seeds, 16/16) |
| 10 | −81 | [−689, +528] |
| 12 | −1,066 | [−1,741, −390] |
| 14 | +6 | [−1,057, +1,068] |
| 16 | −6,716 | [−7,795, −5,637] |
| 18 | −4,249 | [−4,872, −3,627] |
| 22 | +970 | [+481, +1,459] |

**Adopted `melon_tiles=9`** — roughly a 9% gain on a ~28,500 base.

## The response surface is jagged, and that is a design flaw

Those numbers are not noise; the CIs are tight. They are non-monotonic because **`melon_tiles`
is not an independent knob**. `plan_layout` gives melon its budget first, then fits coops into
what remains, so one extra melon tile can cost an entire coop. The parameter moves two things at
once, in integer steps.

Consequences:

1. **Do not read "9 > 8" as "more melon is better."** 16 loses by 6,716.
2. Single-parameter sweeps over this layout are sampling a discontinuous function, so a local
   sweep can easily land on a spike or a trough and generalise wrongly.
3. The real fix is to decouple the allocation — specify the coop count directly rather than
   deriving it from leftover budget — and then sweep the joint space. Not yet done, and it
   should come before any further layout tuning.

## Standing instruction

Use `ab.py` for every future comparison. `bench.py` remains useful for absolute scores and the
health report, but its head-to-head numbers are fixed-seat and unpaired, and should not be used
to accept or reject a change.

```bash
python ab.py --variant hands_target=9 --n 4
```
