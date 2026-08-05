"""A3: the allocation LP -- how should the farm be divided?

Maximises season revenue over tiles-per-crop and animal counts, subject to land,
labour, market depth, the shed cap, and the wheat balance that feeds the animals.

The revenue curve is concave (each extra unit sold fetches less), so it is
represented as piecewise-linear segments and the LP fills the high-price
segments first without needing integer variables. Wheat *purchase* cost is
convex increasing for the same reason and is segmented the same way.

Movement is modelled as a multiplier on every action cost. A2 assumed workers
are co-located with what they tend, which is true only for the handful of tiles
next to the shed; the real overhead is unknown, so `main` sweeps it rather than
picking a number.

Run:  python -m analysis.allocate
"""

import numpy as np
from scipy.optimize import linprog

from kaggle_environments.envs.kaggriculture.kaggriculture import (
    ANIMALS,
    CROPS,
    MARKET_I0,
    market_price,
)

from analysis.labour import animal_profile, crop_profile, fib
from analysis.market import sell_curve

# The game calibrates its own market throughput `T` over a 24-day window rather
# than the full 30, on the grounds that the opening days are setup-heavy and
# yield little. Use the same horizon so our numbers are comparable to theirs.
PRODUCTIVE_DAYS = 24
SEGMENTS = 12
SHED_CAP = 100
UNBOUNDED_CAP = 4000          # sell-curve truncation for wheat and egg


