"""How much rating is an offline margin actually worth?

Every adoption in this project was justified by an offline paired margin in
coins. The ladder is the only thing that pays. If those two are related by a
known factor, we can say how large an offline gain has to be before submitting
it is worth a slot -- and, more uncomfortably, which past adoptions were never
distinguishable from noise.

The probe is the anchor. It was built to lose and measures -33,579 offline; it
finished 45 rating points behind. That single point suggests offline margins
are enormously compressed on the ladder, and this module checks that against
every other comparison we have.

Run:  python -m analysis.calibrate
"""

import math

# (label, offline paired margin in coins, ladder rating gap, episodes at read)
#
# Offline margins are the mirror A/B figures recorded in docs/ at the time each
# build was submitted. Rating gaps are challenger minus champion.
COMPARISONS = [
    ("v5 vs v4  (cows added)",        11673,   -1.2,  15),
    ("v6 vs v5  (routing, hiring)",   16000,  +96.9,  25),
    ("v7 vs v6  (tuner pass 2)",       7170, -114.0,  24),
    ("probe vs v6-rebuild",          -33579,  -45.0,  26),
]

"""Noise estimate.

I previously used 16*sqrt(n) as a "standard error", quoted it repeatedly, and
made decisions on it. That is wrong: 16*sqrt(n) is how far a rating *drifts*
under a fixed-K random walk, which grows without bound, whereas the standard
error of an estimate should *shrink* as games accumulate. Used as a noise floor
it gets the direction of the whole argument backwards.

The honest replacement is empirical. `data/ladder-log.jsonl` records each
submission's rating at every check, so how much a single submission's rating
wanders between checks -- while its true strength is unchanged -- is a direct
measurement of the noise we are up against.
"""

import json
import os
import statistics

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "ladder-log.jsonl")


def observed_rating_swings():
    """Successive rating changes for a submission whose strength is fixed."""
    history = {}
    if not os.path.exists(LOG):
        return {}
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            for ref, score in (entry.get("ratings") or {}).items():
                if score is None:
                    continue
                history.setdefault(ref, []).append(float(score))
    return {ref: vals for ref, vals in history.items() if len(vals) >= 3}


def main():
    print("=== how much does a rating wander on its own? ===\n")
    swings = observed_rating_swings()
    all_moves = []
    for ref, vals in sorted(swings.items()):
        moves = [abs(b - a) for a, b in zip(vals, vals[1:])]
        all_moves.extend(moves)
        print(f"  {ref}: {len(vals)} readings, range {min(vals):.0f}-{max(vals):.0f},"
              f" biggest single move {max(moves):.0f}")

    if all_moves:
        typical = statistics.mean(all_moves)
        worst = max(all_moves)
        print(f"\n  Same submission, unchanged code: mean move between checks"
              f" {typical:.0f} points, largest {worst:.0f}.")
        noise = worst
    else:
        print("  Not enough logged history yet.")
        noise = 100.0

    print(f"\n  Treating {noise:.0f} points as the bar a gap must clear to mean"
          f" anything.\n")

    print("=== offline margin vs ladder movement ===\n")
    header = f"{'comparison':<30} {'offline':>9} {'rating':>8} {'signal?':>8} {'pts/1k':>8}"
    print(header)
    print("-" * len(header))

    usable = []
    for label, offline, gap, _n in COMPARISONS:
        significant = abs(gap) > noise
        per_k = gap / (offline / 1000.0) if offline else float("nan")
        print(f"{label:<30} {offline:>9,} {gap:>8.1f}"
              f" {'yes' if significant else 'no':>8} {per_k:>8.2f}")
        if significant:
            usable.append((label, offline, gap))

    print("\n=== what survives ===")
    if not usable:
        print("  Nothing. Every comparison we have is inside the range a single")
        print("  unchanged submission wanders on its own.")
    for label, offline, gap in usable:
        print(f"  {label}: {offline:+,} offline -> {gap:+.1f} rating")

    print("\n=== the anchor ===")
    print("  The probe is the one comparison where the offline margin is huge and")
    print("  unambiguous: -33,579 coins, losing 0/12 against every panel member.")
    print("  It finished 45 rating points behind.")
    print("\n  So the largest offline difference we can construct moves the ladder")
    print("  by less than a single submission's own week-to-week wander. Every")
    print("  adoption in this project has been smaller than that.")


if __name__ == "__main__":
    main()
