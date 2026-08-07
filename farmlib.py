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
# Days from placement to first production (docs/02-labour.md).
ANIMAL_FIRST_YIELD = {"GOOSE": 4, "COW": 8, "SHEEP": 6}
LAND_PRICES = [1000, 2000, 4000]
MAX_MARKET_ORDERS = 10
SHED_CAP = 100


class Config:
    """A strategy. Defaults are the Phase A recommendation."""

    def __init__(self, **kw):
        # A4 derived 8 against a contesting opponent, and that was right for the
        # agent which existed then. It has fallen 9 -> 7 -> 5 as the herd grew:
        # melon and livestock compete for the same layout budget, so every
        # improvement to the animals makes the marginal melon tile worse. Not a
        # smooth knob -- see docs/09-ab-testing.md.
        self.melon_tiles = 5
        # docs/03-allocation.md: animal count at the optimum.
        self.goose_target = 16
        # docs/03-allocation.md predicted 6-9; measured 8 for most of the
        # project and 9 once the flock grew. Hire cost is Fibonacci and charged
        # daily, so this stops paying quickly: 10 has repeatedly measured well
        # below. This is a ceiling -- `hire_to_demand` sets the actual crew.
        self.hands_target = 9
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
        self.labour_headroom = 0.55
        # Wheat a worker collects per shed trip. One trip should cover a day of
        # feeding for the animals that worker tends.
        # Fell 6 -> 4 -> 3 as the herd grew. Each PICKUP is one turn regardless
        # of quantity, so carrying less costs more trips -- but a worker holding
        # feed it will not use is one that skipped a fetch it needed, and with
        # more animals those fetches matter more.
        self.feed_carry = 3
        # Priority points charged per step of walking when ranking tasks. 0
        # reproduces the old pure-priority ordering, which measured 71.5% of
        # worker turns spent moving. Raised 8 -> 13 by the tuner; note that 12
        # measured -10,506 at an earlier config, so this is strongly coupled to
        # the rest and should not be moved on its own.
        self.travel_weight = 13.0
        # Buy animal feed instead of growing it, trading wheat price escalation
        # for tiles and worker-turns. See plan_layout.
        self.buy_feed = False
        # Carry routes across turns instead of re-deciding assignment globally
        # every turn. Off reproduces the old per-turn greedy, kept so the gain
        # stays measurable.
        self.route_commit = True
        # Plant carrot on general crop tiles before this day, then wheat. 0
        # disables the opening. See planting_choice.
        # Rejected: carrot loses monotonically (-3,865 at 3 days, -13,963 at
        # 12). Kept switchable so the negative result stays reproducible.
        self.carrot_until = 0
        # Pasture tiles, stocked with cows. Adding them at all was worth +11,673
        # (16/16): milk is $160 base against eggs at $50 and the field barely
        # contests it. Cows beat sheep decisively (+11,561 vs +1,037) because
        # wool's pool is shallower still.
        #
        # The count has climbed 2 -> 3 -> 5 -> 7 as throughput improved. Milk's
        # pool is only 76 units deep, but that is the *static* depth: with shops
        # unlocked the town drains ~680 milk a season, so it refills and a bigger
        # herd does not flood it the way the raw number suggests. Cows are now
        # the core of the strategy rather than a side allocation.
        self.pasture_target = 7
        self.pasture_animal = "COW"
        # Wheat tiles reserved per animal (1.25 is break-even) and a cap on
        # surplus income wheat. Both trade wheat for flock size.
        self.feed_ratio = 2.0
        self.max_extra_wheat = 999
        # Take any pending work on the tile a worker already occupies before
        # walking anywhere. Standing work costs no movement.
        self.finish_tile = True
        # Scale the daily crew to the work actually available rather than
        # hiring a fixed crew from day 0. See market_orders.
        # Measured +3,370 (20/20) against a fixed crew. The floor is
        # load-bearing: at min_hands=2 the same mechanism scores -13,293,
        # because the cash guard then strips the crew exactly when the farm is
        # being built. Trimming a couple of idle hands is worth a little;
        # arriving at day 10 with half a farm is not.
        self.hire_to_demand = True
        self.tiles_per_hand = 6
        self.min_hands = 6
        # Per-turn sale caps for shallow-pool products. Empty means dump
        # everything, which is what we did before measuring this.
        self.sale_cap = {}
        # Crops worth spending fertilizer on. Empty -- fertilising melon is a
        # measured loss (-4,861 as-is; -13,043 if we also harvest a day early,
        # -57,192 two days early). Fertilizer doubles the bonus only on days the
        # plant is *also* watered, and the cheapest surviving melon schedule
        # waters on alternate days early on, so the cap is not actually reached
        # sooner -- the cost is paid and nothing is saved. Selling it at ~$50 is
        # better. Kept switchable so the result stays reproducible.
        self.fertilize_crops = ()
        self.fert_carry = 3
        # Harvest day for fertilised crops. 0 keeps the unfertilised schedule.
        self.fert_harvest_day = 0
        # Season length, used to stop planting crops that cannot mature. 0
        # disables the check (plant right up to the final turn).
        self.season_days = 30
        # Days a new quadrant needs to repay itself before the season ends.
        self.land_lead = 8
        # Give animal structures the tiles nearest the shed, ahead of melon.
        # Rejected: -14,481, 0/12. The intuition was that animals want the good
        # ground most, needing 3-4 actions a day plus feed carried from the
        # shed, where melon needs one action per visit. Wrong -- melon is
        # time-critical in a way animals are not. Its first-mover premium is
        # $12,790 (docs/04-pools.md) and it only cycles twice a season, so days
        # lost getting to it are unrecoverable, whereas a structure is placed
        # once and then tended wherever it stands.
        self.animals_near_shed = False
        # Margin-conditioned risk -- REJECTED, kept switchable.
        #
        # The reasoning is sound: the payoff is sign(M_i - M_j), so once the
        # safe line loses with near-certainty, expected coins are free to trade
        # for variance. The lever is simply too weak. Put on the losing side of
        # a real deficit it went 0/20 both with and without risk, and made the
        # margin worse (-27,333 -> -29,861): withholding produce swings a few
        # thousand against a gap of 27,000.
        #
        # In mirror testing it is exactly neutral (50% of decisive games at
        # every setting) because we are rarely meaningfully behind ourselves.
        # A lever big enough to matter would have to change the whole late-game
        # plan, not the sell schedule.
        self.risk_from_day = 0
        self.risk_behind = 8000
        self.risk_shed_margin = 25
        # Best-respond to an opponent who concedes melon -- REJECTED, kept
        # switchable.
        #
        # A4's matrix says playing 11 against an opponent at 0 is worth
        # +$20,702. Against a genuinely conceding opponent it measures *worse*:
        # the goose-engine panel member (zero melon) goes from +45,458 to
        # +31,354 at bonus 3 and +21,389 at bonus 6.
        #
        # A4 priced a melon tile against eggs at $14.72/worker-turn. The
        # alternative is now a cow, and cows are worth far more, so the trade
        # A4 evaluated no longer exists. The table is not wrong; it is obsolete,
        # in the same way its equilibrium of 8 tiles is.
        #
        # Also note the detection itself is awkward: an opponent's melon count
        # is legitimately 0 for the first days of every game, so a naive test
        # fires spuriously before anyone has planted (visible as the mirror
        # going to -1,549 and -9,773 above).
        self.melon_contest_bonus = 0
        self.melon_concede_threshold = 0
        # Carry harvested melon to the shed at once rather than waiting for the
        # end-of-day drop -- REJECTED, kept switchable.
        #
        # SELL draws from the shed, so carried melon is unsellable until the
        # nightly drop: a melon picked at hour 5 sells the *following* morning.
        # Given A4 prices the first-mover premium at $12,790, buying that day
        # back looked worthwhile.
        #
        # It is not. Mirror margin -1,297 (CI crossing zero, 7/16) and a panel
        # worst case of -2,499. The PLACE action plus the walk costs about what
        # the earlier sale earns, and in a mirror both sides gain the day so it
        # cancels. The premium is about beating the opponent to the *pool*,
        # which is decided by planting date, not by delivery time.
        self.run_melon = False
        # Final-day sweep: run carried produce into the shed so it can be sold.
        # There is no end-of-day refresh on the last day, so anything still in
        # hand is lost -- measured at ~$6,600 a game.
        self.endgame_sweep = True
        self.endgame_hour = 8
        # Only issue shed operations from shed tiles we have actually unlocked.
        #
        # The mechanic is real and confirmed in the interpreter: line 323 returns
        # early when the worker's tile is "LOCKED", *before* DROP/PICKUP/PLACE
        # are handled. Measured 199 of 394 shed operations in one episode -- 50.5%
        # -- issued from locked tiles and silently doing nothing.
        #
        # Filtering them out nonetheless does not help: -2,153 over 32 games with
        # the interval crossing zero. Restricting to unlocked tiles collapses the
        # four parallel fetch points to one early on, since only one worker is
        # assigned per tile per turn, and the lost parallelism cancels the saved
        # walking.
        #
        # Left off, but the underlying waste is real and a better fix probably
        # exists: allow several workers to fetch from the same unlocked shed tile
        # in one turn, which would keep the parallelism without the dead trips.
        self.shed_lock_aware = False
        # Once melon can no longer mature, replant its tiles with something that
        # can, rather than leaving them bare for the last stretch of the season.
        # REJECTED: -1,392 (3/16). The farm is labour-bound, not land-bound, so
        # tiles left bare late in the season are not waste -- working them pulls
        # workers off the animals, which earn more. Bare land is the cheapest
        # thing on the board.
        self.repurpose_melon = False
        self.repurpose_order = ("CARROT", "WHEAT")
        self.__dict__.update(kw)
        # A single crop name arrives from the command line as a bare string, and
        # iterating one yields characters -- `CROP_INFO["W"]` then raises inside
        # the agent, which the harness reports as a catastrophic score rather
        # than an error. Normalise it.
        if isinstance(self.repurpose_order, str):
            self.repurpose_order = tuple(
                c.strip() for c in self.repurpose_order.split("|") if c.strip()
            )
        if isinstance(self.fertilize_crops, str):
            self.fertilize_crops = tuple(
                c.strip() for c in self.fertilize_crops.split("|")
                if c.strip() and c.strip() in CROP_INFO
            )
        if isinstance(self.sale_cap, (int, float)):
            # Convenience for sweeping: a scalar caps every shallow product.
            self.sale_cap = {p: int(self.sale_cap) for p in ("MILK", "WOOL", "CARROT", "TOMATO", "STRAWBERRY")}


