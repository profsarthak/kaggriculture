"""Shared agent core, parameterised by a strategy config.

Phase C needs several genuinely different strategies to populate a payoff
matrix, so the decision logic lives here and each strategy is a Config. main.py
picks one.

Constants are hardcoded rather than imported from kaggle_environments: the
submission sandbox runs our files from /kaggle_simulations/agent/ and we should
not assume the environment internals are importable there.

Everything here traces to a Phase A finding; see docs/.
"""

import math

# --- environment constants (docs/02-labour.md) ---------------------------
# harvest_day is the age at which yield is maxed under the cheapest surviving
# watering schedule; window is the inclusive age range where watering adds yield.
CROP_INFO = {
    "WHEAT":      {"seed": 10, "harvest_day": 4,  "window": (2, 4),  "ongoing": False},
    "CARROT":     {"seed": 20, "harvest_day": 3,  "window": (2, 3),  "ongoing": False},
    "MELON":      {"seed": 80, "harvest_day": 10, "window": (6, 10), "ongoing": False},
    "TOMATO":     {"seed": 50, "harvest_day": 8,  "window": (0, 0),  "ongoing": True},
    "STRAWBERRY": {"seed": 100, "harvest_day": 10, "window": (0, 0), "ongoing": True},
}
ANIMAL_INFO = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "product": "WOOL"},
}
LAND_PRICES = [1000, 2000, 4000]
MAX_MARKET_ORDERS = 10
SHED_CAP = 100


class Config:
    """A strategy. Defaults are the Phase A recommendation."""

    def __init__(self, **kw):
        # docs/04-pools.md: equilibrium melon commitment against a contesting
        # opponent. 11 is the monopolist's answer and floods the pool.
        self.melon_tiles = 8
        # docs/03-allocation.md: animal count at the optimum.
        self.goose_target = 16
        # docs/03-allocation.md predicted 6-9 hands; measured optimum is 8.
        # Ten scores well below (26k vs 37k) -- the extra hires are Fibonacci
        # priced and charged daily, and there is nothing profitable left for
        # them to do.
        self.hands_target = 8
        # docs/04-pools.md: past ~8 animals' worth, COLLECT_FERTILIZER earns
        # less than the egg alternative and accelerates the flood.
        self.fertilizer_quota = 8
        # docs/03-allocation.md: the third expansion costs $4,000, returns
        # $1,378. Buy two.
        self.land_purchases = 2
        # docs/04-pools.md: the melon first-mover premium is $12,790. Sell on
        # arrival; holding for a better price hands the curve to the opponent.
        self.dump_melon = True
        # Keep a cash buffer so a land purchase never strands us unable to
        # rebuy seed.
        self.cash_floor = 200
        # Fraction of worker-turns held back for movement and slack. A3 modelled
        # travel as a flat multiplier and concluded it barely mattered; with a
        # real greedy assignment over scattered tiles it matters a great deal,
        # so this is swept empirically rather than derived.
        self.labour_headroom = 0.65
        # Wheat a worker collects per shed trip. One trip should cover a day of
        # feeding for the animals that worker tends.
        self.feed_carry = 6
        # Priority points charged per step of walking when ranking tasks. 0
        # reproduces the old pure-priority ordering, which measured 71.5% of
        # worker turns spent moving.
        self.travel_weight = 8.0
        # Buy animal feed instead of growing it, trading wheat price escalation
        # for tiles and worker-turns. See plan_layout.
        self.buy_feed = False
        self.__dict__.update(kw)


# --- geometry -------------------------------------------------------------

def quadrant_of(x, y, size):
    half = size // 2
    return ("N" if y < half else "S") + ("W" if x < half else "E")


def shed_tiles(size):
    half = size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def step_toward(x, y, tx, ty):
    if x < tx:
        return "EAST"
    if x > tx:
        return "WEST"
    if y < ty:
        return "SOUTH"
    if y > ty:
        return "NORTH"
    return None


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# --- layout ---------------------------------------------------------------

# Daily action cost per active tile, from docs/02-labour.md. Used to size the
# working area against the labour budget.
TILE_COST = {"MELON": 0.91, "WHEAT": 1.20, "COOP": 4.20}


