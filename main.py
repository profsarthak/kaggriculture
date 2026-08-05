"""Kaggriculture baseline agent: a parallel wheat loop.

Strategy, in one sentence: hire cheap labour every morning, give every worker
its own plot in the starting quadrant, and run wheat (plant -> water -> harvest)
on all of them while selling whatever lands in the shed.

Why wheat: it is the fastest cycle in the game (first yield day 2, max yield
day 4) and the market barely punishes oversupply -- dumping 400 units past
equilibrium only moves the price from $25 to $20. Premium crops pay far more
per unit but crash to the $1 floor if you flood them, so they are a worse
first strategy than they look.

This is deliberately simple and leaves a lot on the table. See the notes at the
bottom for the obvious next moves.
"""

# Wheat: seeds cost 10, base price 25, harvestable from day 2.
# Watering on days 2-4 adds one unit each, so harvesting at age 4 yields 4
# instead of 1. Decay starts at age 5, so age 4 is the sweet spot.
HARVEST_AGE = 4

# Hands cost fib(n) each: 1, 1, 2, 3, 5, 8, 13, 21. Eight hands is $54/day,
# which is noise next to what eight extra workers earn.
HANDS_WANTED = 8

# Only the NW quadrant is unlocked at the start: x and y both run 0..4.
QUADRANT = 5


def plot_for(unit_index):
    """Give each worker its own tile so they don't fight over the same plant."""
    return unit_index % QUADRANT, (unit_index // QUADRANT) % QUADRANT


def step_toward(x, y, tx, ty):
    """One move along x first, then y. Returns None once we've arrived."""
    if x < tx:
        return "EAST"
    if x > tx:
        return "WEST"
    if y < ty:
        return "SOUTH"
    if y > ty:
        return "NORTH"
    return None


def act(unit_index, pos, tiles, day, seeds_available):
    """Decide one worker's action. Returns (action, consumed_a_seed)."""
    x, y = pos
    tx, ty = plot_for(unit_index)

    move = step_toward(x, y, tx, ty)
    if move:
        return [move], False

    tile = tiles[y][x]

    # Empty ground: plant, but only if a seed is actually free this turn.
    # Two workers issuing PLANT against one seed means neither plants.
    if tile is None:
        if seeds_available > 0:
            return ["PLANT", "WHEAT"], True
        return ["PASS"], False

    if not isinstance(tile, dict):
        return ["PASS"], False  # "LOCKED" -- nothing to do here

    kind = tile.get("kind")

    if kind == "WEED":
        return ["DIG"], False

    if kind == "PLANT":
        age = day - tile["planted_day"]
        if age >= HARVEST_AGE and tile.get("yield_units", 0) > 0:
            return ["HARVEST"], False
        if not tile.get("watered_today"):
            return ["WATER"], False
        return ["PASS"], False

    return ["PASS"], False


def agent(obs):
    me = obs["farms"][obs["player"]]
    private = obs["private"]
    tiles = me["tiles"]
    day = obs["day"]
    money = me["money"]

    units = [me["farmer"]] + list(me["hands"])
    seeds = private["seeds"].get("WHEAT", 0)

    # --- worker actions -------------------------------------------------
    actions = []
    for i, pos in enumerate(units):
        action, used_seed = act(i, pos, tiles, day, seeds)
        if used_seed:
            seeds -= 1
        actions.append(action)

    # --- market orders (max 10 per turn, processed in order) -------------
    market = []

    # Hire at the very start of the day; hands vanish each night.
    if obs["hour"] == 0:
        for _ in range(HANDS_WANTED - me["hires_today"]):
            market.append(["HIRE"])

    # Keep roughly one spare seed per worker. Buy early in the day so the
    # seed exists by the time someone is standing on empty ground.
    wanted = len(units) + 4
    have = private["seeds"].get("WHEAT", 0)
    if have < wanted and money > 200:
        affordable = min(wanted - have, int((money - 200) // 10))
        if affordable > 0:
            market.append(["BUY_SEED", "WHEAT", affordable])

    # Sell everything that made it into the shed. Harvested wheat sits in a
    # worker's inventory until the end-of-day drop, so this fires each morning.
    in_shed = private["shed"].get("WHEAT", 0)
    if in_shed > 0:
        market.append(["SELL", "WHEAT", in_shed])

    # Expand once the first quadrant is clearly paying for itself.
    if money >= 4000 and len(me["unlocked_quadrants"]) == 1:
        market.append(["BUY_LAND"])

    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[:10],
    }


# --- Where this leaves value on the table -------------------------------
# 1. It never expands past the second quadrant, and never uses the new land
#    (plot_for only addresses the 5x5 starting quadrant).
# 2. No animals. Geese pay 1 egg/day forever at base $50 and only need wheat,
#    which this agent already produces.
# 3. No fertilizer, despite animals producing it free.
# 4. It sells the whole shed in one order instead of spreading sales out to
#    avoid walking the price down.
