"""What does the field's build correlate with its score?

`goose_target` is inert in self-play: raising it to 20 or 24 changes nothing,
because the flock is capped by the labour budget rather than by the target. That
tells us the knob does nothing *in our agent*, but not whether a bigger flock
would be worth having if we could afford the labour.

The replay corpus answers a version of that from outside our own design: every
opponent is an independent choice of build, and we know what each scored. This
is observational, not causal -- strong players differ in many ways at once --
but a flat or negative relationship would be a real argument against spending
effort raising the cap.

Run:  python -m analysis.correlate
"""

import math
from collections import Counter

from ladder import fingerprint, load_replays, our_team_name


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def collect():
    """One row per player-appearance: their day-12 build and final score."""
    rows = []
    replays = load_replays()
    me = our_team_name(replays)
    for r in replays:
        names = (r.get("info") or {}).get("TeamNames") or []
        rewards = r.get("rewards") or []
        if len(names) != 2 or len(rewards) != 2 or None in rewards:
            continue
        if names[0] == names[1]:
            continue                              # validation self-play
        for seat in (0, 1):
            fp = fingerprint(r, seat)
            if not fp:
                continue
            fp["score"] = rewards[seat]
            fp["is_us"] = names[seat] == me
            fp["team"] = names[seat]
            rows.append(fp)
    return rows


def band(rows, key, edges, label):
    print(f"\n  {label}")
    print(f"    {'band':>12} {'n':>4} {'mean score':>12} {'median':>10}")
    for lo, hi in zip(edges, edges[1:] + [10 ** 9]):
        sel = [r for r in rows if lo <= r[key] < hi]
        if not sel:
            continue
        scores = sorted(r["score"] for r in sel)
        mean = sum(scores) / len(scores)
        med = scores[len(scores) // 2]
        name = f"{lo}-{hi - 1}" if hi < 10 ** 9 else f"{lo}+"
        print(f"    {name:>12} {len(sel):>4} {mean:>12,.0f} {med:>10,.0f}")


def main():
    rows = collect()
    theirs = [r for r in rows if not r["is_us"]]
    ours = [r for r in rows if r["is_us"]]
    print(f"{len(rows)} player-appearances: {len(theirs)} opponents, {len(ours)} ours\n")

    if len(theirs) < 5:
        print("too few opponents to say anything")
        return

    print("=== opponents: correlation of day-12 build with final score ===")
    for key in ("animals", "melon_tiles", "wheat_tiles", "structures", "quadrants", "hands"):
        xs = [r[key] for r in theirs]
        ys = [r["score"] for r in theirs]
        rho = pearson(xs, ys)
        spread = f"{min(xs)}-{max(xs)}"
        if rho is None:
            print(f"  {key:<14} n/a (no variation)")
        else:
            print(f"  {key:<14} r = {rho:>+6.2f}   range {spread:>8}   mean {sum(xs) / len(xs):>5.1f}")

    band(theirs, "animals", [0, 1, 3, 6, 10], "opponent score by animal count")
    band(theirs, "melon_tiles", [0, 1, 6, 12, 20], "opponent score by melon tiles")

    if ours:
        our_animals = [r["animals"] for r in ours]
        print(f"\n=== us ===")
        print(f"  animals at day 12: mean {sum(our_animals) / len(our_animals):.1f}"
              f"   range {min(our_animals)}-{max(our_animals)}")
        print(f"  score: mean {sum(r['score'] for r in ours) / len(ours):,.0f}")

    print("\n  Observational only. Strong players differ in many ways at once, so a")
    print("  positive correlation is not evidence that adding animals alone would help.")


if __name__ == "__main__":
    main()