def plan_layout(farm, cfg, n_workers):
    """Assign roles to a *compact subset* of unlocked tiles.

    A3 found land is not the binding constraint -- labour is. So working every
    unlocked tile is actively wrong: it scatters tasks across 75 tiles and burns
    the labour budget on walking. Instead take only as many tiles as the workers
    can service, nearest the shed first.

    `cfg.labour_headroom` is the fraction of worker-turns reserved for movement
    and slack. It is the single most sensitive knob in the agent.
    """
    size = len(farm["tiles"])
    unlocked = set(farm["unlocked_quadrants"])
    centre = (size / 2, size / 2)

    tiles = [
        (x, y)
        for y in range(size)
        for x in range(size)
        if quadrant_of(x, y, size) in unlocked
    ]
    tiles.sort(key=lambda t: (abs(t[0] - centre[0]) + abs(t[1] - centre[1]), t))

    budget = 24 * n_workers * (1 - cfg.labour_headroom)

    # Size the flock against the wheat needed to feed it, and only then spend
    # what is left on more wheat.
    #
    # Filling melon, then every coop, then wheat with the remainder is a trap:
    # when the budget is tight, wheat gets zero tiles, the animals starve and
    # there is no early income either. That failure is silent and total -- it
    # scored ~1,283 (below the $3,000 starting bank) with zero variance across
    # seeds, because it fails the same way every time.
    melon = min(cfg.melon_tiles, len(tiles))
    remaining = budget - melon * TILE_COST["MELON"]

    # One goose eats 1 wheat/day; wheat yields 0.8/tile/day, so a coop needs
    # ~1.25 wheat tiles behind it. Keep a 2:1 ratio for margin.
    #
    # Buying feed instead frees both the tiles and the labour behind them. A3's
    # LP said grow it -- but the LP priced land, and the real constraint turned
    # out to be worker-turns spent walking between scattered crop tiles. An
    # animal packs 4 actions/day onto one tile; a wheat tile spreads 1.2
    # actions/day across many. Whether the wheat price escalation is worth that
    # density is an empirical question, so it is a switch.
    wheat_per_coop = 0 if cfg.buy_feed else 2
    per_coop = TILE_COST["COOP"] + wheat_per_coop * TILE_COST["WHEAT"]
    coops = max(0, min(cfg.goose_target, int(remaining // per_coop)))
    remaining -= coops * per_coop

    wheat = wheat_per_coop * coops + max(0, int(remaining // TILE_COST["WHEAT"]))

    roles = {}
    quota = [("MELON", melon), ("COOP", coops), ("WHEAT", wheat)]
    it = iter(tiles)
    for role, count in quota:
        for _ in range(count):
            t = next(it, None)
            if t is None:
                return roles
            roles[t] = role
    return roles


# --- task generation ------------------------------------------------------

# Higher runs first. Starvation and weeding are irreversible, so they outrank
# everything that merely earns money.
PRIORITY = {
    "FEED": 100,
    "FETCH_WHEAT": 97,
    "WATER_URGENT": 95,
    "HARVEST": 80,
    "FETCH": 78,
    "PLACE": 75,
    # CARE banks +1 egg/day per goose for one action -- worth about as much as
    # the harvest it feeds. At its old priority (below PLANT) it fired 3 times
    # in an entire episode.
    "CARE": 72,
    "WATER_BONUS": 70,
    "PLANT": 60,
    "BUILD": 55,
    "DIG": 50,
    "FERT": 30,
}




def gather_tasks(farm, private, roles, day, cfg, fert_budget, build_budget):
    """One task per tile that wants attention, with a priority."""
    tasks = []
    tiles = farm["tiles"]
    size = len(tiles)
    seeds = dict(private["seeds"])
    shed = private["shed"]

    # PLACE takes the animal from the acting worker's *inventory*, not from the
    # shed, so a purchased goose sits in storage forever unless someone walks to
    # the shed and picks it up. Emit explicit fetch tasks for that.
    empty_coops = sum(
        1
        for (x, y), role in roles.items()
        if isinstance(tiles[y][x], dict)
        and tiles[y][x].get("kind") in ("COOP", "PASTURE")
        and tiles[y][x].get("animal") is None
    )
    fetchable = min(empty_coops, shed.get("GOOSE", 0))
    for pos in sorted(shed_tiles(size))[:fetchable]:
        tasks.append((PRIORITY["FETCH"], pos, ["PICKUP", "GOOSE", 1], "FETCH_GOOSE"))

    # Same problem for feed, and it is the dangerous one: inventories empty into
    # the shed overnight, so every worker starts each day with no wheat and a
    # FEED it cannot perform fails silently. Hires are market orders settled
    # *after* player actions, so hands do not even exist at hour 0 -- this has
    # to be a standing task, not a start-of-day special case.
    animals = sum(
        1
        for row in tiles
        for t in row
        if isinstance(t, dict) and t.get("animal")
    )
    if animals and shed.get("WHEAT", 0) > 0:
        for pos in sorted(shed_tiles(size)):
            tasks.append(
                (PRIORITY["FETCH_WHEAT"], pos, ["PICKUP", "WHEAT", cfg.feed_carry], "FETCH_WHEAT")
            )

    for (x, y), role in roles.items():
        tile = tiles[y][x]

        if tile is None:
            if role == "COOP":
                # Only build what we can actually stock. An empty coop is a
                # wasted build action and a tile taken out of production.
                if build_budget > 0:
                    tasks.append((PRIORITY["BUILD"], (x, y), ["BUILD_COOP"], None))
                    build_budget -= 1
            else:
                crop = role if role in CROP_INFO else "WHEAT"
                if seeds.get(crop, 0) > 0:
                    tasks.append((PRIORITY["PLANT"], (x, y), ["PLANT", crop], crop))
            continue

        if not isinstance(tile, dict):
            continue

        kind = tile.get("kind")

        if kind == "WEED":
            tasks.append((PRIORITY["DIG"], (x, y), ["DIG"], None))
            continue

        if kind == "PLANT":
            crop = tile["crop"]
            info = CROP_INFO.get(crop, CROP_INFO["WHEAT"])
            age = day - tile["planted_day"]
            if age >= info["harvest_day"] and tile.get("yield_units", 0) > 0:
                tasks.append((PRIORITY["HARVEST"], (x, y), ["HARVEST"], None))
            elif not tile.get("watered_today"):
                # Two consecutive misses turns it into a weed.
                urgent = tile.get("consecutive_unwatered", 0) >= 1
                lo, hi = info["window"]
                useful = info["ongoing"] or lo <= age <= hi
                if urgent or useful:
                    key = "WATER_URGENT" if urgent else "WATER_BONUS"
                    tasks.append((PRIORITY[key], (x, y), ["WATER"], None))
            continue

        if kind in ("COOP", "PASTURE"):
            animal = tile.get("animal")
            if animal is None:
                # Only worth walking here if some worker is actually carrying a
                # goose; `assign` rations that against the workers' inventories.
                tasks.append((PRIORITY["PLACE"], (x, y), ["PLACE", "GOOSE", 1], "GOOSE"))
                continue
            if not tile.get("fed_today"):
                tasks.append((PRIORITY["FEED"], (x, y), ["FEED"], "FEED"))
            if tile.get("yield_units", 0) > 0:
                tasks.append((PRIORITY["HARVEST"], (x, y), ["HARVEST"], None))
            if not tile.get("cared_today"):
                # CARE banks a bonus paid on the next yield, and the bank
                # accrued during growth pays out in a lump (docs/02-labour.md).
                tasks.append((PRIORITY["CARE"], (x, y), ["CARE"], None))
            if tile.get("fertilizer_available") and fert_budget > 0:
                tasks.append((PRIORITY["FERT"], (x, y), ["COLLECT_FERTILIZER"], "FERT"))

    tasks.sort(key=lambda t: -t[0])
    return tasks


# --- worker assignment ----------------------------------------------------

def assign(units, tasks, carried_wheat, carried_geese, seeds, shed_geese,
           cfg_feed_carry=6, travel_weight=5.0):
    """Greedy: highest-priority task goes to whichever free worker is nearest.

    Also rations the scarce things a task can consume -- seeds, carried wheat,
    carried geese -- so two workers never both act against one unit of it. A
    worker can only PLACE an animal it is personally carrying, and can only FEED
    with wheat it is personally carrying, so both are tracked per worker.
    """
    actions = [None] * len(units)
    taken = set()
    seeds = dict(seeds)
    wheat = list(carried_wheat)
    geese = list(carried_geese)
    in_shed = shed_geese

    # Order tasks by value *net of the walk*, not by raw priority.
    #
    # Ranking by priority alone means the most urgent task in the world gets the
    # nearest free worker, then the next, and so on -- which scatters everyone
    # across the board. Measured: 71.5% of worker turns spent moving, 23.2%
    # working (analysis/diagnose.py). Charging each task the distance to its
    # closest available worker keeps work local without hard territory, which
    # was tried (angular wedges) and made travel worse: a wedge is long and thin,
    # so its owner is usually at the wrong end of it.
    def nearest_free(pos):
        best = None
        for i, upos in enumerate(units):
            if actions[i] is not None:
                continue
            d = distance(upos, pos)
            if best is None or d < best:
                best = d
        return best if best is not None else 0

    tasks = sorted(
        tasks,
        key=lambda t: -(t[0] - travel_weight * nearest_free(t[1])),
    )

    for _priority, pos, op, need in tasks:
        if pos in taken:
            continue

        def feasible(i):
            if actions[i] is not None:
                return False
            if need == "FEED" and wheat[i] <= 0:
                return False       # no feed on this worker
            if need == "GOOSE" and geese[i] <= 0:
                return False       # not carrying an animal to place
            if need == "FETCH_GOOSE" and geese[i] > 0:
                return False       # already carrying one
            if need == "FETCH_WHEAT" and wheat[i] > 0:
                return False       # already stocked for today
            return True

        best, best_d = None, None
        for i, upos in enumerate(units):
            if not feasible(i):
                continue
            d = distance(upos, pos)
            if best_d is None or d < best_d:
                best, best_d = i, d
        if best is None:
            continue

        if need in CROP_INFO:
            if seeds.get(need, 0) <= 0:
                continue
            seeds[need] -= 1
        elif need == "FETCH_GOOSE":
            if in_shed <= 0:
                continue
            in_shed -= 1

        taken.add(pos)
        ux, uy = units[best]
        move = step_toward(ux, uy, *pos)
        if move:
            actions[best] = [move]
        else:
            actions[best] = op
            # Only charge the consumable once the action actually fires.
            if need == "FEED":
                wheat[best] -= 1
            elif need == "GOOSE":
                geese[best] -= 1
            elif need == "FETCH_GOOSE":
                geese[best] += 1
            elif need == "FETCH_WHEAT":
                wheat[best] += cfg_feed_carry

    return [a if a else ["PASS"] for a in actions]


# --- market ---------------------------------------------------------------

def market_orders(obs, farm, private, roles, cfg, animals_alive):
    orders = []
    money = farm["money"]
    hour = obs["hour"]
    shed = private["shed"]

    # Hire at the top of the day; hands vanish overnight. Each hire is its own
    # order and the per-turn cap is 10, so this has to own hour 0 alone.
    if hour == 0:
        for _ in range(max(0, cfg.hands_target - farm["hires_today"])):
            orders.append(["HIRE"])
        return orders[:MAX_MARKET_ORDERS]

    # Melon sells the instant it lands: the first-mover premium is $12,790 and
    # holding stock is how you lose it (docs/04-pools.md).
    if cfg.dump_melon and shed.get("MELON", 0) > 0:
        orders.append(["SELL", "MELON", shed["MELON"]])

    # Eggs and wheat are unbounded sinks (docs/01-market.md) -- no reason to
    # meter them.
    for item in ("EGG", "FERTILIZER", "MILK", "WOOL"):
        if shed.get(item, 0) > 0:
            orders.append(["SELL", item, shed[item]])

    # Keep enough wheat banked to feed every animal for two days.
    feed_reserve = animals_alive * 2
    banked = shed.get("WHEAT", 0)
    if cfg.buy_feed:
        short = feed_reserve + animals_alive - banked
        if short > 0 and money > cfg.cash_floor + short * 60:
            orders.append(["BUY_PRODUCT", "WHEAT", short])
    elif banked - feed_reserve > 0:
        orders.append(["SELL", "WHEAT", banked - feed_reserve])

    # Seed buying. Melon first -- it is time-critical and the season only fits
    # two cycles.
    wanted = {}
    for role in roles.values():
        crop = role if role in CROP_INFO else None
        if crop:
            wanted[crop] = wanted.get(crop, 0) + 1
    for crop in ("MELON", "WHEAT"):
        need = min(wanted.get(crop, 0), 12) - private["seeds"].get(crop, 0)
        cost = CROP_INFO[crop]["seed"]
        if need > 0 and money > cfg.cash_floor + need * cost:
            orders.append(["BUY_SEED", crop, need])

    # Livestock, once the engine can afford it.
    coops_empty = sum(
        1
        for (x, y), role in roles.items()
        if role == "COOP"
        and isinstance(farm["tiles"][y][x], dict)
        and farm["tiles"][y][x].get("animal") is None
    )
    want_geese = min(coops_empty, cfg.goose_target - animals_alive)
    held = shed.get("GOOSE", 0)
    if want_geese > held and money > 1500:
        affordable = int((money - 1200) // ANIMAL_INFO["GOOSE"]["cost"])
        n = min(want_geese - held, affordable)
        if n > 0:
            orders.append(["BUY_ANIMAL", "GOOSE", n])

    # Expansion. Two quadrants only (docs/03-allocation.md).
    bought = len(farm["unlocked_quadrants"]) - 1
    if bought < cfg.land_purchases:
        price = LAND_PRICES[bought]
        if money > price + 1500:
            orders.append(["BUY_LAND"])

    return orders[:MAX_MARKET_ORDERS]


# --- entry point ----------------------------------------------------------

def make_agent(cfg=None):
    cfg = cfg or Config()

    def agent(obs):
        farm = obs["farms"][obs["player"]]
        private = obs["private"]
        day, hour = obs["day"], obs["hour"]
        size = len(farm["tiles"])

        units = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]
        # Size the working area to the workforce we expect to have, not to the
        # skeleton crew present before the day's hires land.
        roles = plan_layout(farm, cfg, max(len(units), cfg.hands_target + 1))

        animals_alive = sum(
            1
            for row in farm["tiles"]
            for t in row
            if isinstance(t, dict) and t.get("animal")
        )
        structures = sum(
            1
            for row in farm["tiles"]
            for t in row
            if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE")
        )
        # Geese we hold or could buy right now bound how many coops are worth
        # building; anything beyond that stands empty.
        stockable = (
            private["shed"].get("GOOSE", 0)
            + sum(inv.get("GOOSE", 0) for inv in inventories)
            + int(max(0, farm["money"] - 1200) // ANIMAL_INFO["GOOSE"]["cost"])
        )
        build_budget = max(0, min(cfg.goose_target, animals_alive + stockable) - structures)

        # Feed does not survive the night -- inventories are emptied into the
        # shed at the end-of-day refresh, so a worker that skips the morning
        # pickup silently no-ops its FEED and the animal starves in two days.
        # This cost me a whole verification run (docs/02-labour.md).
        carried = [inv.get("WHEAT", 0) for inv in inventories]
        carried_geese = [inv.get("GOOSE", 0) for inv in inventories]
        while len(carried) < len(units):
            carried.append(0)
        while len(carried_geese) < len(units):
            carried_geese.append(0)

        fert_budget = max(0, cfg.fertilizer_quota)
        tasks = gather_tasks(farm, private, roles, day, cfg, fert_budget, build_budget)
        assigned = assign(
            units, tasks, carried, carried_geese,
            private["seeds"], private["shed"].get("GOOSE", 0), cfg.feed_carry,
            cfg.travel_weight,
        )

        return {
            "farmer": assigned[0],
            "hands": assigned[1:],
            "market": market_orders(obs, farm, private, roles, cfg, animals_alive),
        }

    return agent