# --- geometry -------------------------------------------------------------

def quadrant_of(x, y, size):
    half = size // 2
    return ("N" if y < half else "S") + ("W" if x < half else "E")


def shed_tiles(size):
    half = size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def usable_shed_tiles(farm, cfg=None):
    """Shed-adjacent tiles we can actually act from.

    The four centre tiles sit one in each quadrant, so three of them are locked
    at the start and stay locked until bought. `_apply_unit_action` returns
    early on a locked tile, so PICKUP, DROP and PLACE issued there do nothing
    at all -- no error, no warning, the turn is simply spent.

    Measured before this filter existed: 199 of 394 shed operations in a single
    episode, 50.5%, were issued from locked tiles and silently failed. Workers
    were walking to dead drop points and back.
    """
    size = len(farm["tiles"])
    if cfg is not None and not getattr(cfg, "shed_lock_aware", True):
        return shed_tiles(size)
    unlocked = set(farm.get("unlocked_quadrants") or [])
    return {
        pos for pos in shed_tiles(size)
        if quadrant_of(pos[0], pos[1], size) in unlocked
    }


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
TILE_COST = {"MELON": 0.91, "WHEAT": 1.20, "COOP": 4.20, "PASTURE": 3.70}


def tile_cost(role, cfg):
    """Daily action cost charged to a tile when sizing the farm.

    A2 derived these analytically. Measured spend per tile-day
    (analysis/tilecost.py) is quite different: melon 1.74 against a model of
    0.91, coop 2.17 against 4.20, pasture 1.81 against 3.70.

    **Do not "correct" the model to match.** Substituting the measured values
    scores -16,640. Measured spend is what the tiles *get*, not what they
    *need*, and the farm is labour-constrained: a coop wants four actions a day
    (FEED, CARE, HARVEST, COLLECT_FERTILIZER) and is receiving 2.17. Charging it
    the observed 2.17 tells the layout it can afford more animals, which makes
    the existing under-service worse.

    The model's numbers are requirements and are right to be. The gap between
    4.20 and 2.17 is a measure of how far short we fall, not an error.

    Overridable per config as `tc_<role.lower()>` so this stays testable.
    """
    return getattr(cfg, "tc_" + role.lower(), None) or TILE_COST[role]


