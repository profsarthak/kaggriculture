"""Why are plants dying? Instrument one episode rather than guessing.

13.5 weeds and 11.9 thirsty plants per episode is the largest known loss in
agent v2. Three candidate causes, which want different fixes:

  1. Over-planting -- more tiles than the workforce can service.
  2. Thrashing -- the per-turn greedy assignment re-decides every turn, so a
     worker walking to a distant tile can be redirected before it arrives and
     never completes anything.
  3. Priority inversion -- watering losing to harvesting when it should not.

Run:  python -m analysis.diagnose
"""

from collections import Counter

from kaggle_environments import make

from farmlib import Config, make_agent

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def main():
    cfg = Config()
    inner = make_agent(cfg)

    stats = Counter()
    per_worker_last = {}
    switches = 0
    samples = []

    def wrapped(obs):
        nonlocal switches
        action = inner(obs)
        day = obs["day"]
        ops = [action["farmer"]] + list(action["hands"])

        for i, op in enumerate(ops):
            name = op[0]
            stats[name] += 1
            if name in MOVES:
                stats["_moving"] += 1
            elif name != "PASS":
                stats["_working"] += 1
            else:
                stats["_idle"] += 1

        # A worker that moves in one direction then reverses is being
        # re-targeted mid-journey: the signature of thrashing.
        for i, op in enumerate(ops):
            prev = per_worker_last.get((day, i))
            cur = op[0]
            if prev in MOVES and cur in MOVES and prev != cur:
                opposite = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST"}
                if opposite[prev] == cur:
                    switches += 1
            per_worker_last[(day, i)] = cur

        farm = obs["farms"][obs["player"]]
        if obs["hour"] == 23:
            plants = thirsty = weeds = 0
            for row in farm["tiles"]:
                for t in row:
                    if isinstance(t, dict):
                        if t.get("kind") == "PLANT":
                            plants += 1
                            if not t.get("watered_today"):
                                thirsty += 1
                        elif t.get("kind") == "WEED":
                            weeds += 1
            samples.append((day, plants, thirsty, weeds, int(farm["money"])))
        return action

    env = make("kaggriculture", configuration={"seed": 5})
    env.run([wrapped, "starter"])
    print(f"final score {env.steps[-1][0].reward:,.0f}\n")

    total = stats["_moving"] + stats["_working"] + stats["_idle"]
    print("=== where worker turns go ===")
    for key in ("_working", "_moving", "_idle"):
        print(f"  {key[1:]:<9} {stats[key]:>6,}  {stats[key] / total:>6.1%}")
    print(f"\n  direction reversals mid-journey: {switches:,}"
          f"  ({switches / max(1, stats['_moving']):.1%} of moves)")

    print("\n=== action mix (non-move) ===")
    for name, count in stats.most_common():
        if name.startswith("_") or name in MOVES:
            continue
        print(f"  {name:<20} {count:>6,}")

    print("\n=== end-of-day board ===")
    print(f"  {'day':>4} {'plants':>7} {'unwatered':>10} {'weeds':>6} {'money':>10}")
    for day, plants, thirsty, weeds, money in samples:
        if day % 3 == 0 or day > 26:
            print(f"  {day:>4} {plants:>7} {thirsty:>10} {weeds:>6} {money:>10,}")


if __name__ == "__main__":
    main()
