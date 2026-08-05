"""A2: what does one unit of output actually cost in worker-turns?

A1 established how much money the market will absorb. This module asks whether
we can produce enough to reach those limits, and identifies which resource
actually binds: land, labour, shed capacity, or market depth.

This is an analytic model of the rules in kaggriculture.py, not a simulation.
Where it makes a scheduling assumption (which days to water, when to harvest)
the assumption is stated. Yields are cross-checked against the interpreter's own
CROPS/ANIMALS tables and the README's published max-yield figures.

Run:  python -m analysis.labour
"""

from kaggle_environments.envs.kaggriculture.kaggriculture import ANIMALS, CROPS

from analysis.market import pool

TURNS_PER_DAY = 24
SEASON_DAYS = 30

# Average realised prices from A1 (analysis/market.py), for products we expect
# to sell in volume. Premium products are priced at their shallow-pool average
# because you cannot sell many before the floor.
PRICES = {
    "WHEAT": 17.6,
    "CARROT": 12.7,
    "TOMATO": 21.0,
    "STRAWBERRY": 61.4,
    "MELON": 167.6,
    "EGG": 34.6,
    "MILK": 81.3,
    "WOOL": 134.4,
    "FERTILIZER": 50.8,
}


def water_schedule(max_yield_day):
    """Days on which a one-time crop must be watered, cheapest schedule.

    Two rules interact:
      - Survival: two consecutive unwatered end-of-days turns the plant into a
        weed, and a fresh seed starts at consecutive_unwatered = 1, so the
        planting day itself must be watered.
      - Bonus: watering on days [ceil(max_yield_day/2), max_yield_day] adds one
        unit each. Outside that window watering buys nothing but survival.

    So: water day 0, coast on alternate days until the window opens, then water
    every day inside it.
    """
    window_start = (max_yield_day + 1) // 2
    days = {0}
    day = 0
    while day + 2 < window_start:          # alternate-day survival watering
        day += 2
        days.add(day)
    days.update(range(window_start, max_yield_day + 1))
    return sorted(days)


def crop_profile(name):
    c = CROPS[name]
    if c["ongoing"]:
        return ongoing_crop_profile(name)

    max_day = c["max_yield_day"]
    waters = water_schedule(max_day)
    window_start = (max_day + 1) // 2
    bonus_days = max_day - window_start + 1

    # Base 1 unit, plus one per watered day inside the bonus window, capped.
    units = min(c["max_yield"], 1 + bonus_days)

    # Watering past the point the cap is reached is wasted, so trim.
    surplus = (1 + bonus_days) - units
    if surplus > 0:
        waters = waters[: len(waters) - surplus]
        max_day -= surplus

    actions = 1 + len(waters) + 1          # PLANT + waters + HARVEST
    tile_days = max_day + 1
    return {
        "name": name,
        "units": units,
        "product": name,
        "actions": actions,
        "tile_days": tile_days,
        "seed_cost": c["seed"],
    }


def ongoing_crop_profile(name):
    """Tomato and strawberry: fixed number of scheduled yields, then decay."""
    c = CROPS[name]
    first = c["first_yield_day"]
    interval = max(1, c["interval"])
    units = c["max_yield"]
    last_day = first + interval * (units - 1)

    # Must stay watered the whole life; alternate days suffice for survival and
    # watering buys no bonus for ongoing crops unless also fertilized.
    waters = 1 + last_day // 2
    actions = 1 + waters + units           # PLANT + waters + one HARVEST each
    return {
        "name": name,
        "units": units,
        "product": name,
        "actions": actions,
        "tile_days": last_day + 1,
        "seed_cost": c["seed"],
    }


def animal_profile(name, care=True):
    """Steady-state daily cost and output for one animal.

    CARE banks +1 per fed-and-cared day and pays the whole bank out on the next
    scheduled production. For a goose (interval 1) production is daily, so the
    bank never exceeds 1 and CARE is worth exactly +1 egg/day for +1 action/day.
    For slower animals the bank accumulates across the interval, so CARE is
    worth more per action.
    """
    a = ANIMALS[name]
    interval = max(1, a["interval"])

    # Per interval: base 1, plus the bank accrued over `interval` cared days.
    per_interval = 1 + (interval if care else 0)
    per_interval = min(per_interval, a["max_held"])

    # Daily actions: FEED always; CARE optionally; HARVEST once per interval;
    # COLLECT_FERTILIZER once a day (every animal emits 1/day, free).
    daily_actions = 1 + (1 if care else 0) + (1 / interval) + 1

    return {
        "name": name,
        "product": a["product"],
        "cost": a["cost"],
        "structure_actions": 2,            # BUILD_COOP/PASTURE + PLACE
        "first_yield_day": a["first_yield_day"],
        "product_per_day": per_interval / interval,
        "fertilizer_per_day": 1.0,
        "daily_actions": daily_actions,
        "wheat_per_day": 1.0,
    }


