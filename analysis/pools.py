"""A4: the contested pools -- melon and fertilizer -- as two-player games.

A3 drained every finite pool to near its cap assuming nobody else was selling.
That is the assumption most likely to be wrong, because melon and fertilizer are
the two products the town does not meaningfully refill: whatever the opponent
takes is gone.

This module replays the interpreter's actual lockstep settlement for two
simultaneous sellers, builds a payoff matrix over commitment levels, and solves
the resulting zero-sum game for its maximin equilibrium.

Payoffs are stated as (my revenue - their revenue), not my revenue alone. The
ladder scores win/loss only, so the difference is what the game is actually
about, and stating it that way makes the sub-game exactly zero-sum.

Run:  python -m analysis.pools
"""

import numpy as np
from scipy.optimize import linprog

from kaggle_environments.envs.kaggriculture.kaggriculture import (
    ANIMALS,
    MARKET_I0,
    market_price,
)

from analysis.labour import PRICES, animal_profile, crop_profile

PRODUCTIVE_DAYS = 24


def race(q1, q2, product, head_start=0):
    """Both players sell into one inventory. Returns (revenue1, revenue2).

    Mirrors `_process_market`: each round quotes *both* players at the same
    pre-commit inventory, then commits both, and a unit sold at the $1 floor
    does not add supply. `head_start` lets player 1 sell that many units before
    player 2's crop is ready -- melon needs 10 days to first yield, so whoever
    plants first sells into an untouched curve.
    """
    inv = MARKET_I0
    rev = [0.0, 0.0]
    rem = [q1, q2]

    for _ in range(min(head_start, q1)):
        p = market_price(product, inv, None)
        rev[0] += p
        rem[0] -= 1
        if p > 1:
            inv += 1

    while rem[0] > 0 or rem[1] > 0:
        price = market_price(product, inv, None)
        gain = 0
        for i in (0, 1):
            if rem[i] > 0:
                rev[i] += price
                rem[i] -= 1
                if price > 1:
                    gain += 1
        inv += gain
    return rev[0], rev[1]


def solve_zero_sum(matrix):
    """Maximin mixed strategy for the row player of a zero-sum game.

    Standard LP form: maximise v subject to (column payoffs) >= v for every
    opponent pure strategy, and probabilities summing to one.
    """
    m, k = matrix.shape
    # Variables: [p_1..p_m, v]. Minimise -v.
    c = np.zeros(m + 1)
    c[-1] = -1

    # For each opponent column j:  v - sum_i p_i * A[i][j] <= 0
    A_ub = np.zeros((k, m + 1))
    for j in range(k):
        A_ub[j, :m] = -matrix[:, j]
        A_ub[j, m] = 1
    b_ub = np.zeros(k)

    A_eq = np.zeros((1, m + 1))
    A_eq[0, :m] = 1
    b_eq = np.array([1.0])

    bounds = [(0, 1)] * m + [(None, None)]
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    return res.x[:m], res.x[m]


def alternative_value_per_action():
    """What a worker-turn earns in the *uncontested* part of the game.

    Geese selling eggs only -- fertilizer is excluded because it is itself one
    of the contested pools, so counting it here would double-count.
    """
    a = animal_profile("GOOSE", care=True)
    wheat = crop_profile("WHEAT")
    # Feeding one goose costs one wheat/day, which costs labour to grow.
    wheat_actions = wheat["actions"] / wheat["units"]
    actions = a["daily_actions"] - 1 + wheat_actions      # drop COLLECT_FERTILIZER
    gross = a["product_per_day"] * PRICES["EGG"]
    return gross / actions


def melon_game(tile_options, head_start=0):
    """Payoff matrix over melon tile commitments."""
    p = crop_profile("MELON")
    units_per_tile = p["units"] * PRODUCTIVE_DAYS / p["tile_days"]
    actions_per_tile = p["actions"] * PRODUCTIVE_DAYS / p["tile_days"]
    alt = alternative_value_per_action()

    n = len(tile_options)
    matrix = np.zeros((n, n))
    for i, m1 in enumerate(tile_options):
        for j, m2 in enumerate(tile_options):
            r1, r2 = race(
                int(units_per_tile * m1), int(units_per_tile * m2), "MELON", head_start
            )
            # Tiles not in melon earn the uncontested rate with their labour.
            r1 += 0  # melon labour is spent; opportunity cost applied below
            opp1 = actions_per_tile * m1 * alt
            opp2 = actions_per_tile * m2 * alt
            seed = p["seed_cost"] * PRODUCTIVE_DAYS / p["tile_days"]
            matrix[i, j] = (r1 - opp1 - seed * m1) - (r2 - opp2 - seed * m2)
    return matrix


def fertilizer_game(animal_options):
    """Payoff matrix over animal counts, scored on fertilizer only.

    Animals earn their product regardless; what is contested is the 493-unit
    fertilizer pool, which every animal fills at 1/day for free. The marginal
    action is COLLECT_FERTILIZER, so that is what is priced here.
    """
    n = len(animal_options)
    matrix = np.zeros((n, n))
    for i, a1 in enumerate(animal_options):
        for j, a2 in enumerate(animal_options):
            r1, r2 = race(a1 * PRODUCTIVE_DAYS, a2 * PRODUCTIVE_DAYS, "FERTILIZER")
            alt = alternative_value_per_action()
            # One COLLECT_FERTILIZER action per animal per day.
            cost1 = a1 * PRODUCTIVE_DAYS * alt
            cost2 = a2 * PRODUCTIVE_DAYS * alt
            matrix[i, j] = (r1 - cost1) - (r2 - cost2)
    return matrix


def report(name, options, matrix, unit):
    mix, value = solve_zero_sum(matrix)
    print(f"\n=== {name} ===")
    header = "        " + "".join(f"{o:>9}" for o in options)
    print(f"  opponent {unit}:")
    print(header)
    for i, o in enumerate(options):
        row = "".join(f"{matrix[i, j]:>9,.0f}" for j in range(len(options)))
        print(f"  {o:>5}  {row}")
    print(f"\n  equilibrium: ", end="")
    print(", ".join(f"{o} {unit} @ {w:.0%}" for o, w in zip(options, mix) if w > 0.01))
    print(f"  game value: {value:,.0f} (zero by symmetry if both play equilibrium)")
    return mix, value


def main():
    alt = alternative_value_per_action()
    print(f"Uncontested alternative (eggs): ${alt:.2f} per worker-turn")
    print("Payoffs are (my revenue - opponent revenue), net of what the same")
    print("labour would have earned in the uncontested egg engine.")

    tiles = [0, 4, 8, 11, 16, 22]
    m = melon_game(tiles)
    report("MELON: simultaneous harvest", tiles, m, "tiles")

    print("\n  --- with a 10-day head start (planted first) ---")
    p = crop_profile("MELON")
    units_per_tile = p["units"] * PRODUCTIVE_DAYS / p["tile_days"]
    solo, _ = race(int(units_per_tile * 11), int(units_per_tile * 11), "MELON", head_start=0)
    first, second = race(
        int(units_per_tile * 11), int(units_per_tile * 11), "MELON",
        head_start=int(units_per_tile * 11),
    )
    print(f"  11 tiles each, simultaneous:   ${solo:,.0f} each")
    print(f"  11 tiles each, we sell first:  ${first:,.0f} vs ${second:,.0f}"
          f"  (premium ${first - solo:,.0f})")

    animals = [0, 8, 16, 20, 28]
    f = fertilizer_game(animals)
    report("FERTILIZER: collection race", animals, f, "animals")


if __name__ == "__main__":
    main()
