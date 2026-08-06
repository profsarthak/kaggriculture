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

## UPDATE: the hypothesis above is wrong, and so was reading the gap as a signal

Tested it properly by adding a melon-contesting panel member and sweeping our melon against
opponents holding 0, 5, 9, 12 and 18 tiles:

| opponent melon | ours = 5 | ours = 7 |
|---:|---:|---:|
| 0 | **+14,530** | +8,262 |
| 5 | **0** | −7,645 |
| 9 | +15,626 | **+18,528** |
| 12 | +21,562 | **+22,948** |
| 18 | **+32,146** | +29,593 |

Seven only wins in a narrow band around 9–12. Weighted by the field's observed melon
distribution, **five comes out ahead** (~16,200 vs ~14,100). Melon concession does not explain
the loss.

The same argument applied to milk, since v7 also took cows 5 → 7. That fails too: **pasture 7
beats pasture 5 at every opponent herd size tested** (0, 3, 7, 12), including against twelve cows.

With both allocation hypotheses refuted, and the remaining v7 changes being throughput
parameters that have transferred before, the honest conclusion is that **the 114-point gap was
noise.** It was about one standard error at 24 episodes. I said exactly that when reporting it —
and then built a theory on it anyway, which is the same error documented two days earlier when
correctly dismissing v5's −18.3 gap.

**A result inside one standard error is not a phenomenon to explain, however satisfying the
explanation would be.** The reasoning about self-play blindness was sound in the abstract; it
simply was not what happened here, and there was no signal to attribute to it.

### What the investigation was nonetheless worth

- **The panel now contains an equally-strong melon-contesting opponent.** Every previous member
  either conceded melon or was weak elsewhere, so the panel really could not price pool
  concession. That gap was real even though it did not cause this particular result.
- **Melon 5 is confirmed as the field-weighted optimum**, not a self-play artefact.
- **Pasture 7 dominates pasture 5** against every herd size.
- **A4's best-response structure is now measured rather than assumed.** The optimum genuinely
  moves with the opponent's commitment — it is just much flatter than A4's matrix implied.

## What should be tested next

The panel needs an opponent that **actually contests melon**. Every current member concedes it,
which is precisely the configuration that cannot detect this failure. Adding a melon-heavy
sparring partner and re-running the melon sweep against it is the direct test of the hypothesis
above — and if it holds, the melon reductions from 9 → 7 → 5 need revisiting, since each was
adopted on evidence that could not see their true cost.
