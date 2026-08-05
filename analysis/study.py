"""Reconstruct what a ladder opponent actually did, turn by turn.

The field finishes on ~41,600 against our ~19,900, and their day-12 board looks
*less* developed than ours (fewer animals, fewer quadrants). That is a strategy
difference, not a tuning difference, so the way to find it is to read what a
strong opponent did rather than sweep another parameter.

Run:  python -m analysis.study            # the highest-scoring opponent we have
      python -m analysis.study --all      # one summary line per replay
"""

import argparse
import json
from collections import Counter

from ladder import fingerprint, load_replays, our_team_name


def seats(replay, me):
    names = (replay.get("info") or {}).get("TeamNames") or []
    if len(names) != 2 or names[0] == names[1]:
        return None, None
    ours = 0 if names[0] == me else 1
    return ours, 1 - ours


def trace(replay, player):
    """Per-day summary of one player's board, money and actions."""
    steps = replay.get("steps") or []
    cfg = replay.get("configuration") or {}
    per_day = int(cfg.get("turnsPerDay", 24) or 24)

    market = Counter()
    worker_ops = Counter()
    days = []

    for i, step in enumerate(steps):
        try:
            state = step[player]
        except (IndexError, TypeError):
            continue

        action = state.get("action")
        if isinstance(action, dict):
            for op in action.get("market") or []:
                if isinstance(op, list) and op:
                    key = op[0] if op[0] in ("HIRE", "BUY_LAND") else f"{op[0]} {op[1]}"
                    market[key] += 1
            ops = [action.get("farmer")] + list(action.get("hands") or [])
            for op in ops:
                if isinstance(op, list) and op:
                    worker_ops[op[0]] += 1

        if i % per_day != per_day - 1:
            continue
        obs = step[0].get("observation") or {}
        farms = obs.get("farms") or []
        if player >= len(farms):
            continue
        farm = farms[player]
        crops, animals, weeds = Counter(), 0, 0
        for row in farm.get("tiles") or []:
            for t in row:
                if not isinstance(t, dict):
                    continue
                if t.get("kind") == "PLANT":
                    crops[t.get("crop")] += 1
                elif t.get("kind") == "WEED":
                    weeds += 1
                elif t.get("kind") in ("COOP", "PASTURE") and t.get("animal"):
                    animals += 1
        days.append({
            "day": i // per_day,
            "money": int(farm.get("money", 0)),
            "crops": dict(crops),
            "animals": animals,
            "weeds": weeds,
            "quadrants": len(farm.get("unlocked_quadrants") or []),
            "hands": len(farm.get("hands") or []),
        })
    return days, market, worker_ops


def show(replay, player, label):
    days, market, ops = trace(replay, player)
    print(f"\n=== {label} ===")
    print(f"  {'day':>4} {'money':>9} {'hands':>6} {'quad':>5} {'anim':>5} {'weeds':>6}  crops")
    for d in days:
        if d["day"] % 3 and d["day"] != days[-1]["day"]:
            continue
        crops = " ".join(f"{k[:3]}{v}" for k, v in sorted(d["crops"].items()))
        print(f"  {d['day']:>4} {d['money']:>9,} {d['hands']:>6} {d['quadrants']:>5}"
              f" {d['animals']:>5} {d['weeds']:>6}  {crops}")

    print("\n  market orders issued:")
    for key, count in market.most_common(12):
        print(f"    {key:<22} {count:>5}")

    total = sum(ops.values()) or 1
    moving = sum(v for k, v in ops.items() if k in ("NORTH", "SOUTH", "EAST", "WEST"))
    idle = ops.get("PASS", 0)
    print(f"\n  worker turns: {total - moving - idle:,} working "
          f"({(total - moving - idle) / total:.0%}), {moving:,} moving "
          f"({moving / total:.0%}), {idle:,} idle ({idle / total:.0%})")
    print("  top ops: " + ", ".join(
        f"{k} {v}" for k, v in ops.most_common(8)
        if k not in ("NORTH", "SOUTH", "EAST", "WEST")
    ))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    replays = load_replays()
    me = our_team_name(replays)
    if not me:
        raise SystemExit("could not identify our team from the replays")
    print(f"our team: {me}\n")

    matches = []
    for r in replays:
        ours, theirs = seats(r, me)
        if ours is None:
            continue
        rewards = r.get("rewards") or []
        if len(rewards) != 2 or None in rewards:
            continue
        matches.append((rewards[theirs], rewards[ours], r, ours, theirs))
    if not matches:
        raise SystemExit("no completed matches yet")

    matches.sort(reverse=True, key=lambda m: m[0])

    if args.all:
        print(f"{'them':>9} {'us':>9}  opponent")
        for them, us, r, _o, t in matches:
            name = ((r.get("info") or {}).get("TeamNames") or ["", ""])[t]
            print(f"{them:>9,.0f} {us:>9,.0f}  {name}")
        return

    them, us, replay, ours, theirs = matches[0]
    name = ((replay.get("info") or {}).get("TeamNames") or ["", ""])[theirs]
    print(f"studying our heaviest defeat: {name} scored {them:,.0f}, we scored {us:,.0f}")
    show(replay, theirs, f"OPPONENT: {name}")
    show(replay, ours, "US")


if __name__ == "__main__":
    main()
