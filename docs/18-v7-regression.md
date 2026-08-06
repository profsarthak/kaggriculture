# v7 lost on the ladder, and why that is the most important result so far

## What happened

| submission | offline vs its predecessor | ladder rating |
|---|---:|---:|
| v6 | +30% self-play over v5 | **694.4** |
| v7 | +7,170 (~10%) over v6 | **580.4** (24 episodes) |

v7 measured better offline by every instrument we have — mirror A/B (+7,170), and a panel worst
case of +8,314 across five strategies — and finished **114 rating points behind** the build it
was meant to improve on.

At 24 episodes the standard error on a rating is roughly `16·√n` ≈ 78, and on the *difference*
of two ratings about 110, so 114 is around one standard error: suggestive rather than proven.
But it is six times the −18.3 gap correctly dismissed as noise for v5, and it is the wrong sign.

## The likely cause: self-play cannot see a conceded pool

v7's headline change was cutting melon from 7 tiles to 5, freeing budget for cows.

In a **mirror match, both sides cut equally.** The shared melon pool is then split the same way
it was before, so giving up melon looks free — the tiles go to cows and the score rises. The
comparison never charges us for the melon we stopped taking, because our opponent stopped taking
it too.

Against a **real field that plants ~10 melon tiles**, cutting ours does not shrink the pool. It
hands the difference to them. A4 measured conceding melon entirely at **−$20,702**.

The panel does not catch this either: every member runs our engine, and most were configured
with little or no melon, so they concede alongside us.

**This is a structural blind spot, not bad luck.** Any change that trades a contested resource
for an uncontested one will look better in self-play than it is, because the mirror concedes in
lockstep. Melon and fertiliser are exactly such resources.

## What it implies about the whole method

Three ladder comparisons now exist:

| comparison | offline gain | ladder result |
|---|---|---|
| v6 vs v5 | ~30% | **+96.9 — transferred** |
| v5 vs v4 | +11,673 (~30%) | −1.2 — inconclusive |
| v7 vs v6 | +7,170 (~10%) | **−114 — reversed** |

Large structural gains transferred. A moderate tuning gain did not, and may have been negative.
That is consistent with the blind spot above: the big wins (routing, hire-to-demand, adding cows
at all) were about *doing more with the same farm*, which a mirror measures honestly. The v7
changes were about *reallocating between products*, which a mirror measures dishonestly whenever
one of those products is contested.

**Working rule going forward: trust self-play for throughput, distrust it for allocation.**

## Action taken

- Resubmitted v6 from its tag, rebuilt byte-identically (preflight 93,026 / 68,488, matching the
  original exactly). It and the diagnostic probe are the tracked pair; v7 has dropped out.
- v7 is preserved as `submitted/v7` and remains reproducible.

## What should be tested next

The panel needs an opponent that **actually contests melon**. Every current member concedes it,
which is precisely the configuration that cannot detect this failure. Adding a melon-heavy
sparring partner and re-running the melon sweep against it is the direct test of the hypothesis
above — and if it holds, the melon reductions from 9 → 7 → 5 need revisiting, since each was
adopted on evidence that could not see their true cost.
