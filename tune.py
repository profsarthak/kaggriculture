"""Coordinate descent over the config, using paired A/B as the objective.

The parameters are coupled: changing `labour_headroom` moves the optimum for
`melon_tiles`, which moves the optimum for `pasture_target`, and so on. Sweeping
each once in isolation leaves value on the table, and re-sweeping by hand after
every change is what most of this session has been.

This walks the neighbourhood repeatedly until no single-parameter change helps,
adopting only changes whose confidence interval clears zero.

Run:  python tune.py --n 4 --rounds 3
"""

import argparse
import math
import statistics

from ab import compare
from farmlib import Config

# Candidate values per parameter. Deliberately small steps -- the surface is
# jagged enough that large jumps land somewhere unrelated.
# Ranges must extend past the current value in both directions, or the search
# silently reports a "local optimum" that is really the edge of the grid -- the
# first run capped `pasture_target` at 4 and missed +3,326 at 5.
GRID = {
    "melon_tiles": [4, 5, 6, 7, 8, 9, 10, 12],
    "labour_headroom": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65],
    "pasture_target": [3, 4, 5, 6, 7, 9],
    "hands_target": [7, 8, 9, 10, 11],
    "feed_carry": [3, 4, 5, 6],
    "travel_weight": [5.0, 6.5, 8.0, 10.0, 13.0],
    "goose_target": [10, 14, 16, 20, 26],
    "tiles_per_hand": [4, 5, 6, 7, 8],
    "min_hands": [4, 5, 6, 7, 8],
    "land_purchases": [1, 2, 3],
    "feed_ratio": [1.6, 2.0, 2.5],
    "cash_floor": [100, 200, 400],
}


def evaluate(current, param, value, n):
    """Paired margin of `current + {param: value}` against `current`."""
    cfg_b = Config(**current)
    cfg_a = Config(**{**current, param: value})
    margins, _seats, _wins, _games = compare(cfg_a, cfg_b, n)
    mean = statistics.mean(margins)
    sd = statistics.stdev(margins) if len(margins) > 1 else 0.0
    stderr = sd / math.sqrt(len(margins)) if margins else 0.0
    return mean, mean - 1.96 * stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    base = Config()
    current = {k: getattr(base, k) for k in GRID}
    print("starting point:")
    for k, v in current.items():
        print(f"  {k:<18} {v}")

    total = 0.0
    for rnd in range(1, args.rounds + 1):
        print(f"\n=== round {rnd} ===")
        improved = False
        for param, values in GRID.items():
            best = None
            for value in values:
                if value == current[param]:
                    continue
                mean, lo = evaluate(current, param, value, args.n)
                # Adopt only if the interval clears zero -- otherwise we are
                # chasing noise, and with a jagged surface that compounds.
                if lo > 0 and (best is None or mean > best[1]):
                    best = (value, mean, lo)
            if best:
                value, mean, lo = best
                print(f"  {param:<18} {current[param]} -> {value:<6} "
                      f"{mean:>+9,.0f}  (CI low {lo:>+8,.0f})")
                current[param] = value
                total += mean
                improved = True
        if not improved:
            print("  no single-parameter change clears zero -- local optimum")
            break

    print("\n=== final config ===")
    for k, v in current.items():
        print(f"  {k:<18} {v}")
    print(f"\n  cumulative measured gain: {total:>+,.0f}")
    print("\n  Apply by editing farmlib.Config, then re-verify with:")
    print("    python ab.py --variant <changes> --panel --n 3")


if __name__ == "__main__":
    main()
