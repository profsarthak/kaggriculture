"""Pull ladder data and turn it into an iteration decision.

The point is not to collect episodes for their own sake. It is to answer two
questions that local benchmarking cannot:

  1. Is the current submission actually better than the last one? Rating moves
     on win/loss only, so this needs enough episodes for the win-rate interval
     to clear 50% -- until then a rating change is noise.
  2. What are real opponents doing? A4 built a best-response table indexed by
     the opponent's melon commitment, and the agent currently plays a fixed 8
     tiles because we had no idea what the field does. Replays contain the
     opponent's board, so this is measurable.

Deliberately does NOT auto-submit. It reports when there is enough signal to
justify iterating; the decision stays yours.

Run:  python ladder.py            # pull + summarise
      python ladder.py --no-fetch # re-analyse what is already cached
"""

import argparse
import csv
import io
import json
import math
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REPLAYS = os.path.join(DATA, "replays")
LOG = os.path.join(DATA, "ladder-log.jsonl")
COMPETITION = "kaggriculture"

# Episodes needed to distinguish a true win rate from 50% at 95% confidence.
# Detecting small edges is expensive, which is what sets the iteration cadence:
# early changes are large and cheap to measure, later ones are neither.
SAMPLE_SIZE = {0.70: 50, 0.60: 200, 0.55: 800}

# Only the latest two submissions are scored. That makes them a champion/
# challenger pair: submitting a third displaces the champion and throws away
# the comparison, so the cadence is set by how long a pair needs, not by the
# 5/day submission cap.
TRACKED_SLOTS = 2


def kaggle(*args, timeout=300):
    """Call the Kaggle CLI. Returns stdout, or None if it failed."""
    exe = [sys.executable, "-m", "kaggle"]
    try:
        proc = subprocess.run(
            exe + list(args), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def parse_csv(text):
    if not text:
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if "," in ln and not ln.startswith("Next Page")), 0)
    return list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))


