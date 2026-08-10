"""Full-season trajectories for the strongest opponents on our ladder.

`ladder.py:fingerprint` samples one day-12 snapshot per replay, which was enough
to show *what* the strong builds are (docs/23-what-beats-us.md) but not *when*
they do it. The opening trace that came out of a one-off script was the single
most informative measurement of the project -- they spend the whole opening 3,000
on livestock inside two days and buy land around day 8, where we buy land at hour
1 of day 0 and our first animal on day 5.

This makes that measurement repeatable and extends it across the season, so the
compact build has a trajectory to hit rather than a score to chase. A trajectory
is a far tighter signal than a final score: it says which day we diverge.

Replays are large and there are hundreds, so extraction is cached in
data/field-trajectories.json and only new files are parsed.

Run:  python -m analysis.field                 # top 10, every 2 days
      python -m analysis.field --top 25        # wider group
      python -m analysis.field --compare       # against our current build
"""

import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPLAYS = os.path.join(ROOT, "data", "replays")
CACHE = os.path.join(ROOT, "data", "field-trajectories.json")
# Whose seat to read in a replay. Override to reuse this on another
# account: KAGGLE_TEAM_NAME="Your Team" python -m analysis.field
ME = os.environ.get("KAGGLE_TEAM_NAME", "Sarthak Vedant Mohanty")

FIELDS = ("money", "animals", "cows", "sheep", "geese", "structures",
          "quadrants", "melon", "wheat")


def snapshot(farm):
    """One player's state on one step, in the terms the layout plan uses."""
    counts = {k: 0 for k in FIELDS}
    counts["money"] = int(farm.get("money", 0))
    counts["quadrants"] = len(farm.get("unlocked_quadrants") or [])
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "PLANT":
                crop = tile.get("crop")
                if crop == "MELON":
                    counts["melon"] += 1
                elif crop == "WHEAT":
                    counts["wheat"] += 1
            elif kind in ("COOP", "PASTURE"):
                counts["structures"] += 1
                animal = tile.get("animal")
                if animal:
                    counts["animals"] += 1
                    key = {"COW": "cows", "SHEEP": "sheep", "GOOSE": "geese"}.get(animal)
                    if key:
                        counts[key] += 1
    return counts


def trajectory(replay, player, days):
    steps = replay.get("steps") or []
    if not steps:
        return None
    per_day = int((replay.get("configuration") or {}).get("turnsPerDay", 24) or 24)
    out = {}
    for day in days:
        idx = min(len(steps) - 1, day * per_day)
        try:
            farm = steps[idx][0]["observation"]["farms"][player]
        except (KeyError, IndexError, TypeError):
            return None
        out[str(day)] = snapshot(farm)
    return out


def load_cache():
    if not os.path.exists(CACHE):
        return {}
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def extract(days, refresh=False):
    """Opponent trajectories keyed by replay file, cached across runs."""
    cache = {} if refresh else load_cache()
    wanted = {str(d) for d in days}
    fresh = 0

    for path in sorted(glob.glob(os.path.join(REPLAYS, "*.json"))):
        key = os.path.basename(path)
        hit = cache.get(key)
        if hit and hit.get("opp") and wanted <= set(hit["opp"]):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                replay = json.load(f)
        except (OSError, json.JSONDecodeError):
            cache[key] = {"skip": True}
            continue
        names = (replay.get("info") or {}).get("TeamNames") or []
        rewards = replay.get("rewards") or []
        if (len(names) != 2 or len(rewards) != 2 or None in rewards
                or names[0] == names[1] or ME not in names):
            cache[key] = {"skip": True}
            continue
        seat = 0 if names[0] == ME else 1
        opp = trajectory(replay, 1 - seat, days)
        us = trajectory(replay, seat, days)
        if not opp or not us:
            cache[key] = {"skip": True}
            continue
        cache[key] = {
            "name": names[1 - seat],
            "opp_score": rewards[1 - seat],
            "our_score": rewards[seat],
            "opp": opp,
            "us": us,
        }
        fresh += 1

    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    return cache, fresh


def averaged(records, side, days):
    """Mean trajectory over a group of records."""
    out = {}
    for day in days:
        key = str(day)
        rows = [r[side][key] for r in records if key in r[side]]
        if not rows:
            continue
        out[day] = {f: sum(r[f] for r in rows) / len(rows) for f in FIELDS}
    return out


def show(label, traj, days):
    print(f"\n  {label}")
    print("    day     " + "".join(f"{d:>8}" for d in days))
    for field in FIELDS:
        row = "".join(
            f"{traj[d][field]:>8.0f}" if d in traj else f"{'-':>8}" for d in days
        )
        print(f"    {field:<8}" + row)


def our_trajectory(days, seed=0):
    """The same measurement taken from our own agent, for a like-for-like diff."""
    from kaggle_environments import make
    import farmlib

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([farmlib.make_agent(), farmlib.make_agent()])
    out = {}
    for day in days:
        idx = min(len(env.steps) - 1, day * 24)
        out[day] = snapshot(env.steps[idx][0].observation["farms"][0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--compare", action="store_true",
                    help="also run our current build and diff against the target")
    args = ap.parse_args()

    days = list(range(0, 30, args.every))
    cache, fresh = extract(days, args.refresh)
    records = [r for r in cache.values() if not r.get("skip")]
    print(f"=== field trajectories: {len(records)} usable replays "
          f"({fresh} newly parsed) ===")
    if not records:
        return 1

    records.sort(key=lambda r: -r["opp_score"])
    top = records[: args.top]
    names = {r["name"] for r in top}
    print(f"top {len(top)} performances, {len(names)} distinct players, "
          f"mean score {sum(r['opp_score'] for r in top) / len(top):,.0f}")

    show(f"TOP {args.top} OPPONENTS", averaged(top, "opp", days), days)
    show("US (as recorded on the ladder)", averaged(records, "us", days), days)

    if args.compare:
        mine = our_trajectory(days)
        show("US (current build, seed 0)", mine, days)
        target = averaged(top, "opp", days)
        print("\n  GAP (target minus current build)")
        print("    day     " + "".join(f"{d:>8}" for d in days))
        for field in FIELDS:
            row = "".join(
                f"{target[d][field] - mine[d][field]:>+8.0f}" if d in target else f"{'-':>8}"
                for d in days
            )
            print(f"    {field:<8}" + row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
