"""Paired, seat-swapped A/B testing with honest statistics.

Every comparison so far ran the variant as player 0 against the baseline as
player 1 over a handful of seeds, and read off the mean. Two problems with that:

  1. **Seat bias.** Market orders settle in player order for HIRE and BUY_LAND,
     and hired hands spawn by a fixed NWSE preference. If seat 0 is worth
     anything, a fixed-seat comparison measures the seat, not the change. Self
     play showed 1/6 wins for player 0 with near-identical means, which is
     exactly what a seat effect looks like.
  2. **Unpaired noise.** Seed-to-seed variance is large. Comparing two means
     throws away the fact that both agents played the *same* seed, which is the
     single biggest variance reduction available.

This runs each seed twice with the seats swapped, pairs the results, and
reports how large an effect the sample can actually resolve.

Run:  python ab.py --variant melon_tiles=12 --n 8
      python ab.py --null --n 12          # identical configs: measures the noise floor
"""

import argparse
import math
import statistics

from kaggle_environments import make

from farmlib import Config, make_agent


def parse_kwargs(spec):
    kwargs = {}
    if not spec:
        return kwargs
    for pair in spec.split(","):
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if value.lower() in ("true", "false"):
            kwargs[key] = value.lower() == "true"
        elif "." in value:
            kwargs[key] = float(value)
        else:
            try:
                kwargs[key] = int(value)
            except ValueError:
                kwargs[key] = value
    return kwargs


def play(cfg_a, cfg_b, seed):
    """Return (a_score, b_score) with A in seat 0."""
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([make_agent(cfg_a), make_agent(cfg_b)])
    final = env.steps[-1]
    return final[0].reward or 0, final[1].reward or 0


def compare(cfg_a, cfg_b, n, verbose=False):
    """Each seed played both ways. Returns per-seed paired margins for A."""
    margins, seat_effects, wins, games = [], [], 0, 0
    for seed in range(n):
        a0, b1 = play(cfg_a, cfg_b, seed)      # A in seat 0
        b0, a1 = play(cfg_b, cfg_a, seed)      # A in seat 1

        # Averaging A's margin over both orientations cancels any seat effect.
        margin = ((a0 - b1) + (a1 - b0)) / 2
        margins.append(margin)
        # And the seat effect itself is the part that does NOT cancel.
        seat_effects.append(((a0 - b1) - (a1 - b0)) / 2)

        # Count decisive games only. The agent is deterministic, so a change
        # that does not fire produces an exact tie -- counting those in the
        # denominator makes a 50/50 change look like a heavy loss.
        for ours, theirs in ((a0, b1), (a1, b0)):
            if ours > theirs:
                wins += 1
                games += 1
            elif theirs > ours:
                games += 1
        if verbose:
            print(f"  seed {seed:>3}: A@0 {a0:>8,.0f}-{b1:<8,.0f}   "
                  f"A@1 {a1:>8,.0f}-{b0:<8,.0f}   margin {margin:>+9,.0f}")
    return margins, seat_effects, wins, games


