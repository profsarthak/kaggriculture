"""Scoring harness with health assertions.

Two jobs:

1. Score an agent over many seeded episodes. Single games are noise -- weed
   spawns and the shop unlock order are random, and docs/04-pools.md shows a
   melon timing difference alone can swing $12,000.

2. Catch silent breakage. Invalid actions no-op with no signal anywhere in the
   observation: a starved animal, an unwatered plant and a discarded shed
   overflow all look exactly like a slightly lower score. The health checks
   below inspect the final board for evidence that the agent was quietly
   failing, which is the only way to tell a bad strategy from a bug.

Run:  python bench.py                 # default config vs starter, 30 episodes
      python bench.py --n 10 --opp random
"""

import argparse
import statistics
from collections import Counter

from kaggle_environments import make

from farmlib import Config, make_agent


def health_report(env, player=0):
    """Evidence of silent failure on the final board."""
    obs = env.steps[-1][player].observation
    farm = obs["farms"][player]
    counts = Counter()

    for row in farm["tiles"]:
        for t in row:
            if t is None or not isinstance(t, dict):
                continue
            kind = t.get("kind")
            if kind == "WEED":
                counts["weeds"] += 1
            elif kind == "PLANT":
                counts["plants"] += 1
                if t.get("consecutive_unwatered", 0) >= 1:
                    counts["thirsty"] += 1
            elif kind in ("COOP", "PASTURE"):
                if t.get("animal"):
                    counts["animals"] += 1
                    if t.get("consecutive_unfed", 0) >= 1:
                        counts["hungry"] += 1
                else:
                    counts["empty_structures"] += 1

    counts["shed_used"] = sum(obs["private"]["shed"].values())
    counts["unsold_value_units"] = counts["shed_used"]
    counts["quadrants"] = len(farm["unlocked_quadrants"])
    return counts


def resolve_opponent(spec, cfg):
    """Allow benchmarking against ourselves, not just the built-in agents.

    `starter` turned out to be a strawman: it finishes on ~3,500 coins while
    real ladder opponents finish on ~41,000. Beating it 15/15 measured nothing.
    Self-play against the current or a previous config is a far more honest
    signal, and is also what Phase C's payoff matrix will be built from.
    """
    if spec == "self":
        return make_agent(cfg)
    if spec.startswith("cfg:"):
        kwargs = {}
        for pair in spec[4:].split(","):
            key, _, value = pair.partition("=")
            try:
                kwargs[key] = float(value) if "." in value else int(value)
            except ValueError:
                kwargs[key] = value
        return make_agent(Config(**kwargs))
    return spec


def run_episodes(cfg, opponent, n, verbose=False):
    scores, opp_scores, wins, health = [], [], 0, Counter()
    for seed in range(n):
        env = make("kaggriculture", configuration={"seed": seed})
        env.run([make_agent(cfg), resolve_opponent(opponent, cfg)])
        final = env.steps[-1]
        us, them = final[0].reward or 0, final[1].reward or 0
        scores.append(us)
        opp_scores.append(them)
        wins += 1 if us > them else 0
        for k, v in health_report(env).items():
            health[k] += v
        if verbose:
            print(f"  seed {seed:>3}: {us:>9,.0f} vs {them:>9,.0f}")
    return scores, opp_scores, wins, health


def sweep(args):
    """Grid over the knobs Phase A could not derive.

    labour_headroom sizes the working area against the workforce, and it is the
    one number A3's flat travel multiplier could not predict -- a real greedy
    assignment over scattered tiles behaves nothing like a constant tax.
    """
    print(f"grid over {args.n} seeds each, vs {args.opp}\n")
    header = f"{'headroom':>9} {'hands':>6} {'geese':>6} {'mean':>9} {'win%':>6} {'weeds':>7} {'hungry':>7}"
    print(header)
    print("-" * len(header))
    best = None
    for headroom in (0.20, 0.30, 0.35):
        for hands in (5, 6, 8):
            cfg = Config(labour_headroom=headroom, hands_target=hands)
            scores, opp, wins, health = run_episodes(cfg, args.opp, args.n)
            mean = statistics.mean(scores)
            print(
                f"{headroom:>9.2f} {hands:>6} {cfg.goose_target:>6} {mean:>9,.0f}"
                f" {wins / len(scores):>5.0%} {health['weeds'] / args.n:>7.1f}"
                f" {health['hungry'] / args.n:>7.1f}"
            )
            if best is None or mean > best[0]:
                best = (mean, headroom, hands)
    print(f"\nbest: headroom {best[1]}, hands {best[2]} -> {best[0]:,.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--opp", default="starter")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    if args.sweep:
        return sweep(args)

    cfg = Config()
    scores, opp, wins, health = run_episodes(cfg, args.opp, args.n, args.verbose)

    n = len(scores)
    print(f"\n=== {n} episodes vs {args.opp} ===")
    print(f"  win rate   {wins}/{n} = {wins / n:.0%}")
    print(f"  our score  mean {statistics.mean(scores):>10,.0f}"
          f"   median {statistics.median(scores):>10,.0f}")
    print(f"  their score mean {statistics.mean(opp):>9,.0f}")
    if n > 1:
        print(f"  our stdev  {statistics.stdev(scores):>10,.0f}")

    print("\n=== health (totals across episodes; per-episode in brackets) ===")
    for key in (
        "animals", "hungry", "plants", "thirsty", "weeds",
        "empty_structures", "shed_used", "quadrants",
    ):
        v = health[key]
        print(f"  {key:<18} {v:>7,}  [{v / n:>8.1f}]")

    warnings = []
    if health["hungry"]:
        warnings.append(
            f"{health['hungry'] / n:.1f} animals/episode ended unfed -- FEED is failing, "
            "most likely no wheat carried (inventory empties overnight)"
        )
    if health["thirsty"] > health["plants"] * 0.2:
        warnings.append("over 20% of surviving plants ended thirsty -- watering is behind")
    if health["weeds"] / n > 5:
        warnings.append(f"{health['weeds'] / n:.1f} weeds/episode -- plants are dying or DIG is starved")
    if health["empty_structures"] / n > 2:
        warnings.append(
            f"{health['empty_structures'] / n:.1f} empty coops/episode -- built structures "
            "we never stocked; wasted build actions and land"
        )
    if health["shed_used"] / n > 80:
        warnings.append(
            f"shed averaging {health['shed_used'] / n:.0f}/100 at end -- close to the cap, "
            "overflow is discarded silently"
        )

    if warnings:
        print("\n  WARNINGS")
        for w in warnings:
            print(f"    - {w}")
    else:
        print("\n  no health warnings")


if __name__ == "__main__":
    main()
