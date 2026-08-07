"""How the strongest opponents spend their worker turns.

`analysis/travel.py` attributes our own turn budget: 46.8% moving, 38.8% working,
14.4% idle, at 1.89 actions per tile visit. `analysis/field.py` shows what the
strong builds *have* — 15 animals and 11 melon tiles on roughly 34 worked tiles
where we need 62. Neither says how they service it.

Replays record the opponent's full action stream, not just the board, so the same
attribution can be computed for them. This is the last question the project has a
concrete method for: if their turn budget looks like ours, the difference is
elsewhere and the tuning phase is finished; if it does not, the gap is named.

Run:  python -m analysis.opponents            # top 8 opponent performances
      python -m analysis.opponents --top 15
"""

import argparse
import glob
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPLAYS = os.path.join(ROOT, "data", "replays")
CACHE = os.path.join(ROOT, "data", "field-trajectories.json")
ME = "Sarthak Vedant Mohanty"

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
ANIMAL_OPS = {"FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER", "PLACE"}
CROP_OPS = {"PLANT", "WATER", "FERTILIZE"}
SHED_OPS = {"PICKUP", "DROP"}


def units_at(step, player):
    """Worker positions this turn, farmer first, from the shared farm state."""
    try:
        farm = step[0]["observation"]["farms"][player]
    except (KeyError, IndexError, TypeError):
        return None
    return [tuple(farm.get("farmer") or (0, 0))] + [
        tuple(h) for h in (farm.get("hands") or [])
    ]


def actions_of(step, player):
    action = step[player].get("action") if len(step) > player else None
    if not isinstance(action, dict):
        return []
    hands = action.get("hands")
    return [action.get("farmer")] + (hands if isinstance(hands, list) else [])


def profile(replay, player):
    """Turn budget, action mix and visit depth for one player over a whole game."""
    steps = replay.get("steps") or []
    counts = Counter()
    turns = 0
    crew_by_day = {}
    # Per unit index: where it was, and how many actions it has taken there.
    depth = {}
    visits = Counter()

    for i, step in enumerate(steps[:-1]):
        pos = units_at(step, player)
        acts = actions_of(step, player)
        if pos is None:
            continue
        crew_by_day[i // 24] = max(crew_by_day.get(i // 24, 0), len(pos))
        for idx, act in enumerate(acts):
            if not isinstance(act, list) or not act:
                continue
            turns += 1
            op = act[0]
            here = pos[idx] if idx < len(pos) else None
            if op in MOVES:
                counts["move"] += 1
                if depth.get(idx):
                    visits[min(depth[idx], 5)] += 1
                depth[idx] = 0
                continue
            if op == "PASS":
                counts["idle"] += 1
                continue
            counts["work"] += 1
            counts[op] += 1
            if op in ANIMAL_OPS:
                counts["animal-work"] += 1
            elif op in CROP_OPS:
                counts["crop-work"] += 1
            elif op in SHED_OPS:
                counts["logistics"] += 1
            if here is not None:
                depth[idx] = depth.get(idx, 0) + 1

    for d in depth.values():
        if d:
            visits[min(d, 5)] += 1
    counts["turns"] = turns
    counts["visits"] = sum(visits.values())
    counts["crew"] = max(crew_by_day.values()) if crew_by_day else 0
    return counts, visits


def show(label, c, visits):
    turns = max(c["turns"], 1)
    print(f"\n  {label}")
    print(f"    worker turns {c['turns']:,}   peak crew {c['crew']}")
    for key in ("move", "work", "idle"):
        print(f"      {key:<12} {c[key]:>6,}  {100 * c[key] / turns:5.1f}%")
    work = max(c["work"], 1)
    for key in ("animal-work", "crop-work", "logistics"):
        print(f"      {key:<12} {c[key]:>6,}  {100 * c[key] / turns:5.1f}%"
              f"   ({100 * c[key] / work:.0f}% of work)")
    if c["visits"]:
        per = c["work"] / c["visits"]
        print(f"      actions per tile visit {per:.2f}"
              f"   (depth 1: {visits[1]}, 2: {visits[2]}, 3: {visits[3]},"
              f" 4: {visits[4]}, 5+: {visits[5]})")
    mix = {k: c[k] for k in ("FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER",
                             "WATER", "PLANT", "PICKUP", "DROP") if c[k]}
    print("      " + "  ".join(f"{k[:5]} {v}" for k, v in mix.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        cache = {}
    ranked = sorted(
        ((v["opp_score"], k, v["name"]) for k, v in cache.items() if not v.get("skip")),
        reverse=True,
    )
    if not ranked:
        print("  no cached trajectories -- run `python -m analysis.field` first")
        return 1

    print(f"=== action profile, top {args.top} opponent performances ===")
    theirs, ours = Counter(), Counter()
    tv, ov = Counter(), Counter()
    seen = set()
    for score, key, name in ranked[: args.top]:
        path = os.path.join(REPLAYS, key)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            replay = json.load(f)
        names = (replay.get("info") or {}).get("TeamNames") or []
        seat = 0 if names[0] == ME else 1
        c, v = profile(replay, 1 - seat)
        theirs.update(c)
        tv.update(v)
        c2, v2 = profile(replay, seat)
        ours.update(c2)
        ov.update(v2)
        seen.add(name)
        print(f"  {name[:28]:<28} {score:>8,.0f}")

    print(f"\n  {len(seen)} distinct players")
    show("THEM (aggregated)", theirs, tv)
    show("US (same games)", ours, ov)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
