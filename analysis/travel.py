"""Where does the walking actually go?

The routing rework took travel from 65% of worker turns to 51%, and that is now
the largest remaining inefficiency. Before changing anything again, attribute it:

  * **Commute** -- shed to the first tile each morning. Workers respawn at the
    shed every day, so this is paid 30 times over a season per worker.
  * **Hops** -- moving between work tiles during the day.
  * **Actions per visit** -- an animal tile wants 4 actions (FEED, CARE,
    HARVEST, COLLECT_FERTILIZER) and a crop tile usually 1. If a worker leaves
    an animal tile after one action and comes back, that is pure waste.

The floor is set by the mix: a crop tile costing 1 move + 1 action is 50%
travel no matter how good the routing is, while an animal tile worked 4 actions
deep is 20%. So "reduce travel" may really mean "change what is being worked",
and this separates those.

Run:  python -m analysis.travel
"""

from collections import Counter

from kaggle_environments import make

from farmlib import Config, make_agent, shed_tiles

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def main(seed=5):
    cfg = Config()
    inner = make_agent(cfg)

    # per worker: last position acted on, and whether it has worked yet today
    last_worked = {}
    started = {}
    stats = Counter()
    visit_runs = Counter()
    run_len = {}

    def wrapped(obs):
        action = inner(obs)
        day = obs["day"]
        farm = obs["farms"][obs["player"]]
        size = len(farm["tiles"])
        sheds = shed_tiles(size)
        units = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        ops = [action["farmer"]] + list(action["hands"])

        if obs["hour"] == 0:
            last_worked.clear()
            started.clear()
            for key in list(run_len):
                visit_runs[min(run_len[key], 5)] += 1
            run_len.clear()

        for i, op in enumerate(ops):
            if i >= len(units):
                break
            name = op[0]
            pos = units[i]
            if name in MOVES:
                stats["move"] += 1
                # A move before the worker's first action of the day, starting
                # from a shed tile, is commute.
                if not started.get(i) and pos in sheds:
                    stats["commute_start"] += 1
                elif not started.get(i):
                    stats["commute"] += 1
                else:
                    stats["hop"] += 1
            elif name == "PASS":
                stats["idle"] += 1
            else:
                stats["work"] += 1
                started[i] = True
                key = (day, i)
                if last_worked.get(i) == pos:
                    run_len[key] = run_len.get(key, 1) + 1
                    stats["repeat_visit_action"] += 1
                else:
                    if key in run_len:
                        visit_runs[min(run_len[key], 5)] += 1
                    run_len[key] = 1
                    stats["first_action_at_tile"] += 1
                last_worked[i] = pos
        return action

    env = make("kaggriculture", configuration={"seed": seed})
    env.run([wrapped, "starter"])

    total = stats["move"] + stats["work"] + stats["idle"]
    print(f"score {env.steps[-1][0].reward:,.0f}   {total:,} worker turns\n")

    print("=== turn budget ===")
    for key in ("work", "move", "idle"):
        print(f"  {key:<8} {stats[key]:>6,}  {stats[key] / total:>6.1%}")

    print("\n=== what the moving is for ===")
    commute = stats["commute_start"] + stats["commute"]
    for label, v in (("commute (shed -> first tile)", commute), ("hops between tiles", stats["hop"])):
        print(f"  {label:<30} {v:>6,}  {v / max(1, stats['move']):>6.1%} of moves")

    print("\n=== actions per tile visit ===")
    first = stats["first_action_at_tile"]
    repeat = stats["repeat_visit_action"]
    print(f"  distinct tile visits      {first:>6,}")
    print(f"  follow-up actions on tile {repeat:>6,}")
    print(f"  actions per visit         {(first + repeat) / max(1, first):>6.2f}")
    print("\n  visit depth distribution (actions before leaving):")
    for depth in sorted(visit_runs):
        label = f"{depth}" if depth < 5 else "5+"
        print(f"    {label:>3} action(s): {visit_runs[depth]:>5,}")

    print("\n  An animal tile wants 4 actions per visit; a crop tile 1.")
    print("  Visits ending at depth 1 on animal tiles are round-trips we pay twice for.")


if __name__ == "__main__":
    main()