def animal_for(structure, cfg):
    """Which animal belongs on a structure. Coops are geese by definition."""
    return "GOOSE" if structure == "COOP" else cfg.pasture_animal


def melon_target(farm, cfg, opponent=None):
    """Melon commitment, optionally best-responding to the opponent's.

    A4 solved the melon sub-game and produced a best-response table; the agent
    has never used it, playing a fixed number regardless. `verify.py` confirmed
    the opponent's board -- crop and planted_day -- is public, so the input is
    there every turn.

    Only the one case A4 shows a large gain is acted on: an opponent who
    concedes melon entirely leaves the pool uncontested, worth +$20,702 in the
    matrix. Everything else stays fixed, because the response surface is steep
    and jagged (`melon_tiles=10` has measured -17,980) and moving along it at
    runtime risks far more than the adaptation gains.
    """
    if not cfg.melon_contest_bonus or opponent is None:
        return cfg.melon_tiles
    theirs = sum(
        1
        for row in opponent.get("tiles", [])
        for t in row
        if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "MELON"
    )
    if theirs <= cfg.melon_concede_threshold:
        return cfg.melon_tiles + cfg.melon_contest_bonus
    return cfg.melon_tiles


def plan_layout(farm, cfg, n_workers, opponent=None):
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

    # Each target is honoured independently, and everything scales together when
    # the budget cannot cover them.
    #
    # The previous version spent melon's budget first and fitted coops into
    # whatever remained, which meant `melon_tiles` silently moved the flock size
    # too: one extra melon tile could cost an entire coop. That produced a
    # jagged, non-monotonic response (9 tiles +2,703, 16 tiles -6,716, all with
    # tight confidence intervals) and made single-parameter sweeps unsafe --
    # they were sampling a discontinuous function. See docs/09-ab-testing.md.
    #
    # Proportional scaling keeps each knob doing one thing and degrades smoothly
    # instead of dropping a whole coop at a threshold.
    #
    # One goose eats 1 wheat/day and wheat yields 0.8/tile/day, so a coop needs
    # ~1.25 wheat tiles behind it; 2 gives margin. Buying feed instead is a
    # measured loss (6,053 vs 30,850) -- see docs/08-field-study.md -- but stays
    # switchable so the negative result is reproducible.
    # Wheat tiles reserved behind each animal. A goose eats 1/day and wheat
    # yields 0.8/tile/day, so 1.25 is the break-even and anything above is
    # margin. Lowering it buys more animals from the same budget -- which the
    # ladder data argues for: across 31 opponent appearances, animal count
    # correlates +0.61 with final score (0 animals 31,492, 10+ animals 73,199)
    # while wheat tiles correlate -0.43. See docs/12-goose-target.md.
    wheat_per_coop = 0 if cfg.buy_feed else cfg.feed_ratio

    # Melon is honoured exactly. It is a small, strategically-chosen number
    # (A4's contested-pool equilibrium) costing ~10% of the budget, so there is
    # no reason to let it be squeezed -- and scaling it made `melon_tiles` a
    # weight rather than a count, which silently delivered 5 tiles when asked
    # for 9. The flock and its feed absorb the budget constraint instead, and
    # they scale proportionally so one extra melon tile shaves a fraction of a
    # coop rather than dropping a whole one.
    melon = max(0, min(melon_target(farm, cfg, opponent), len(tiles)))
    remaining = max(0.0, budget - melon * tile_cost("MELON", cfg))

    # Pastures are claimed before coops. Milk and wool have far higher base
    # prices than eggs and the field averages only 3.4 animals, so those pools
    # are barely contested -- but they are shallow (76 and 59 units) so this is
    # a small fixed allocation, not a scaling one (docs/01-market.md).
    per_pasture = tile_cost("PASTURE", cfg) + wheat_per_coop * tile_cost("WHEAT", cfg)
    pastures = max(0, min(cfg.pasture_target, int(remaining // per_pasture) if per_pasture else 0))
    remaining = max(0.0, remaining - pastures * per_pasture)

    per_coop = tile_cost("COOP", cfg) + wheat_per_coop * tile_cost("WHEAT", cfg)
    coop_demand = cfg.goose_target * per_coop

    if coop_demand > remaining and per_coop > 0:
        coops = int(remaining // per_coop)
        surplus = remaining - coops * per_coop
    else:
        coops = cfg.goose_target
        surplus = remaining - coop_demand

    # Feed tracks the flock we actually built, then spare budget buys income
    # wheat. Wheat is the filler because it is the only crop with unbounded
    # market depth (docs/01-market.md).
    feed_tiles = int(math.ceil(wheat_per_coop * (coops + pastures)))
    extra = max(0, int(surplus // tile_cost("WHEAT", cfg)))
    wheat = feed_tiles + min(extra, cfg.max_extra_wheat)

    # Tiles are handed out nearest-the-shed first, so this order decides who
    # gets the good ground. Animals want it most: a structure needs 3-4 actions
    # a day *and* its feed carried from the shed, where a melon tile needs one
    # action per visit and no logistics.
    roles = {}
    quota = [
        ("PASTURE", pastures), ("COOP", coops), ("MELON", melon), ("WHEAT", wheat),
    ] if cfg.animals_near_shed else [
        ("MELON", melon), ("PASTURE", pastures), ("COOP", coops), ("WHEAT", wheat),
    ]
    it = iter(tiles)
    for role, count in quota:
        for _ in range(max(0, count)):
            t = next(it, None)
            if t is None:
                return roles
            roles[t] = role
    return roles


# --- task generation ------------------------------------------------------

# Higher runs first. Starvation and weeding are irreversible, so they outrank
# everything that merely earns money.
PRIORITY = {
    # Getting carried produce into the shed before the season ends. There is no
    # end-of-day refresh on the final day, so anything still in a worker's hands
    # is simply lost -- measured at ~23 wheat, 15 fertilizer, 10 eggs and 15
    # milk per game, roughly $6,600 at late-season prices. Outranks everything:
    # on the last afternoon nothing else earns.
    "ENDGAME": 120,
    "FEED": 100,
    "FETCH_WHEAT": 97,
    "WATER_URGENT": 95,
    "HARVEST": 80,
    "FETCH": 78,
    "FETCH_FERT": 73,
    # Measured +967 (20/20) at 90 rather than 75. A structure standing empty is
    # a tile earning nothing and a bought animal idling in the shed, so placing
    # it beats almost anything else on the board.
    "PLACE": 90,
    # CARE banks +1 egg/day per goose for one action -- worth about as much as
    # the harvest it feeds. At its old priority (below PLANT) it fired 3 times
    # in an entire episode.
    # Running harvested melon to the shed so it can be sold today rather than
    # tomorrow. Only worth interrupting for because melon is the one product
    # where a day's delay is priced: A4 measured the first-mover premium at
    # $12,790, and produce otherwise reaches the shed only at the end-of-day
    # auto-drop, so a melon picked at hour 5 sells on the *following* morning.
    "RUN_MELON": 82,
    "CARE": 72,
    "FERTILIZE": 71,
    "WATER_BONUS": 70,
    "PLANT": 60,
    "BUILD": 55,
    "DIG": 50,
    "FERT": 30,
}


def prio(key, cfg):
    """Task priority, with a per-config override so the table can be swept.

    The ordering was hand-set from "irreversible things first" reasoning and
    never measured. `Config` exposes `p_<key.lower()>` for each entry.
    """
    return getattr(cfg, "p_" + key.lower(), None) or PRIORITY[key]




def planting_choice(role, day, cfg):
    """What a general-purpose crop tile should plant today.

    Carrot is the better opening: it harvests on day 3 against wheat's day 4 and
    pays 3 units at a $35 base against 4 at $25, so it turns the starting bank
    into cash faster -- which matters because the whole build-out is gated on
    early capital. The strongest opponent we have faced opened on 17 carrot
    tiles (docs/08-field-study.md).

    It cannot replace wheat, though: animals eat wheat, and carrot's market pool
    is only ~842 units against wheat's unbounded depth (docs/01-market.md). So
    it is an opening, not a crop plan -- these tiles revert to wheat once the
    flock needs feeding.
    """
    # Melon tiles are a strategic commitment, but only while melon can still
    # mature. It needs 10 days, so from roughly day 19 the tile can never
    # produce again and the static layout leaves it bare for the rest of the
    # season. Fall back to the fastest crop that still has time to finish.
    if role == "MELON":
        if not cfg.season_days or day + CROP_INFO["MELON"]["harvest_day"] <= cfg.season_days - 1:
            return "MELON"
        if not cfg.repurpose_melon:
            return "MELON"
        for crop in cfg.repurpose_order:
            if day + CROP_INFO[crop]["harvest_day"] <= cfg.season_days - 1:
                return crop
        return "MELON"
    # Everything else is the general-purpose crop role, which is *named*
    # "WHEAT". Role names and crop names share a namespace, so this cannot be
    # resolved with `role in CROP_INFO` -- that test passes for the general
    # role and silently makes the carrot branch unreachable.
    if day < cfg.carrot_until:
        return "CARROT"
    return "WHEAT"


def gather_tasks(farm, private, roles, day, cfg, fert_budget, build_budget,
                 carried_melon=0, carried_any=0, hour=0):
    """One task per tile that wants attention, with a priority."""
    tasks = []
    tiles = farm["tiles"]
    size = len(tiles)
    seeds = dict(private["seeds"])
    shed = private["shed"]

    # PLACE takes the animal from the acting worker's *inventory*, not from the
    # shed, so a purchased goose sits in storage forever unless someone walks to
    # the shed and picks it up. Emit explicit fetch tasks for that.
    empty = {"COOP": 0, "PASTURE": 0}
    for (x, y) in roles:
        tile = tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") in empty and tile.get("animal") is None:
            empty[tile["kind"]] += 1

    slots = sorted(usable_shed_tiles(farm, cfg))
    for structure, count in empty.items():
        animal = animal_for(structure, cfg)
        fetchable = min(count, shed.get(animal, 0))
        for pos in slots[:fetchable]:
            if pos in {t[1] for t in tasks}:
                continue
            tasks.append((prio("FETCH", cfg), pos, ["PICKUP", animal, 1], f"FETCH_{animal}"))

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
        for pos in sorted(usable_shed_tiles(farm, cfg)):
            tasks.append(
                (prio("FETCH_WHEAT", cfg), pos, ["PICKUP", "WHEAT", cfg.feed_carry], "FETCH_WHEAT")
            )

    # Final-day sweep. `DROP` empties the whole inventory in one action, and
    # discards only what exceeds shedCapacity -- the shed holds a handful of
    # items by this point, so nothing is at risk. Feed carried at this stage is
    # worthless anyway: there is no refresh left to feed for.
    if cfg.endgame_sweep and carried_any and cfg.season_days:
        last_day = day >= cfg.season_days - 1
        if last_day and hour >= cfg.endgame_hour:
            for pos in sorted(usable_shed_tiles(farm, cfg)):
                tasks.append((prio("ENDGAME", cfg), pos, ["DROP"], "ENDGAME"))

    # Carried melon cannot be sold -- SELL draws from the shed -- and the
    # end-of-day drop is a whole day late for the one product where timing is
    # worth $12,790. Run it in by hand.
    if cfg.run_melon and carried_melon:
        for pos in sorted(usable_shed_tiles(farm, cfg)):
            tasks.append((prio("RUN_MELON", cfg), pos, ["PLACE", "MELON", 12], "RUN_MELON"))

    # Fertilizer is produced at the animals and needed at the crops, so it has
    # to be routed through the shed the same way feed is.
    if cfg.fertilize_crops and shed.get("FERTILIZER", 0) > 0:
        for pos in sorted(usable_shed_tiles(farm, cfg)):
            tasks.append(
                (prio("FETCH_FERT", cfg), pos,
                 ["PICKUP", "FERTILIZER", cfg.fert_carry], "FETCH_FERT")
            )

    for (x, y), role in roles.items():
        tile = tiles[y][x]

        if tile is None:
            if role in ("COOP", "PASTURE"):
                # Only build what we can actually stock. An empty structure is a
                # wasted build action and a tile taken out of production.
                if build_budget > 0:
                    tasks.append((prio("BUILD", cfg), (x, y), [f"BUILD_{role}"], None))
                    build_budget -= 1
            else:
                crop = planting_choice(role, day, cfg)
                # Do not plant what cannot mature. Melon needs 10 days and wheat
                # 4, so late in the season a fresh planting is pure loss: the
                # seed money, the PLANT action and every watering it consumes
                # before the season ends with nothing harvested.
                matures = day + CROP_INFO[crop]["harvest_day"] <= cfg.season_days - 1
                if matures and seeds.get(crop, 0) > 0:
                    tasks.append((prio("PLANT", cfg), (x, y), ["PLANT", crop], crop))
            continue

        if not isinstance(tile, dict):
            continue

        kind = tile.get("kind")

        if kind == "WEED":
            tasks.append((prio("DIG", cfg), (x, y), ["DIG"], None))
            continue

        if kind == "PLANT":
            crop = tile["crop"]
            info = CROP_INFO.get(crop, CROP_INFO["WHEAT"])
            age = day - tile["planted_day"]
            lo_w, hi_w = info["window"]
            # Fertilising reaches the yield cap sooner, but only pays if we
            # also harvest sooner -- otherwise the cost is spent and the days
            # saved are thrown away waiting.
            harvest_at = info["harvest_day"]
            if crop in cfg.fertilize_crops and cfg.fert_harvest_day:
                harvest_at = cfg.fert_harvest_day
            if age >= harvest_at and tile.get("yield_units", 0) > 0:
                tasks.append((prio("HARVEST", cfg), (x, y), ["HARVEST"], None))
                continue
            # Fertilizer doubles the per-day watering bonus for three days, so a
            # melon reaches its cap of 6 at age 8 instead of 10 -- two days off
            # an 11-day cycle. We produce fertilizer free from the animals and
            # were selling all of it at ~$50/unit while a melon tile earns far
            # more than that from the days saved.
            if (
                cfg.fertilize_crops
                and crop in cfg.fertilize_crops
                and lo_w <= age <= hi_w
                and tile.get("fertilized_until_day", -1) < day
            ):
                tasks.append((prio("FERTILIZE", cfg), (x, y), ["FERTILIZE"], "FERTILIZER"))
            if not tile.get("watered_today"):
                # Two consecutive misses turns it into a weed.
                urgent = tile.get("consecutive_unwatered", 0) >= 1
                lo, hi = info["window"]
                useful = info["ongoing"] or lo <= age <= hi
                if urgent or useful:
                    key = "WATER_URGENT" if urgent else "WATER_BONUS"
                    tasks.append((prio(key, cfg), (x, y), ["WATER"], None))
            continue

        if kind in ("COOP", "PASTURE"):
            animal = tile.get("animal")
            if animal is None:
                # Only worth walking here if some worker is actually carrying
                # the right animal; `assign` rations that against inventories.
                want = animal_for(kind, cfg)
                tasks.append((prio("PLACE", cfg), (x, y), ["PLACE", want, 1], f"PLACE_{want}"))
                continue
            if not tile.get("fed_today"):
                tasks.append((prio("FEED", cfg), (x, y), ["FEED"], "FEED"))
            if tile.get("yield_units", 0) > 0:
                tasks.append((prio("HARVEST", cfg), (x, y), ["HARVEST"], None))
            if not tile.get("cared_today"):
                # CARE banks a bonus paid on the next yield, and the bank
                # accrued during growth pays out in a lump (docs/02-labour.md).
                tasks.append((prio("CARE", cfg), (x, y), ["CARE"], None))
            if tile.get("fertilizer_available") and fert_budget > 0:
                tasks.append((prio("FERT", cfg), (x, y), ["COLLECT_FERTILIZER"], "FERT"))

    tasks.sort(key=lambda t: -t[0])
    return tasks


# --- worker assignment ----------------------------------------------------

# Tasks at or above this priority may interrupt a worker mid-route. Starvation
# and weeding are irreversible; everything else can wait a turn.
PREEMPT_ABOVE = 90


def assign(units, tasks, carried_wheat, carried_animals, seeds, shed_animals,
           cfg_feed_carry=6, travel_weight=5.0, commitments=None, finish_tile=True,
           carried_fert=None, fert_carry=3, carried_melon_each=None,
           carried_each_total=None):
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
    fert = list(carried_fert) if carried_fert else [0] * len(units)
    melon_held = list(carried_melon_each) if carried_melon_each else [0] * len(units)
    carried_totals = list(carried_each_total) if carried_each_total else [0] * len(units)
    animals = [dict(a) for a in carried_animals]
    in_shed = dict(shed_animals)
    commitments = commitments if commitments is not None else {}

    # Several tasks can share a tile -- an animal wants FEED, HARVEST, CARE and
    # COLLECT_FERTILIZER at once -- so keep the most valuable one per position.
    # A plain dict comprehension keeps the *last* appended, which is the lowest
    # priority of the four.
    task_map = {}
    for prio, pos, op, need in tasks:
        if pos not in task_map or prio > task_map[pos][0]:
            task_map[pos] = (prio, op, need)

    def held(i):
        return sum(animals[i].values())

    def feasible(i, need):
        if actions[i] is not None:
            return False
        if need == "FEED" and wheat[i] <= 0:
            return False           # no feed on this worker
        if need == "ENDGAME" and carried_totals[i] <= 0:
            return False           # empty-handed, nothing to run in
        if need == "RUN_MELON" and melon_held[i] <= 0:
            return False           # nothing to run in
        if need == "FERTILIZER" and fert[i] <= 0:
            return False           # no fertilizer on this worker
        if need == "FETCH_FERT" and fert[i] > 0:
            return False           # already carrying some
        if need and need.startswith("PLACE_"):
            if animals[i].get(need[6:], 0) <= 0:
                return False       # not carrying this animal
        if need and need.startswith("FETCH_") and need != "FETCH_WHEAT":
            if held(i) > 0:
                return False       # already carrying an animal
        if need == "FETCH_WHEAT" and wheat[i] > 0:
            return False           # already stocked for today
        return True

    def commit(worker, pos, op, need):
        """Move toward the tile, or act if standing on it. Returns True if acted."""
        if need in CROP_INFO:
            if seeds.get(need, 0) <= 0:
                return None
            seeds[need] -= 1
        elif need and need.startswith("FETCH_") and need not in ("FETCH_WHEAT", "FETCH_FERT"):
            animal = need[6:]
            if in_shed.get(animal, 0) <= 0:
                return None
            in_shed[animal] -= 1

        taken.add(pos)
        ux, uy = units[worker]
        move = step_toward(ux, uy, *pos)
        if move:
            actions[worker] = [move]
            commitments[worker] = pos          # keep walking to it next turn
            return False
        actions[worker] = op
        commitments.pop(worker, None)          # arrived; free to pick a new tile
        # Only charge the consumable once the action actually fires.
        if need == "FEED":
            wheat[worker] -= 1
        elif need == "FETCH_WHEAT":
            wheat[worker] += cfg_feed_carry
        elif need == "FERTILIZER":
            fert[worker] -= 1
        elif need == "FETCH_FERT":
            fert[worker] += fert_carry
        elif need == "RUN_MELON":
            melon_held[worker] = 0
        elif need and need.startswith("PLACE_"):
            animal = need[6:]
            animals[worker][animal] = animals[worker].get(animal, 0) - 1
        elif need and need.startswith("FETCH_"):
            animal = need[6:]
            animals[worker][animal] = animals[worker].get(animal, 0) + 1
        return True

    def nearest_free(pos):
        best = None
        for i, upos in enumerate(units):
            if actions[i] is not None:
                continue
            d = distance(upos, pos)
            if best is None or d < best:
                best = d
        return best if best is not None else 0

    # --- phase 0: finish the tile you are standing on ------------------------
    # An animal tile wants four actions (FEED, CARE, HARVEST,
    # COLLECT_FERTILIZER) but only one can be taken per turn, so a worker that
    # leaves after one pays the walk back. Measured: 1.40 actions per tile
    # visit, with 967 of 1,385 visits ending at depth 1 and exactly one ever
    # reaching depth 4 (analysis/travel.py).
    #
    # The cause is that urgent watering outranks CARE, so workers get pulled off
    # mid-tile every turn. Standing work is free -- it costs no movement -- so
    # taking it first is close to strictly better than walking somewhere for
    # work of similar value.
    if finish_tile:
        for worker, upos in enumerate(units):
            if actions[worker] is not None or upos in taken:
                continue
            entry = task_map.get(upos)
            if entry and feasible(worker, entry[2]):
                commit(worker, upos, entry[1], entry[2])

    # --- phase 1: urgent work, globally ranked and allowed to preempt --------
    # Starvation and weeding are irreversible, so these outrank route locality.
    urgent = sorted(
        (t for t in tasks if t[0] >= PREEMPT_ABOVE),
        key=lambda t: -(t[0] - travel_weight * nearest_free(t[1])),
    )
    for _prio, pos, op, need in urgent:
        if pos in taken:
            continue
        best, best_d = None, None
        for i, upos in enumerate(units):
            if not feasible(i, need):
                continue
            d = distance(upos, pos)
            if best_d is None or d < best_d:
                best, best_d = i, d
        if best is not None:
            commit(best, pos, op, need)

    # --- phase 2: honour routes already in progress -------------------------
    # Without this, assignment is re-decided from scratch every turn and a
    # worker that has walked three tiles toward something can be redirected
    # before it arrives. Measured 65% of worker turns spent moving.
    for worker in range(len(units)):
        pos = commitments.get(worker)
        if pos is None:
            continue
        entry = task_map.get(pos)
        if entry is None or pos in taken or not feasible(worker, entry[2]):
            commitments.pop(worker, None)      # task is gone or now impossible
            continue
        commit(worker, pos, entry[1], entry[2])

    # --- phase 3: idle workers pick up the nearest remaining work -----------
    # Chosen by proximity to the worker rather than by global rank, so finishing
    # one tile naturally chains into an adjacent one instead of sending the
    # worker back across the farm.
    for worker in range(len(units)):
        if actions[worker] is not None:
            continue
        upos = units[worker]
        best, best_score = None, None
        for prio, pos, op, need in tasks:
            if pos in taken or not feasible(worker, need):
                continue
            score = prio - travel_weight * distance(upos, pos)
            if best_score is None or score > best_score:
                best, best_score = (pos, op, need), score
        if best:
            commit(worker, *best)

    return [a if a else ["PASS"] for a in actions]


# --- market ---------------------------------------------------------------

def market_orders(obs, farm, private, roles, cfg, animals_alive):
    orders = []
    money = farm["money"]
    hour = obs["hour"]
    shed = private["shed"]

    # Hire at the top of the day; hands vanish overnight. Each hire is its own
    # order and the per-turn cap is 10, so this has to own hour 0 alone.
    #
    # Hire to demand, not to a fixed target. The early season is capital-bound,
    # not labour-bound: measured idle is 25% on day 0, 51% on day 3 and 81% on
    # day 6, because every plantable tile is already planted and watered and
    # there is no money for more. Paying a full crew to stand around is worst
    # exactly when capital compounds hardest.
    if hour == 0:
        want = cfg.hands_target
        if cfg.hire_to_demand:
            workable = 0
            for (x, y) in roles:
                tile = farm["tiles"][y][x]
                if isinstance(tile, dict):
                    workable += 1                 # a plant or animal to tend
                elif tile is None:
                    workable += 1                 # a tile we could plant
            want = max(
                cfg.min_hands,
                min(cfg.hands_target, -(-workable // cfg.tiles_per_hand)),
            )
            # Never hire more than the bank can stand: the n-th hire of the day
            # costs fib(n), so a full crew on an empty bank is real money.
            if money < cfg.cash_floor * 4:
                want = min(want, cfg.min_hands)
        for _ in range(max(0, want - farm["hires_today"])):
            orders.append(["HIRE"])
        return orders[:MAX_MARKET_ORDERS]

    # --- margin-conditioned risk ----------------------------------------
    # The payoff is sign(M_i - M_j), not coins, and both players' money is
    # public every turn. So when the season is nearly over and we are behind by
    # more than normal play will close, expected coins are worth trading for
    # variance: a narrower loss scores exactly the same as a heavy one.
    #
    # The lever is withholding produce. Town demand keeps draining market
    # inventory, so prices recover while we hold, and dumping the lot at the end
    # can beat selling steadily. It can also lose everything: the shed caps at
    # 100 items and overflow is discarded silently. That downside is the point --
    # it is only correct when the safe line loses anyway.
    holding = False
    if cfg.risk_from_day and obs["day"] >= cfg.risk_from_day:
        opponent = obs["farms"][1 - obs["player"]]
        behind = opponent.get("money", 0) - money
        last_day = not cfg.season_days or obs["day"] >= cfg.season_days - 1
        stored = sum(shed.values())
        holding = (
            behind > cfg.risk_behind
            and not last_day
            and stored < SHED_CAP - cfg.risk_shed_margin
        )
    if holding:
        return orders[:MAX_MARKET_ORDERS]

    # Melon sells the instant it lands: the first-mover premium is $12,790 and
    # holding stock is how you lose it (docs/04-pools.md).
    if cfg.dump_melon and shed.get("MELON", 0) > 0:
        orders.append(["SELL", "MELON", shed["MELON"]])

    # Sell everything else that lands. This list is derived rather than
    # hardcoded: an unlisted product silently accumulates until the 100-item
    # shed cap, at which point *all* overflow is discarded -- so forgetting one
    # does not cost that product's revenue, it costs the whole shed. Adding
    # carrot as an opening crop hit exactly that, and the failure looked like a
    # flat -4,175 regardless of how much carrot was planted.
    for item in shed:
        if item in ("WHEAT", "MELON") or item in ANIMAL_INFO:
            continue                      # handled separately / not sellable
        held = shed.get(item, 0)
        if held <= 0:
            continue
        # Shallow pools reward metering. A1 measured milk floored after 76
        # units and wool after 59, against town demand that drains ~20-26/day:
        # dumping a stockpile walks the price to $1, whereas selling at the
        # drain rate holds it near base indefinitely. Deep pools (egg,
        # fertilizer) have no such cliff, so they are dumped.
        cap = cfg.sale_cap.get(item)
        orders.append(["SELL", item, min(held, cap) if cap else held])

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
        crop = planting_choice(role, obs["day"], cfg)
        wanted[crop] = wanted.get(crop, 0) + 1
    for crop in ("MELON", "CARROT", "WHEAT"):
        if crop not in wanted:
            continue
        need = min(wanted[crop], 12) - private["seeds"].get(crop, 0)
        cost = CROP_INFO[crop]["seed"]
        if need > 0 and money > cfg.cash_floor + need * cost:
            orders.append(["BUY_SEED", crop, need])

    # Livestock, once the engine can afford it. Pastures are bought first: milk
    # and wool are worth far more per unit than eggs and the field barely
    # contests them, but the pools are shallow so the allocation stays small.
    for structure in ("PASTURE", "COOP"):
        animal = animal_for(structure, cfg)
        # A cow bought on day 25 never produces -- first yield is 8 days out,
        # plus a day to build and place. Same reasoning as the planting cutoff.
        if cfg.season_days:
            lead = ANIMAL_FIRST_YIELD[animal] + 2
            if obs["day"] + lead > cfg.season_days - 1:
                continue
        vacant = sum(
            1
            for (x, y), role in roles.items()
            if role == structure
            and isinstance(farm["tiles"][y][x], dict)
            and farm["tiles"][y][x].get("kind") == structure
            and farm["tiles"][y][x].get("animal") is None
        )
        held = shed.get(animal, 0)
        if vacant > held and money > 1500:
            cost = ANIMAL_INFO[animal]["cost"]
            affordable = int((money - 1200) // cost)
            n = min(vacant - held, affordable)
            if n > 0:
                orders.append(["BUY_ANIMAL", animal, n])

    # Expansion. Two quadrants only (docs/03-allocation.md).
    bought = len(farm["unlocked_quadrants"]) - 1
    if bought < cfg.land_purchases:
        price = LAND_PRICES[bought]
        # Land bought too late is pure waste: with the planting cutoff above,
        # its tiles never even get sown.
        in_time = not cfg.season_days or obs["day"] + cfg.land_lead <= cfg.season_days - 1
        if money > price + 1500 and in_time:
            orders.append(["BUY_LAND"])

    return orders[:MAX_MARKET_ORDERS]


# --- entry point ----------------------------------------------------------

def make_agent(cfg=None):
    cfg = cfg or Config()
    # Routes in progress, worker index -> target tile. Held across turns so a
    # worker walking to a tile is not redirected before it arrives.
    state = {"day": -1, "units": -1, "commitments": {}}

    def agent(obs):
        farm = obs["farms"][obs["player"]]
        private = obs["private"]
        day, hour = obs["day"], obs["hour"]
        size = len(farm["tiles"])

        units = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]
        # Size the working area to the workforce we expect to have, not to the
        # skeleton crew present before the day's hires land.
        opponent = obs['farms'][1 - obs['player']]
        roles = plan_layout(farm, cfg, max(len(units), cfg.hands_target + 1), opponent)

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
        carried_animals = [
            {a: inv.get(a, 0) for a in ANIMAL_INFO if inv.get(a, 0)}
            for inv in inventories
        ]
        carried_fert = [inv.get("FERTILIZER", 0) for inv in inventories]
        while len(carried) < len(units):
            carried.append(0)
        while len(carried_fert) < len(units):
            carried_fert.append(0)
        while len(carried_animals) < len(units):
            carried_animals.append({})
        shed_animals = {a: private["shed"].get(a, 0) for a in ANIMAL_INFO}

        fert_budget = max(0, cfg.fertilizer_quota)
        melon_each = [inv.get("MELON", 0) for inv in inventories]
        while len(melon_each) < len(units):
            melon_each.append(0)
        carried_any = sum(
            v for inv in inventories for k, v in inv.items() if k not in ANIMAL_INFO
        )
        tasks = gather_tasks(
            farm, private, roles, day, cfg, fert_budget, build_budget,
            sum(melon_each), carried_any, hour,
        )
        # Hands are re-hired every morning and land as market orders after the
        # hour-0 actions, so worker indices only mean the same thing within a
        # day and only once the day's hires have arrived. Drop routes whenever
        # that identity could have changed.
        if day != state["day"] or len(units) != state["units"]:
            state["commitments"].clear()
            state["day"] = day
            state["units"] = len(units)

        assigned = assign(
            units, tasks, carried, carried_animals,
            private["seeds"], shed_animals, cfg.feed_carry,
            cfg.travel_weight,
            state["commitments"] if cfg.route_commit else {},
            cfg.finish_tile, carried_fert, cfg.fert_carry, melon_each,
            [sum(v for k, v in inv.items() if k not in ANIMAL_INFO)
             for inv in inventories],
        )

        return {
            "farmer": assigned[0],
            "hands": assigned[1:],
            "market": market_orders(obs, farm, private, roles, cfg, animals_alive),
        }

    return agent
