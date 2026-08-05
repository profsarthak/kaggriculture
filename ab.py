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

        wins += (1 if a0 > b1 else 0) + (1 if a1 > b0 else 0)
        games += 2
        if verbose:
            print(f"  seed {seed:>3}: A@0 {a0:>8,.0f}-{b1:<8,.0f}   "
                  f"A@1 {a1:>8,.0f}-{b0:<8,.0f}   margin {margin:>+9,.0f}")
    return margins, seat_effects, wins, games


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="", help="e.g. melon_tiles=12,hands_target=9")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--null", action="store_true",
                    help="compare defaults against defaults to measure the noise floor")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cfg_b = Config(**parse_kwargs(args.baseline))
    cfg_a = Config(**parse_kwargs(args.baseline)) if args.null else Config(
        **{**parse_kwargs(args.baseline), **parse_kwargs(args.variant)}
    )

    label = "NULL (identical configs)" if args.null else f"variant: {args.variant}"
    print(f"{label}, {args.n} seeds, each played both ways")

    margins, seats, wins, games = compare(cfg_a, cfg_b, args.n, args.verbose)
    report(margins, seats, wins, games, label)

    if args.null:
        print("\n  Any non-zero margin here is pure noise. Use the stdev above as the")
        print("  floor: a real change must clear it by more than the CI to be believed.")


if __name__ == "__main__":
    main()