def wilson(wins, n, z=1.96):
    """Wilson interval -- honest at the small n these comparisons run at."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def report_winrate(wins, games, label):
    """Score on win rate rather than mean margin.

    The ladder pays for wins, not coins, so a change that converts heavy losses
    into narrow ones -- or narrow wins into heavy ones -- is worth nothing and
    everything respectively, and the margin statistic cannot tell them apart.
    Anything deliberately trading expected coins for win probability (see
    `risk_*` in farmlib) has to be judged here instead.
    """
    p, lo, hi = wilson(wins, games)
    print(f"\n=== {label} (win rate) ===")
    print(f"  wins        {wins}/{games} = {p:.1%}")
    print(f"  95% CI      [{lo:.1%}, {hi:.1%}]")
    verdict = "INCONCLUSIVE"
    if lo > 0.5:
        verdict = "VARIANT BETTER"
    elif hi < 0.5:
        verdict = "VARIANT WORSE"
    print(f"  verdict: {verdict}")
    if verdict == "INCONCLUSIVE":
        need = math.ceil((1.96 / (abs(p - 0.5) or 0.01)) ** 2 * 0.25)
        print(f"  (an edge this size needs ~{need} games to resolve)")
    return p


def report(margins, seat_effects, wins, games, label):
    n = len(margins)
    mean = statistics.mean(margins)
    sd = statistics.stdev(margins) if n > 1 else 0.0
    stderr = sd / math.sqrt(n) if n else 0.0
    # 95% CI using a normal approximation; with n < 30 this is optimistic, which
    # is stated rather than hidden.
    lo, hi = mean - 1.96 * stderr, mean + 1.96 * stderr

    print(f"\n=== {label} ===")
    print(f"  paired margin   {mean:>+10,.0f}   95% CI [{lo:>+,.0f}, {hi:>+,.0f}]")
    print(f"  per-seed stdev  {sd:>10,.0f}   over {n} seeds ({games} games)")
    print(f"  head-to-head    {wins}/{games} = {wins / games:.0%}")

    seat = statistics.mean(seat_effects)
    seat_sd = statistics.stdev(seat_effects) if n > 1 else 0.0
    seat_err = seat_sd / math.sqrt(n) if n else 0.0
    flag = "SIGNIFICANT" if abs(seat) > 1.96 * seat_err else "not significant"
    print(f"  seat 0 advantage {seat:>+9,.0f}   ({flag}) -- cancelled by swapping")

    verdict = "INCONCLUSIVE"
    if lo > 0:
        verdict = "VARIANT BETTER"
    elif hi < 0:
        verdict = "VARIANT WORSE"
    print(f"  verdict: {verdict}")

    if sd > 0:
        print("\n  seeds needed to resolve an effect of:")
        for effect in (500, 1000, 2000, 4000):
            need = math.ceil((1.96 * sd / effect) ** 2)
            print(f"    {effect:>6,} coins  ->  {need:>4} seeds ({need * 2} games)")
    return mean, sd


# A panel of sparring partners, not just ourselves.
#
# Self-play rewards changes that beat *us*, which is measurably not the same as
# beating the field: the cows build won its self-play A/B by +11,673 and then
# finished 18 rating points BELOW the build it replaced. A change that only
# helps against a mirror of itself is not worth shipping, so a variant is now
# scored against several genuinely different strategies and judged on the worst
# case as well as the average.
#
# The field-like entries are built from what replays actually show opponents
# doing (docs/12-goose-target.md): ~10 melon tiles, few animals, 2 quadrants.
PANEL = {
    "mirror": {},
    # An opponent that is *equally strong* and takes more melon. Without this
    # the panel cannot price conceding a contested pool: every other member is
    # weak elsewhere, so our margin against them is dominated by that weakness
    # rather than by the melon contest, and the mirror concedes in lockstep with
    # us. That blind spot is what let v7 cut melon 7 -> 5, measure +7,170, and
    # lose 114 rating (docs/18-v7-regression.md).
    "melon-contest": {"melon_tiles": 12},
    "no-cows": {"pasture_target": 0},
    "field-like": {"melon_tiles": 11, "pasture_target": 0, "goose_target": 6,
                   "land_purchases": 1, "hands_target": 6},
    "melon-rush": {"melon_tiles": 20, "pasture_target": 0, "goose_target": 4},
    "goose-engine": {"melon_tiles": 0, "goose_target": 24, "pasture_target": 3},
}


def run_panel(cfg_a, baseline_kwargs, n, verbose=False):
    """Score the variant against every panel member. Returns per-opponent means."""
    results = {}
    for name, extra in PANEL.items():
        cfg_b = Config(**{**baseline_kwargs, **extra})
        margins, seats, wins, games = compare(cfg_a, cfg_b, n, verbose)
        mean = statistics.mean(margins)
        sd = statistics.stdev(margins) if len(margins) > 1 else 0.0
        stderr = sd / math.sqrt(len(margins)) if margins else 0.0
        results[name] = (mean, mean - 1.96 * stderr, mean + 1.96 * stderr, wins, games)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="", help="e.g. melon_tiles=12,hands_target=9")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--null", action="store_true",
                    help="compare defaults against defaults to measure the noise floor")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--panel", action="store_true",
                    help="score against several strategies, not just a mirror")
    args = ap.parse_args()

    if args.panel:
        base_kwargs = parse_kwargs(args.baseline)
        cfg_a = Config(**{**base_kwargs, **parse_kwargs(args.variant)})
        print(f"variant: {args.variant or '(defaults)'}   {args.n} seeds vs each opponent\n")
        header = f"{'opponent':<14} {'margin':>10} {'95% CI':>22} {'wins':>8}"
        print(header)
        print("-" * len(header))
        results = run_panel(cfg_a, base_kwargs, args.n)
        for name, (mean, lo, hi, wins, games) in results.items():
            ci = f"[{lo:>+8,.0f}, {hi:>+8,.0f}]"
            print(f"{name:<14} {mean:>+10,.0f} {ci:>22} {wins:>4}/{games}")
        worst = min(results.values(), key=lambda r: r[0])[0]
        avg = statistics.mean(r[0] for r in results.values())
        print(f"\n  average {avg:>+10,.0f}    worst case {worst:>+10,.0f}")
        if worst < 0:
            print("  Loses to at least one strategy -- not a safe adopt.")
        else:
            print("  Beats every panel member.")
        return

    cfg_b = Config(**parse_kwargs(args.baseline))
    cfg_a = Config(**parse_kwargs(args.baseline)) if args.null else Config(
        **{**parse_kwargs(args.baseline), **parse_kwargs(args.variant)}
    )

    label = "NULL (identical configs)" if args.null else f"variant: {args.variant}"
    print(f"{label}, {args.n} seeds, each played both ways")

    margins, seats, wins, games = compare(cfg_a, cfg_b, args.n, args.verbose)
    report(margins, seats, wins, games, label)
    report_winrate(wins, games, label)

    if args.null:
        print("\n  Any non-zero margin here is pure noise. Use the stdev above as the")
        print("  floor: a real change must clear it by more than the CI to be believed.")


if __name__ == "__main__":
    main()
