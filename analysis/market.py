"""A1: derive the market's revenue structure from the interpreter itself.

Everything here is computed by calling the live `market_price` and reading the
live `MARKET_PARAMS` / `SHOPS` tables out of the installed environment. Nothing
is hardcoded from the README, so if Kaggle patches the environment this module
reports the new numbers rather than stale ones.

The question this answers: for each product, how much money can actually be
taken out of the market over one season, and how fast does the town refill it?

Run:  python -m analysis.market
"""

from kaggle_environments.envs.kaggriculture.kaggriculture import (
    MARKET_I0,
    MARKET_PARAMS,
    PRODUCTS,
    SHOPS,
    TOWN_CENTER_DEMAND_SCHEDULE,
    TOWN_CENTER_PRODUCTS,
    market_price,
)

# Defaults from kaggriculture.json.
TURNS_PER_DAY = 24
SHOP_SELL_INTERVAL = 4
CENTER_SELL_INTERVAL = 12
SEASON_DAYS = 30


def price_at(item, inventory):
    return market_price(item, inventory, None)


def sell_curve(item, max_units=20000):
    """Replay the interpreter's sell loop and record the price of each unit.

    Mirrors `_commit_unit`: the unit is quoted at the *pre-sell* inventory, and
    inventory only grows when the price cleared above the $1 floor. That last
    detail matters -- once a product bottoms out, dumping more does not dig the
    hole deeper, so the pool recovers on town demand alone.
    """
    inv = MARKET_I0
    prices = []
    for _ in range(max_units):
        p = price_at(item, inv)
        prices.append(p)
        if p <= 1:
            break
        inv += 1
    return prices


def pool(item):
    """Units sellable above the floor, and the revenue that represents."""
    prices = sell_curve(item)
    above_floor = [p for p in prices if p > 1]
    return len(above_floor), sum(above_floor)


def town_demand_per_day(item, shops_unlocked, day):
    """Units of `item` the town removes from market inventory per day."""
    shop_ticks = TURNS_PER_DAY // SHOP_SELL_INTERVAL      # 6
    center_ticks = TURNS_PER_DAY // CENTER_SELL_INTERVAL  # 2

    per_tick = 0
    for shop in shops_unlocked:
        products = SHOPS[shop]
        if item in products:
            per_tick += 2 if len(products) == 1 else 1
    demand = per_tick * shop_ticks

    if item in TOWN_CENTER_PRODUCTS:
        mult = next(m for threshold, m in TOWN_CENTER_DEMAND_SCHEDULE if day >= threshold)
        demand += mult * center_ticks
    return demand


def season_town_demand(item, shops_unlocked):
    return sum(town_demand_per_day(item, shops_unlocked, d) for d in range(SEASON_DAYS))


def check_readme_checkpoints():
    """Hard gate: the interpreter must reproduce the README's published prices.

    The README documents P(I0-T), P(I0+T) and P(I0+2T) for every resource. If
    these disagree, our reading of the price model is wrong and every strategy
    conclusion downstream is suspect.
    """
    published = {
        # item:        (P(I0-T), P(I0+T), P(I0+2T))
        "WHEAT":      (45, 20, 19),
        "CARROT":     (42, 10, 1),
        "TOMATO":     (84, 24, 9),
        "STRAWBERRY": (204, 1, 1),
        "MELON":      (300, 1, 1),
        "EGG":        (70, 40, 39),
        "MILK":       (256, 1, 1),
        "WOOL":       (240, 1, 1),
        "FERTILIZER": (140, 60, 20),
    }
    failures = []
    for item, (below, above1, above2) in published.items():
        t = MARKET_PARAMS[item]["T"]
        got = (
            price_at(item, MARKET_I0 - t),
            price_at(item, MARKET_I0 + t),
            price_at(item, MARKET_I0 + 2 * t),
        )
        if got != (below, above1, above2):
            failures.append((item, (below, above1, above2), got))
    return failures


def main():
    failures = check_readme_checkpoints()
    print("=== A1 gate: interpreter vs README checkpoints ===")
    if failures:
        for item, expected, got in failures:
            print(f"  MISMATCH {item}: README {expected}, interpreter {got}")
        print("\nGATE FAILED -- do not trust downstream conclusions.\n")
    else:
        print(f"  all {len(MARKET_PARAMS)} resources match\n")

    all_shops = list(SHOPS)

    print("=== Sell-side depth (selling into an untouched market) ===")
    header = f"{'product':<11} {'base':>5} {'units>$1':>9} {'pool $':>9} {'avg $/u':>8}"
    print(header)
    print("-" * len(header))
    rows = []
    for item in PRODUCTS:
        units, revenue = pool(item)
        base = MARKET_PARAMS[item]["base"]
        avg = revenue / units if units else 0
        rows.append((item, base, units, revenue, avg))
        capped = "+" if units >= 19999 else ""
        print(f"{item:<11} {base:>5} {units:>8}{capped} {revenue:>9,} {avg:>8.1f}")

    print("\n  '+' = never reached the $1 floor within the search bound;")
    print("  treat those as unbounded income streams.\n")

    print("=== Season town demand (units drained, = pool regeneration) ===")
    header = f"{'product':<11} {'no shops':>9} {'all shops':>10} {'per day, all':>13}"
    print(header)
    print("-" * len(header))
    for item in PRODUCTS:
        none_ = season_town_demand(item, [])
        all_ = season_town_demand(item, all_shops)
        per_day = town_demand_per_day(item, all_shops, SEASON_DAYS - 1)
        print(f"{item:<11} {none_:>9,} {all_:>10,} {per_day:>13}")

    print("\n=== Contested pools (no shop demand at all) ===")
    for item in PRODUCTS:
        if season_town_demand(item, all_shops) == season_town_demand(item, []):
            units, revenue = pool(item)
            print(f"  {item}: no shop demand -- {units} units / ${revenue:,} for the whole season, shared")


if __name__ == "__main__":
    main()