def main():
    print("=== Crops: cost per unit produced ===")
    print("  'pool' = how many of these plants exhaust the product's entire season")
    print("  market depth (A1). Below that count, $/action is real; above it the")
    print("  marginal plant earns the $1 floor.\n")
    header = (
        f"{'crop':<11} {'units':>6} {'actions':>8} {'tile-days':>10}"
        f" {'act/unit':>9} {'$/action':>9} {'pool':>7}"
    )
    print(header)
    print("-" * len(header))
    for name in CROPS:
        p = crop_profile(name)
        revenue = p["units"] * PRICES[p["product"]] - p["seed_cost"]
        per_action = revenue / p["actions"]
        depth_units, _ = pool(p["product"])
        plants = depth_units / p["units"]
        plants_s = "inf" if depth_units >= 19999 else f"{plants:.0f}"
        print(
            f"{name:<11} {p['units']:>6} {p['actions']:>8} {p['tile_days']:>10}"
            f" {p['actions'] / p['units']:>9.2f} {per_action:>9.2f} {plants_s:>7}"
        )

    print("\n=== Animals: steady-state daily economics ===")
    print("  'pool' = animal-days of production before the product floors.\n")
    header = (
        f"{'animal':<8} {'prod/day':>9} {'fert/day':>9} {'act/day':>8}"
        f" {'$/day':>8} {'$/action':>9} {'pool':>7}"
    )
    print(header)
    print("-" * len(header))
    for name in ANIMALS:
        a = animal_profile(name, care=True)
        gross = (
            a["product_per_day"] * PRICES[a["product"]]
            + a["fertilizer_per_day"] * PRICES["FERTILIZER"]
            - a["wheat_per_day"] * PRICES["WHEAT"]     # feed, valued at market
        )
        per_action = gross / a["daily_actions"]
        depth_units, _ = pool(a["product"])
        days = depth_units / a["product_per_day"]
        days_s = "inf" if depth_units >= 19999 else f"{days:.0f}"
        print(
            f"{name:<8} {a['product_per_day']:>9.2f} {a['fertilizer_per_day']:>9.2f}"
            f" {a['daily_actions']:>8.2f} {gross:>8.2f} {per_action:>9.2f} {days_s:>7}"
        )

    fert_units, _ = pool("FERTILIZER")
    print("\n  Animal $/day is net of one wheat/day of feed valued at market.")
    print(f"  Fertilizer is free output but the pool is {fert_units} units for the whole")
    print(f"  game, shared: {fert_units // SEASON_DAYS} animals exhaust it in one season.")
    print("  Above that, drop COLLECT_FERTILIZER and animal $/action falls accordingly.\n")

    print("=== Which constraint binds? ===")
    for hands in (0, 4, 8, 12):
        worker_turns = TURNS_PER_DAY * (1 + hands)
        hire_cost = sum(fib(n) for n in range(hands))
        # A goose is the densest per-action use of labour; see rows above.
        goose = animal_profile("GOOSE")
        # Reserve labour for the wheat that feeds them.
        wheat = crop_profile("WHEAT")
        wheat_per_tile_day = wheat["units"] / wheat["tile_days"]
        wheat_actions_per_unit = wheat["actions"] / wheat["units"]

        # Each goose needs daily_actions + enough wheat labour to feed itself.
        actions_per_goose = goose["daily_actions"] + wheat_actions_per_unit
        max_by_labour = worker_turns / actions_per_goose
        # Land: one tile per coop, plus tiles growing its feed.
        tiles_per_goose = 1 + 1 / wheat_per_tile_day
        max_by_land_1q = 25 / tiles_per_goose
        max_by_land_4q = 100 / tiles_per_goose

        print(
            f"  {hands:>2} hands ({worker_turns:>3} worker-turns/day, ${hire_cost:>3}/day): "
            f"labour supports {max_by_labour:>5.1f} geese | "
            f"1 quadrant fits {max_by_land_1q:>4.1f} | 4 quadrants fit {max_by_land_4q:>5.1f}"
        )

    print("\n  Shed cap is 100 non-seed items with overflow discarded, so daily")
    print("  production above ~100 units must be sold the same day it lands.")


def fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


if __name__ == "__main__":
    main()
