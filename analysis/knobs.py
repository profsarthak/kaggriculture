"""Which config parameters actually change what the agent does?

The layout-drift bug (docs/22-layout-drift.md) hid for the whole project because
`pasture_target` and `goose_target` set quotas that the planner then overrode.
Nothing caught it: the tuner sweeps values and reads the *score*, so a knob that
does nothing looks the same as a knob whose best value we already hold. Four
tuner passes swept two dead parameters without noticing.

This asks the cheaper and much more sensitive question. Not "is this value
better" but "does this value change a single action the agent takes". A knob that
changes nothing is either gated behind a feature we have switched off -- fine,
and expected -- or it is disconnected, which is a bug.

Method: record the baseline agent's action stream turn by turn, then replay each
perturbed config against the same opponent and seed, aborting the moment the two
streams differ. Live knobs usually diverge within a few turns, so they cost
almost nothing; only genuinely inert knobs pay for a full episode.

Run:  python -m analysis.knobs            # one seed
      python -m analysis.knobs --seeds 3  # confirm the inert ones
"""

import argparse

from kaggle_environments import make

import farmlib

# A plausible alternative for each parameter -- something we might actually
# consider, not a degenerate value that would trivially change everything.
#
# These have to be chosen so they *could* bite. Four of the first run's seven
# "unexplained inert" knobs were bad perturbations, not disconnected code:
# sale_cap was set on MELON, which the metering loop skips because dump_melon
# handles it separately; max_extra_wheat=4 and land_lead=3 were both already
# slack; fertilizer_quota=2 was above what we spend. An inert result is only
# evidence of anything if the value moved past where the parameter binds.
PERTURB = {
    "melon_tiles": 8,
    "goose_target": 8,
    "hands_target": 6,
    "fertilizer_quota": 0,
    "land_purchases": 3,
    "dump_melon": False,
    "cash_floor": 2000,
    "labour_headroom": 0.40,
    "feed_carry": 6,
    "travel_weight": 5.0,
    "buy_feed": True,
    "route_commit": False,
    "carrot_until": 6,
    "pasture_target": 8,
    "pasture_animal": "SHEEP",
    "feed_ratio": 1.25,
    "max_extra_wheat": 0,
    "finish_tile": False,
    "hire_to_demand": False,
    "tiles_per_hand": 3,
    "min_hands": 2,
    "sale_cap": {"MILK": 3},   # MELON is handled by dump_melon and skipped in that loop
    "fertilize_crops": ("MELON",),
    "fert_carry": 6,
    "fert_harvest_day": 8,
    "season_days": 29,
    "land_lead": 25,
    "animals_near_shed": True,
    "risk_from_day": 20,
    "risk_behind": 2000,
    "risk_shed_margin": 50,
    "melon_contest_bonus": 4,
    "melon_concede_threshold": 10,
    "run_melon": True,
    "endgame_sweep": False,
    "endgame_hour": 18,
    "shed_lock_aware": True,
    "shed_shared": True,
    "layout_pinned": False,
    "repurpose_melon": True,
    "repurpose_order": ("WHEAT",),
}

# Knobs that only do anything when another switch is on. Inertness here is
# correct behaviour, not a defect, and saying so keeps the report honest.
GATED_BY = {
    "goose_target": "budget -- 14 pastures exhaust it, so coops are set by the "
                    "remainder (verified inert at 3, 8, 16 and 24)",
    "risk_from_day": "its own trigger -- needs to be behind by risk_behind after "
                     "risk_from_day, which never happens in mirror play",
    "melon_concede_threshold": "melon_contest_bonus, which is 0",
    "fert_carry": "fertilize_crops",
    "fert_harvest_day": "fertilize_crops",
    "melon_contest_bonus": "melon_concede_threshold > 0",
    "risk_behind": "risk_from_day > 0",
    "risk_shed_margin": "risk_from_day > 0",
    "repurpose_order": "repurpose_melon",
    "endgame_hour": "endgame_sweep",
    "shed_lock_aware": "superseded by shed_shared",
}


class Diverged(Exception):
    pass


def record(cfg, seed, steps):
    """Run one episode and return the agent's action stream, turn by turn."""
    inner = farmlib.make_agent(cfg)
    stream = []

    def agent(obs):
        action = inner(obs)
        stream.append(repr(action))
        return action

    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run([agent, farmlib.make_agent()])
    return stream


def diverges_from(baseline, cfg, seed, steps):
    """Replay `cfg` against the same opponent, stopping at the first difference.

    Returns the turn index where the streams part, or None if identical.
    """
    inner = farmlib.make_agent(cfg)
    state = {"turn": 0, "at": None}

    def agent(obs):
        action = inner(obs)
        i = state["turn"]
        state["turn"] = i + 1
        if i >= len(baseline) or repr(action) != baseline[i]:
            state["at"] = i
            raise Diverged
        return action

    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    try:
        env.run([agent, farmlib.make_agent()])
    except Diverged:
        pass
    return state["at"]


def audit(seeds, steps):
    base_cfg = farmlib.Config()
    defaults = dict(base_cfg.__dict__)
    unknown = [k for k in defaults if k not in PERTURB]
    if unknown:
        print(f"  !! no perturbation defined for: {', '.join(sorted(unknown))}\n")

    live, inert = {}, []
    for seed in range(seeds):
        baseline = record(base_cfg, seed, steps)
        pending = [k for k in defaults if k in PERTURB and k not in live]
        for key in pending:
            if defaults[key] == PERTURB[key]:
                continue
            cfg = farmlib.Config(**{key: PERTURB[key]})
            at = diverges_from(baseline, cfg, seed, steps)
            if at is not None:
                live[key] = (seed, at)
        inert = [k for k in defaults if k in PERTURB and k not in live]
        print(f"  seed {seed}: {len(live)} live, {len(inert)} still inert")

    return live, inert, defaults


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--steps", type=int, default=720)
    args = ap.parse_args()

    print(f"=== knob liveness, {args.seeds} seed(s), {args.steps} steps ===\n")
    live, inert, defaults = audit(args.seeds, args.steps)

    print(f"\n--- LIVE ({len(live)}) — turn at which behaviour first differs ---")
    for key in sorted(live, key=lambda k: live[k][1]):
        seed, at = live[key]
        print(f"  {key:26} turn {at:>4}  (day {at // 24}) "
              f"{defaults[key]!r} -> {PERTURB[key]!r}")

    print(f"\n--- INERT ({len(inert)}) — not one action changed ---")
    for key in sorted(inert):
        why = GATED_BY.get(key)
        tag = f"gated by {why}" if why else "** UNEXPLAINED **"
        print(f"  {key:26} {defaults[key]!r} -> {PERTURB[key]!r:22} {tag}")

    unexplained = [k for k in inert if k not in GATED_BY]
    if unexplained:
        print(f"\n{len(unexplained)} knob(s) inert with no gate to explain it: "
              f"{', '.join(sorted(unexplained))}")
        print("Each is either disconnected or its perturbation was too small to bite.")
    return len(unexplained)


if __name__ == "__main__":
    raise SystemExit(main())
