"""Empirical verification of A1 and A2 against the live interpreter.

A1's gate only checked that three published price points reproduce. A2 was pure
analysis -- derived from reading the rules, never run. This module drives real
episodes with scripted agents and checks that what actually happens matches what
the model predicts.

A failure here means a docs/ conclusion is wrong and must be corrected before
Phase B builds on it.

Run:  python -m analysis.verify
"""

from kaggle_environments import make

from analysis.labour import animal_profile, crop_profile, water_schedule
from analysis.market import sell_curve

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
RESULTS = []


def record(name, expected, actual, note=""):
    ok = expected == actual
    RESULTS.append((ok, name, expected, actual, note))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name}: expected {expected}, got {actual} {note}")
    return ok


def run(agent, steps):
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": 7})
    env.run([agent, "pass"])
    return env


def final_obs(env):
    return env.steps[-1][0].observation


def carried(obs, item):
    """Units of `item` held by the main farmer plus the shed."""
    inv = obs["private"]["inventories"][0].get(item, 0)
    shed = obs["private"]["shed"].get(item, 0)
    return inv + shed


# --------------------------------------------------------------------------
# A2: crop yields under the cheapest surviving watering schedule
# --------------------------------------------------------------------------

def crop_agent(crop, water_days, harvest_day):
    """Buy one seed, plant it, water on exactly `water_days`, harvest once."""
    def agent(obs):
        step, day, hour = obs["step"], obs["day"], obs["hour"]
        if step == 0:
            return {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", crop, 1]]}
        if step == 1:
            return {"farmer": ["PLANT", crop], "hands": [], "market": []}
        if day == harvest_day and hour == 3:
            return {"farmer": ["HARVEST"], "hands": [], "market": []}
        # Day 0's watering has to dodge the plant action on step 1.
        if day in water_days and hour == (2 if day == 0 else 1):
            return {"farmer": ["WATER"], "hands": [], "market": []}
        return PASS
    return agent


def verify_crop(crop):
    p = crop_profile(crop)
    harvest_day = p["tile_days"] - 1
    days = [d for d in water_schedule(harvest_day) if d <= harvest_day]
    env = run(crop_agent(crop, set(days), harvest_day), (harvest_day + 2) * 24)
    obs = final_obs(env)
    got = carried(obs, crop)
    record(
        f"{crop} yield (water {days}, harvest day {harvest_day})",
        p["units"], got,
    )
    # The plant must also have survived the alternate-day watering gaps.
    return got


# --------------------------------------------------------------------------
# A2: goose steady state -- 2 eggs/day with CARE, 1 fertilizer/day free
# --------------------------------------------------------------------------

def goose_agent(stop_day):
    """Build a coop, place a goose, then feed + care + harvest every day.

    Note the PICKUP at the top of every day. Inventory is emptied into the shed
    at each end-of-day refresh, so feed does not persist overnight -- a worker
    that skips the morning pickup silently fails its FEED and the animal starves
    after two days. This cost is not optional and A2 has to charge for it.
    """
    def agent(obs):
        step, day, hour = obs["step"], obs["day"], obs["hour"]
        market = []
        if step == 0:
            market = [["BUY_ANIMAL", "GOOSE", 1], ["BUY_PRODUCT", "WHEAT", 40]]
        if step == 1:
            return {"farmer": ["BUILD_COOP"], "hands": [], "market": market}
        if step == 2:
            return {"farmer": ["PICKUP", "GOOSE", 1], "hands": [], "market": market}
        if step == 3:
            return {"farmer": ["PLACE", "GOOSE", 1], "hands": [], "market": market}
        if day > stop_day:
            return PASS
        # Daily routine, one action per hour so nothing collides. The coop sits
        # on (4,4), which is itself shed-adjacent, so no travel is needed here.
        if hour == 0:
            return {"farmer": ["PICKUP", "WHEAT", 2], "hands": [], "market": market}
        if hour == 1:
            return {"farmer": ["FEED"], "hands": [], "market": market}
        if hour == 2:
            return {"farmer": ["CARE"], "hands": [], "market": market}
        if hour == 3:
            return {"farmer": ["HARVEST"], "hands": [], "market": market}
        if hour == 4:
            return {"farmer": ["COLLECT_FERTILIZER"], "hands": [], "market": market}
        return {"farmer": ["PASS"], "hands": [], "market": market}
    return agent


def verify_goose():
    """Check the steady-state rate, not the cumulative total.

    Totals include a startup effect the model deliberately doesn't carry: CARE
    banks +1 per fed-and-cared day and pays the whole bank out on the next
    scheduled production, so the pre-production growth days (1-3 for a goose)
    dump an extra lump on the first yield, capped at max_held. That's a one-off,
    not a rate. Differencing two run lengths isolates the rate.
    """
    a = animal_profile("GOOSE", care=True)
    early, late = 8, 12
    obs_early = final_obs(run(goose_agent(early), (early + 1) * 24))
    obs_late = final_obs(run(goose_agent(late), (late + 1) * 24))

    span = late - early
    predicted = int(a["product_per_day"] * span)
    got = carried(obs_late, "EGG") - carried(obs_early, "EGG")
    record(
        f"GOOSE steady-state eggs over {span} days (fed + cared)",
        predicted, got, f"= {a['product_per_day']}/day",
    )

    # Fertilizer starts the day after placement, one per surviving animal.
    got_fert = carried(obs_late, "FERTILIZER")
    record("GOOSE fertilizer (1/day, free)", late, got_fert, "1 per day alive")

    # And the startup lump should be real -- worth exploiting in Phase B.
    first_yield_total = carried(obs_early, "EGG")
    steady_only = int(a["product_per_day"] * (early - a["first_yield_day"] + 1))
    print(
        f"       note: first-yield care lump = +{first_yield_total - steady_only} eggs"
        f" (total {first_yield_total} vs steady-rate {steady_only})"
    )
    return got


# --------------------------------------------------------------------------
# A1: realised sale revenue must match the predicted sell curve
# --------------------------------------------------------------------------

def sell_agent(units):
    """Buy fertilizer into the shed, then dump it and measure what we're paid."""
    def agent(obs):
        step = obs["step"]
        if step == 0:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "FERTILIZER", units]]}
        if step == 1:
            return {"farmer": ["DROP"], "hands": [], "market": []}
        if step == 2:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["SELL", "FERTILIZER", units]]}
        return PASS
    return agent


def verify_sell_curve():
    """A buy then an immediate sell must net exactly zero (documented invariant).

    The interpreter quotes buys at post-buy inventory and sells at pre-sell
    inventory precisely so this round-trip is free. If it isn't, our reading of
    the price mechanism is wrong.
    """
    units = 20
    env = run(sell_agent(units), 24)
    obs = final_obs(env)
    start = 3000
    record(
        f"buy {units} then sell {units} FERTILIZER nets zero",
        start, int(obs["farms"][0]["money"]),
    )

    # And the standalone curve should be monotone non-increasing.
    curve = sell_curve("MELON")
    monotone = all(curve[i] >= curve[i + 1] for i in range(len(curve) - 1))
    record("MELON sell curve monotone non-increasing", True, monotone)


def main():
    print("=== A2: crop yields ===")
    for crop in ("WHEAT", "CARROT", "MELON"):
        verify_crop(crop)

    print("\n=== A2: animal steady state ===")
    verify_goose()

    print("\n=== A1: market mechanism ===")
    verify_sell_curve()

    failed = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("\nFAILURES -- correct docs/ before building on these:")
        for _, name, expected, actual, _note in failed:
            print(f"  {name}: expected {expected}, got {actual}")
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