def wilson(wins, n, z=1.96):
    """Wilson score interval -- honest at small n, unlike normal approximation."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


# --- replay analysis ------------------------------------------------------

def fingerprint(replay, player):
    """Summarise one player's strategy from a replay.

    Sampled around day 12 -- late enough that melon and coops are committed,
    early enough that one-time crops have not all been harvested off the board.
    """
    steps = replay.get("steps") or []
    if not steps:
        return None
    cfg = replay.get("configuration") or {}
    per_day = int(cfg.get("turnsPerDay", 24) or 24)
    idx = min(len(steps) - 1, 12 * per_day)

    try:
        obs = steps[idx][0]["observation"]
        farm = obs["farms"][player]
    except (KeyError, IndexError, TypeError):
        return None

    crops, animals, structures = Counter(), Counter(), 0
    for row in farm.get("tiles", []):
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                crops[t.get("crop")] += 1
            elif t.get("kind") in ("COOP", "PASTURE"):
                structures += 1
                if t.get("animal"):
                    animals[t["animal"]] += 1

    final = steps[-1]
    try:
        final_farms = final[0]["observation"]["farms"]
        money = [f.get("money") for f in final_farms]
    except (KeyError, IndexError, TypeError):
        money = [None, None]

    return {
        "melon_tiles": crops.get("MELON", 0),
        "wheat_tiles": crops.get("WHEAT", 0),
        "crops": dict(crops),
        "animals": sum(animals.values()),
        "structures": structures,
        "quadrants": len(farm.get("unlocked_quadrants", [])),
        "hands": len(farm.get("hands", [])),
        "final_money": money[player],
    }


def analyse_replays():
    ours, theirs, results = [], [], []
    if not os.path.isdir(REPLAYS):
        return ours, theirs, results

    for name in sorted(os.listdir(REPLAYS)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(REPLAYS, name)
        try:
            with open(path, encoding="utf-8") as f:
                replay = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        # Which seat were we? The metadata sidecar records it; default to 0.
        meta_path = path.replace(".json", ".meta.json")
        seat = 0
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    seat = json.load(f).get("seat", 0)
            except (OSError, json.JSONDecodeError):
                pass
        us = fingerprint(replay, seat)
        them = fingerprint(replay, 1 - seat)
        if not us or not them:
            continue
        ours.append(us)
        theirs.append(them)
        if us["final_money"] is not None and them["final_money"] is not None:
            results.append(1 if us["final_money"] > them["final_money"] else 0)
    return ours, theirs, results


# --- fetching -------------------------------------------------------------

def fetch():
    os.makedirs(REPLAYS, exist_ok=True)
    subs = parse_csv(kaggle("competitions", "submissions", COMPETITION, "--format", "csv"))
    if not subs:
        print("could not read submissions -- is the Kaggle CLI authenticated?")
        return subs, 0

    print(f"{len(subs)} submission(s):")
    for s in subs[:5]:
        print(f"  {s.get('ref'):>10}  {s.get('status', ''):<28} {s.get('description', '')[:50]}")

    new = 0
    for s in subs[:2]:                     # only the latest two are scored
        sub_id = s.get("ref")
        if not sub_id:
            continue
        eps = parse_csv(kaggle("competitions", "episodes", sub_id, "--format", "csv"))
        print(f"  submission {sub_id}: {len(eps)} episode(s)")
        for ep in eps:
            ep_id = ep.get("id") or ep.get("ref") or ep.get("episodeId")
            if not ep_id:
                continue
            dest = os.path.join(REPLAYS, f"{ep_id}.json")
            if os.path.exists(dest):
                continue
            if kaggle("competitions", "replay", str(ep_id), "-p", REPLAYS) is None:
                continue
            new += 1
    print(f"  downloaded {new} new replay(s)")
    return subs, new


def standing():
    rows = parse_csv(kaggle("competitions", "leaderboard", COMPETITION, "-s", "--format", "csv"))
    return rows[:5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    os.makedirs(DATA, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"=== ladder check {stamp} ===\n")

    subs, new = ([], 0) if args.no_fetch else fetch()

    ours, theirs, results = analyse_replays()
    n = len(results)
    wins = sum(results)

    print(f"\n=== {n} scored episode(s) analysed ===")
    entry = {"time": stamp, "episodes": n, "wins": wins, "new_replays": new}

    if n:
        p, lo, hi = wilson(wins, n)
        print(f"  win rate {wins}/{n} = {p:.0%}   95% CI [{lo:.0%}, {hi:.0%}]")
        entry.update({"win_rate": round(p, 3), "ci": [round(lo, 3), round(hi, 3)]})

        melon = [t["melon_tiles"] for t in theirs]
        animals = [t["animals"] for t in theirs]
        quads = [t["quadrants"] for t in theirs]
        contest = sum(1 for m in melon if m > 0)
        print("\n=== what the field actually does (day 12 snapshot) ===")
        print(f"  melon tiles   mean {sum(melon) / n:.1f}   max {max(melon)}"
              f"   contesting {contest}/{n}")
        print(f"  animals       mean {sum(animals) / n:.1f}   max {max(animals)}")
        print(f"  quadrants     mean {sum(quads) / n:.1f}")
        entry.update({
            "opp_melon_mean": round(sum(melon) / n, 2),
            "opp_contesting": contest,
            "opp_animals_mean": round(sum(animals) / n, 2),
        })

        avg_melon = sum(melon) / n
        if contest == 0:
            print("\n  A4 says: nobody is contesting melon -> raise melon_tiles to 11")
            print("  (best response to an opponent at 0 is worth +$20,702).")
        elif avg_melon > 12:
            print(f"\n  A4 says: field averages {avg_melon:.1f} melon tiles -> stay at 8;")
            print("  over-committing floods the pool.")
    else:
        print("  no scored episodes yet -- the validation episode may still be running.")

    recommend(subs, n, entry)

    for row in standing() or []:
        print(f"\n  leaderboard top: {row.get('teamName')} @ {row.get('score')}")
        break

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"\n  appended to {LOG}")


def history():
    if not os.path.exists(LOG):
        return []
    out = []
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def recommend(subs, episodes, entry):
    """Decide whether there is enough data to justify another submission.

    Two things make raw win rate the wrong headline metric here:

      * Matchmaking pairs you with similarly-rated bots, so a *successful*
        agent converges toward 50% by construction. A win rate near 50% at a
        high rating is the target state, not a failure.
      * Only the latest two submissions are scored, so they act as champion and
        challenger. Submitting a third discards the comparison.

    So the signal we actually want is the rating gap between the tracked pair,
    and the constraint is how fast episodes accrue.
    """
    print("\n=== iteration decision ===")

    rated = []
    for s in subs[:TRACKED_SLOTS]:
        score = s.get("publicScore")
        try:
            rated.append((s.get("ref"), s.get("description", "")[:34], float(score)))
        except (TypeError, ValueError):
            rated.append((s.get("ref"), s.get("description", "")[:34], None))

    for ref, desc, score in rated:
        shown = f"{score:,.1f}" if score is not None else "unrated yet"
        print(f"  {ref:>10}  {shown:>12}  {desc}")
    entry["ratings"] = {r: s for r, _d, s in rated}

    # Episode accrual rate, measured rather than assumed.
    hist = history()
    rate = None
    if hist:
        prev = hist[-1]
        try:
            dt = datetime.fromisoformat(entry["time"]) - datetime.fromisoformat(prev["time"])
            hours = dt.total_seconds() / 3600
            if hours > 0.5:
                rate = (episodes - prev.get("episodes", 0)) / hours * 24
                print(f"\n  accrual: {rate:.0f} episodes/day at this rating")
                entry["episodes_per_day"] = round(rate, 1)
        except (KeyError, ValueError):
            pass

    if episodes == 0:
        print("\n  WAIT -- nothing scored yet. Re-check in a few hours.")
        return

    for target, need in sorted(SAMPLE_SIZE.items(), reverse=True):
        if episodes >= need:
            print(f"\n  {episodes} episodes resolves an edge of ~{target:.0%} or better.")
            break
    else:
        smallest = min(SAMPLE_SIZE.items(), key=lambda kv: abs(kv[1] - episodes))
        print(f"\n  {episodes} episodes only resolves large edges "
              f"(~{smallest[0]:.0%} needs {smallest[1]}).")

    if rate:
        for target, need in sorted(SAMPLE_SIZE.items(), reverse=True):
            if need > episodes:
                days = (need - episodes) / rate
                print(f"  to resolve a {target:.0%} edge: ~{days:.1f} more days")
                break

    both_rated = [s for _r, _d, s in rated if s is not None]
    if len(both_rated) == TRACKED_SLOTS:
        gap = both_rated[0] - both_rated[1]
        print(f"\n  challenger vs champion: {gap:+.1f} rating")
        if abs(gap) < 50:
            print("  Too close to call. Hold -- a third submission would displace the champion")
            print("  and throw away the comparison.")
        elif gap > 0:
            print("  Challenger is ahead. Promote it and start the next challenger.")
        else:
            print("  Challenger is behind. Revert the change and try a different one.")
    else:
        print("\n  Only one rated submission -- nothing to compare against yet.")


if __name__ == "__main__":
    main()