def sell_segments(product):
    """(price, width) pairs approximating the concave revenue curve."""
    curve = sell_curve(product)[:UNBOUNDED_CAP]
    width = max(1, len(curve) // SEGMENTS)
    segments = []
    for start in range(0, len(curve), width):
        chunk = curve[start:start + width]
        if chunk:
            segments.append((sum(chunk) / len(chunk), len(chunk)))
    return segments


def buy_segments(product, cap=UNBOUNDED_CAP):
    """(price, width) pairs for buying, which drains inventory and raises price."""
    inv = MARKET_I0
    prices = []
    for _ in range(cap):
        inv -= 1
        prices.append(market_price(product, inv, None))
    width = max(1, len(prices) // SEGMENTS)
    segments = []
    for start in range(0, len(prices), width):
        chunk = prices[start:start + width]
        if chunk:
            segments.append((sum(chunk) / len(chunk), len(chunk)))
    return segments


def solve(land, hands, travel=1.0, verbose=False):
    """Return the revenue-maximising allocation for one (land, hands, travel)."""
    crops = list(CROPS)
    animals = list(ANIMALS)
    products = sorted({*crops, *(ANIMALS[a]["product"] for a in animals), "FERTILIZER"})

    worker_turns = 24 * (1 + hands)
    hire_cost = sum(fib(n) for n in range(hands)) * PRODUCTIVE_DAYS

    cp = {c: crop_profile(c) for c in crops}
    ap = {a: animal_profile(a, care=True) for a in animals}

    segs = {p: sell_segments(p) for p in products}
    wheat_buy = buy_segments("WHEAT")

    # ---- variable layout -------------------------------------------------
    idx, n = {}, 0
    for c in crops:
        idx[("crop", c)] = n; n += 1
    for a in animals:
        idx[("animal", a)] = n; n += 1
    for p in products:
        for k in range(len(segs[p])):
            idx[("sell", p, k)] = n; n += 1
    for k in range(len(wheat_buy)):
        idx[("buy", k)] = n; n += 1

    # ---- objective (linprog minimises, so negate) ------------------------
    obj = np.zeros(n)
    for p in products:
        for k, (price, _) in enumerate(segs[p]):
            obj[idx[("sell", p, k)]] = -price
    for k, (price, _) in enumerate(wheat_buy):
        obj[idx[("buy", k)]] = price
    for c in crops:                                   # seed cost per season
        cycles = PRODUCTIVE_DAYS / cp[c]["tile_days"]
        obj[idx[("crop", c)]] = cp[c]["seed_cost"] * cycles
    for a in animals:                                 # one-off capital
        obj[idx[("animal", a)]] = ap[a]["cost"]

    rows, rhs = [], []

    def add(coeffs, bound):
        row = np.zeros(n)
        for key, v in coeffs.items():
            row[idx[key]] = v
        rows.append(row); rhs.append(bound)

    # 1. Land: one tile per crop plot, one per animal structure.
    add({("crop", c): 1 for c in crops} | {("animal", a): 1 for a in animals}, land)

    # 2. Labour, inflated by travel overhead.
    labour = {}
    for c in crops:
        labour[("crop", c)] = travel * cp[c]["actions"] / cp[c]["tile_days"]
    for a in animals:
        labour[("animal", a)] = travel * ap[a]["daily_actions"]
    add(labour, worker_turns)

    # 3. Per-product balance: cannot sell more than we make.
    for p in products:
        coeffs = {("sell", p, k): 1 for k in range(len(segs[p]))}
        if p in CROPS:
            rate = cp[p]["units"] / cp[p]["tile_days"]
            coeffs[("crop", p)] = -PRODUCTIVE_DAYS * rate
        for a in animals:
            if ANIMALS[a]["product"] == p:
                coeffs[("animal", a)] = -PRODUCTIVE_DAYS * ap[a]["product_per_day"]
            if p == "FERTILIZER":
                coeffs[("animal", a)] = -PRODUCTIVE_DAYS * ap[a]["fertilizer_per_day"]
        if p == "WHEAT":
            # Feed comes out of the same pile, purchases go into it.
            for a in animals:
                coeffs[("animal", a)] = (
                    coeffs.get(("animal", a), 0) + PRODUCTIVE_DAYS * ap[a]["wheat_per_day"]
                )
            for k in range(len(wheat_buy)):
                coeffs[("buy", k)] = -1
        add(coeffs, 0)

    # 4. Segment widths.
    for p in products:
        for k, (_, w) in enumerate(segs[p]):
            add({("sell", p, k): 1}, w)
    for k, (_, w) in enumerate(wheat_buy):
        add({("buy", k): 1}, w)

    # 5. Shed: production that lands in a day must clear that day.
    daily = {}
    for c in crops:
        daily[("crop", c)] = cp[c]["units"] / cp[c]["tile_days"]
    for a in animals:
        daily[("animal", a)] = ap[a]["product_per_day"] + ap[a]["fertilizer_per_day"]
    add(daily, SHED_CAP)

    res = linprog(obj, A_ub=np.array(rows), b_ub=np.array(rhs), method="highs")
    if not res.success:
        return None

    x = res.x
    plan = {
        "revenue": -res.fun - hire_cost,
        "hire_cost": hire_cost,
        "tiles": {c: x[idx[("crop", c)]] for c in crops if x[idx[("crop", c)]] > 0.05},
        "animals": {a: x[idx[("animal", a)]] for a in animals if x[idx[("animal", a)]] > 0.05},
        "sold": {
            p: sum(x[idx[("sell", p, k)]] for k in range(len(segs[p])))
            for p in products
            if sum(x[idx[("sell", p, k)]] for k in range(len(segs[p]))) > 0.5
        },
        "wheat_bought": sum(x[idx[("buy", k)]] for k in range(len(wheat_buy))),
        "land_used": sum(x[idx[("crop", c)]] for c in crops)
        + sum(x[idx[("animal", a)]] for a in animals),
        "labour_used": sum(
            travel * cp[c]["actions"] / cp[c]["tile_days"] * x[idx[("crop", c)]] for c in crops
        )
        + sum(travel * ap[a]["daily_actions"] * x[idx[("animal", a)]] for a in animals),
        "worker_turns": worker_turns,
    }
    return plan


def fmt(d):
    return ", ".join(f"{k} {v:.0f}" for k, v in sorted(d.items(), key=lambda kv: -kv[1]))


def main():
    print("=== A3: optimal allocation, all four quadrants (100 tiles) ===")
    print("  Sweeping hired hands and travel overhead. 'travel' multiplies every")
    print("  action cost: 1.0 is A2's co-location assumption, 1.5 is a worker")
    print("  spending a third of its turns walking.\n")

    header = f"{'travel':>7} {'hands':>6} {'revenue':>10} {'land':>6} {'labour':>13}  allocation"
    print(header)
    print("-" * (len(header) + 20))
    for travel in (1.0, 1.25, 1.5):
        best = None
        for hands in range(0, 20):
            plan = solve(100, hands, travel)
            if plan and (best is None or plan["revenue"] > best[1]["revenue"]):
                best = (hands, plan)
        hands, p = best
        util = f"{p['labour_used']:.0f}/{p['worker_turns']}"
        alloc = fmt({**p["tiles"], **{f"{a}*": v for a, v in p["animals"].items()}})
        print(
            f"{travel:>7.2f} {hands:>6} {p['revenue']:>10,.0f}"
            f" {p['land_used']:>5.0f}  {util:>12}  {alloc}"
        )

    print("\n=== Is expanding worth it? (travel 1.25, best hands each) ===")
    print(f"{'land':>6} {'revenue':>10} {'cost to unlock':>15} {'net':>10}")
    print("-" * 45)
    unlock_cost = {25: 0, 50: 1000, 75: 3000, 100: 7000}
    for land in (25, 50, 75, 100):
        best = max(
            (solve(land, h, 1.25) for h in range(0, 20)),
            key=lambda p: p["revenue"] if p else -1e9,
        )
        net = best["revenue"] - unlock_cost[land]
        print(f"{land:>6} {best['revenue']:>10,.0f} {unlock_cost[land]:>15,} {net:>10,.0f}")

    print("\n=== What the optimum actually sells (100 tiles, travel 1.25) ===")
    best = max((solve(100, h, 1.25) for h in range(0, 20)), key=lambda p: p["revenue"])
    for p, units in sorted(best["sold"].items(), key=lambda kv: -kv[1]):
        print(f"  {p:<11} {units:>8,.0f} units")
    print(f"  wheat bought as feed: {best['wheat_bought']:,.0f} units")


if __name__ == "__main__":
    main()
