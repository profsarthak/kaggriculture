"""Are the layout's tile-cost estimates right?

`plan_layout` sizes the farm by charging each tile a daily action cost from
TILE_COST, which came from A2's analytic model and has never been checked
against play. Everything downstream depends on it: `pasture_target=9`,
`goose_target=22` and `fertilizer_quota=20` all measure exactly +0 because the
budget is saturated, so the budget's accuracy now *is* the constraint.

This counts what each tile type actually consumes in a real episode.

Run:  python -m analysis.tilecost
"""

from collections import Counter

from kaggle_environments import make

from farmlib import TILE_COST, Config, make_agent, plan_layout

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def main(seed=5):
    cfg = Config()
    inner = make_agent(cfg)
    actions_by_role = Counter()
    tiles_by_role = Counter()
    days = set()

    def wrapped(obs):
        action = inner(obs)
        farm = obs["farms"][obs["player"]]
        # Must match how the agent sizes the layout. Calling this at hour 0 with
        # the live hand count gives a one-worker farm, because hires are market
        # orders that settle after the hour-0 actions.
        roles = plan_layout(farm, cfg, max(len(farm["hands"]) + 1, cfg.hands_target + 1))
        days.add(obs["day"])

        if obs["hour"] == 0:
            for role in roles.values():
                tiles_by_role[role] += 1

        units = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        ops = [action["farmer"]] + list(action["hands"])
        for i, op in enumerate(ops):
            if i >= len(units) or not op:
                continue
            if op[0] in MOVES or op[0] == "PASS":
                continue
            role = roles.get(units[i])
            actions_by_role[role or "OFF_PLAN"] += 1
        return action

    env = make("kaggriculture", configuration={"seed": seed})
    env.run([wrapped, "starter"])

    print(f"score {env.steps[-1][0].reward:,.0f} over {len(days)} days\n")
    header = f"{'role':<10} {'tile-days':>10} {'actions':>9} {'measured':>10} {'model':>8} {'ratio':>7}"
    print(header)
    print("-" * len(header))
    for role in ("MELON", "WHEAT", "COOP", "PASTURE"):
        tile_days = tiles_by_role[role]
        acts = actions_by_role[role]
        if not tile_days:
            continue
        measured = acts / tile_days
        model = TILE_COST[role]
        print(f"{role:<10} {tile_days:>10,} {acts:>9,} {measured:>10.2f} {model:>8.2f}"
              f" {measured / model:>7.2f}")

    stray = actions_by_role["OFF_PLAN"]
    total = sum(actions_by_role.values())
    print(f"\n  actions on tiles with no planned role: {stray:,} ({stray / max(1, total):.1%})")
    print("  (shed pickups happen on centre tiles, which may hold any role)")
    print("\n  ratio > 1 means the model under-charges that tile type, so the")
    print("  layout believes it can afford more of them than it really can.")


if __name__ == "__main__":
    main()
