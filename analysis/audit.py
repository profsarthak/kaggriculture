"""Systematic mechanic audit: drive every documented rule against the interpreter.

`verify.py` checks the twelve rules Phase A's conclusions rest on. This checks the
rest -- the ones no doc claims, which is exactly where a silent loss can hide. The
locked-shed-tile finding came from reading the interpreter rather than our own
notes, and it turned out half our shed operations were no-ops. That was found by
accident. This is the same search done deliberately.

Two parts:

  Part 1  scripted micro-episodes that isolate one rule each. These say what the
          interpreter does, not whether it costs us anything.
  Part 2  instrumented full episodes of our own agent, counting what each rule
          actually destroys or blocks in real play.

Part 1 failing means a doc is wrong. Part 2 returning zero means the rule is real
but costs us nothing, which is a reason NOT to act -- see the locked shed tiles,
where 50% of operations were failing and fixing it measured -2,153.

Run:  python -m analysis.audit
"""

import kaggle_environments.envs.kaggriculture.kaggriculture as K
from kaggle_environments import make

PASS = {"farmer": ["PASS"], "hands": [], "market": []}
RESULTS = []
SHED_TILE = (4, 4)  # farmer's spawn: shed-adjacent and a normal buildable tile


def record(name, expected, actual, note=""):
    ok = expected == actual
    RESULTS.append((ok, name, expected, actual, note))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: expected {expected}, got {actual} {note}")
    return ok


def observe(name, value, note=""):
    """A measurement with no pass/fail -- reported, not asserted."""
    print(f"  [ .. ] {name}: {value} {note}")
    return value


def run(agent, steps, **config):
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": 7, **config})
    env.run([agent, "pass"])
    return env


def final(env):
    return env.steps[-1][0].observation


def held(obs, item):
    return obs["private"]["inventories"][0].get(item, 0) + obs["private"]["shed"].get(item, 0)


# ---------------------------------------------------------------------------
# Part 1a -- feeding: what does an unfed animal actually lose?
# ---------------------------------------------------------------------------

def animal_agent(animal, cadence, care=True, stop_day=14):
    """Keep one animal, feeding every `cadence` days. Harvest daily.

    Inventory is wiped into the shed at every end-of-day refresh, so the wheat
    for the day has to be picked up that morning.
    """
    structure = "BUILD_COOP" if K.ANIMALS[animal]["structure"] == "COOP" else "BUILD_PASTURE"

    def agent(obs):
        step, day, hour = obs["step"], obs["day"], obs["hour"]
        market = []
        if step == 0:
            market = [["BUY_ANIMAL", animal, 1], ["BUY_PRODUCT", "WHEAT", 40]]
        if step == 1:
            return {"farmer": [structure], "hands": [], "market": market}
        if step == 2:
            return {"farmer": ["PICKUP", animal, 1], "hands": [], "market": market}
        if step == 3:
            return {"farmer": ["PLACE", animal, 1], "hands": [], "market": market}
        if day > stop_day:
            return PASS
        # The animal is placed at hour 3 on day 0, so the daily routine has to
        # sit after that or day 0's feed lands on an empty structure and the
        # animal starts life already one unfed day down.
        feed_today = (day % cadence) == 0
        if hour == 5 and feed_today:
            return {"farmer": ["PICKUP", "WHEAT", 1], "hands": [], "market": market}
        if hour == 6 and feed_today:
            return {"farmer": ["FEED"], "hands": [], "market": market}
        if hour == 7 and care and feed_today:
            return {"farmer": ["CARE"], "hands": [], "market": market}
        if hour == 8:
            return {"farmer": ["HARVEST"], "hands": [], "market": market}
        if hour == 9:
            return {"farmer": ["COLLECT_FERTILIZER"], "hands": [], "market": market}
        return {"farmer": ["PASS"], "hands": [], "market": market}

    return agent


def audit_feeding():
    """The rule: `base = 1` is added on every interval day regardless of feeding.

    Only the *care bonus* is gated on `fed_today` (kaggriculture.py:802-806), and
    the animal only leaves at `consecutive_unfed >= 2` (795). So feeding on
    alternate days keeps the animal and its base yield, and forfeits only the
    bonus. We currently feed every animal every day at priority 100.
    """
    print("\n=== Part 1a: feeding cadence ===")
    days = 14
    for animal in ("GOOSE", "COW"):
        product = K.ANIMALS[animal]["product"]
        out = {}
        for cadence in (1, 2, 3):
            obs = final(run(animal_agent(animal, cadence, stop_day=days), (days + 1) * 24))
            tiles = obs["farms"][0]["tiles"]
            alive = any(
                isinstance(t, dict) and t.get("animal") == animal
                for row in tiles for t in row
            )
            out[cadence] = (held(obs, product), held(obs, "FERTILIZER"), alive)

        base = out[1][0]
        for cadence in (1, 2, 3):
            product_n, fert_n, alive = out[cadence]
            share = f"{product_n / base:.0%} of daily" if base else "n/a"
            observe(
                f"{animal} fed every {cadence}d",
                f"{product_n} {product}, {fert_n} FERT, alive={alive}",
                f"({share}, {(days + 1) // cadence} feed actions)",
            )

        record(f"{animal} survives alternate-day feeding", True, out[2][2])
        record(f"{animal} still produces unfed on 2-day cadence", True, out[2][0] > 0)
        record(f"{animal} starves on 3-day cadence", False, out[3][2])
        record(
            f"{animal} fertilizer is independent of feeding",
            True, out[2][1] >= out[1][1] - 1,
            f"({out[1][1]} daily vs {out[2][1]} alternate)",
        )


# ---------------------------------------------------------------------------
# Part 1b -- the shed: what silently disappears
# ---------------------------------------------------------------------------

def shed_agent(mode, cap):
    """Fill the shed, hold `cap` units, then try to put them away.

    DROP deletes the whole inventory whether or not it fits (kaggriculture.py:339
    dels unconditionally). PLACE moves `min(n, room)` and leaves the rest (473).
    """
    def agent(obs):
        step = obs["step"]
        if step == 0:  # fill the shed to capacity
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "WHEAT", cap]]}
        if step == 1:  # take some back out, so we are holding goods
            return {"farmer": ["PICKUP", "WHEAT", 5], "hands": [], "market": []}
        if step == 2:  # refill the shed behind us
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "WHEAT", 5]]}
        if step == 3:
            action = ["DROP"] if mode == "DROP" else ["PLACE", "WHEAT", 5]
            return {"farmer": action, "hands": [], "market": []}
        return PASS
    return agent


def audit_shed():
    print("\n=== Part 1b: shed capacity and overflow ===")
    cap = 20  # small cap keeps the test cheap; the code path is capacity-generic

    for mode in ("DROP", "PLACE"):
        obs = final(run(shed_agent(mode, cap), 8, shedCapacity=cap))
        inv = obs["private"]["inventories"][0].get("WHEAT", 0)
        shed = obs["private"]["shed"].get("WHEAT", 0)
        observe(f"{mode} against a full shed", f"{inv} still held, {shed} in shed")
        record(f"{mode} overflow: 5 units held, shed full", 0 if mode == "DROP" else 5, inv,
               "(DROP destroys, PLACE keeps)")

    # A full shed also refuses purchases -- including the wheat the animals eat.
    def blocked_agent(obs):
        step = obs["step"]
        if step == 0:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "WHEAT", cap]]}
        if step == 1:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "WHEAT", 5], ["BUY_ANIMAL", "GOOSE", 1]]}
        return PASS

    obs = final(run(blocked_agent, 6, shedCapacity=cap))
    record("full shed blocks BUY_PRODUCT", cap, obs["private"]["shed"].get("WHEAT", 0))
    record("full shed blocks BUY_ANIMAL", 0, obs["private"]["shed"].get("GOOSE", 0))

    # And selling draws from the shed only -- carried stock is unsellable.
    def carry_sell_agent(obs):
        step = obs["step"]
        if step == 0:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "WHEAT", 10]]}
        if step == 1:
            return {"farmer": ["PICKUP", "WHEAT", 10], "hands": [], "market": []}
        if step == 2:  # holding all 10; the shed is empty
            return {"farmer": ["PASS"], "hands": [], "market": [["SELL", "WHEAT", 10]]}
        return PASS

    obs = final(run(carry_sell_agent, 6, shedCapacity=cap))
    record("SELL cannot reach carried stock", 10,
           obs["private"]["inventories"][0].get("WHEAT", 0))


# ---------------------------------------------------------------------------
# Part 1c -- end of episode
# ---------------------------------------------------------------------------

def audit_timing():
    """Where the season actually stops, and what still resolves on the way out."""
    print("\n=== Part 1c: end of episode ===")
    steps = 240  # 10 days, same structure as the 720-step season

    seen = []

    def watcher(obs):
        seen.append(obs["step"])
        return PASS

    env = run(watcher, steps)
    record("last step the agent acts on", steps - 2, max(seen),
           f"(episodeSteps={steps}; hour {max(seen) % 24} of day {max(seen) // 24})")
    record("final day gets no end-of-day refresh", 23, (max(seen) % 24) + 1,
           "(refresh needs (step+1) %% 24 == 0)")

    # Unit actions resolve before the market in the same turn, so stock dropped
    # on the last turn is still sellable on the last turn.
    def last_gasp(obs):
        step = obs["step"]
        if step == 0:
            return {"farmer": ["PASS"], "hands": [],
                    "market": [["BUY_PRODUCT", "WHEAT", 10]]}
        if step == 1:
            return {"farmer": ["PICKUP", "WHEAT", 10], "hands": [], "market": []}
        if step == steps - 2:  # drop and sell on the very last acting turn
            return {"farmer": ["DROP"], "hands": [], "market": [["SELL", "WHEAT", 10]]}
        return PASS

    env = run(last_gasp, steps)
    obs = final(env)
    record("DROP then SELL in the same turn both resolve", 0,
           obs["private"]["shed"].get("WHEAT", 0) + obs["private"]["inventories"][0].get("WHEAT", 0))


# ---------------------------------------------------------------------------
# Part 1d -- watering window and hire cost (confirming what we already model)
# ---------------------------------------------------------------------------

def water_agent(crop, water_ages, harvest_age):
    def agent(obs):
        step, day, hour = obs["step"], obs["day"], obs["hour"]
        if step == 0:
            return {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", crop, 1]]}
        if step == 1:
            return {"farmer": ["PLANT", crop], "hands": [], "market": []}
        if day == harvest_age and hour == 5:
            return {"farmer": ["HARVEST"], "hands": [], "market": []}
        if day in water_ages and hour == (3 if day == 0 else 1):
            return {"farmer": ["WATER"], "hands": [], "market": []}
        return PASS
    return agent


def audit_water_window():
    """Watering only adds yield inside [(max_yield_day+1)//2, max_yield_day].

    Outside it, watering is pure survival. We already model this (`CROP_INFO`
    carries a `window`), so this is a regression check on a live assumption.
    """
    print("\n=== Part 1d: watering window ===")
    # `_new_plant` sets consecutive_unwatered=1, so day 0 must be watered or the
    # plant weeds at the first refresh. Every schedule below therefore includes
    # it, and the comparison is over what the *extra* waterings buy.
    survive = final(run(water_agent("WHEAT", {0, 2, 4}, 4), 6 * 24))
    window = final(run(water_agent("WHEAT", {0, 2, 3, 4}, 4), 6 * 24))
    everyday = final(run(water_agent("WHEAT", {0, 1, 2, 3, 4}, 4), 6 * 24))
    record("WHEAT: alternate-day survival watering", 3, held(survive, "WHEAT"),
           "(1 base + ages 2 and 4)")
    record("WHEAT: every day in the 2-4 window", 4, held(window, "WHEAT"))
    record("WHEAT: watering age 1 as well buys nothing", held(window, "WHEAT"),
           held(everyday, "WHEAT"), "(one action wasted outside the window)")

    print("\n=== Part 1d: hire cost ===")
    costs = [K._hire_cost(n) for n in range(13)]
    observe("cost of the n-th hire today", costs)
    observe("cumulative cost of k hands", [sum(costs[:k]) for k in range(1, 13)],
            "(charged every day; hires_today resets at the refresh)")
    record("hire cost is Fibonacci from 1", [1, 1, 2, 3, 5, 8, 13], costs[:7])


# ---------------------------------------------------------------------------
# Part 2 -- what our own agent loses to these rules
# ---------------------------------------------------------------------------

class Instrument:
    """Wrap the interpreter's mutating helpers and count what they destroy."""

    def __init__(self):
        self.drop_lost = 0
        self.drop_calls = 0
        self.eod_lost = 0
        self.buys_blocked = 0
        self.feeds = 0
        self.escapes = 0
        self.shed_peak = 0
        self.shed_full_steps = 0
        self.animal_days = 0
        self.fed_animal_days = 0
        self.cared_animal_days = 0
        self.banking_days = 0
        self.production_days = 0
        self.production_days_fed = 0
        self.bonus_wiped = 0
        self.produced = 0
        self.capped_loss = 0
        self.harvested = 0
        self.issued = {}
        self.noops = {}
        self.orders_issued = 0
        self.orders_dropped = 0
        self.turns_over_cap = 0
        self.why = {}
        self._originals = {}

    def __enter__(self):
        inst = self
        self._originals = {
            "_apply_unit_action": K._apply_unit_action,
            "_drop_inventories_to_shed": K._drop_inventories_to_shed,
            "_commit_unit": K._commit_unit,
            "_daily_refresh_animals": K._daily_refresh_animals,
            "_process_market": K._process_market,
        }
        orig = self._originals

        def fingerprint(farm, private, idx):
            """Everything `_apply_unit_action` is able to touch, cheaply."""
            pos = K._farmer_position(farm, idx)
            if pos is None:
                return None
            tile = farm["tiles"][pos[1]][pos[0]]
            return (
                tuple(pos),
                repr(tile),
                tuple(sorted(K._farmer_inventory(private, idx).items())),
                sum(private["shed"].values()),
                tuple(sorted(private["seeds"].items())),
            )

        def apply_unit_action(farm, private, idx, action, *a, **kw):
            if not (isinstance(action, list) and action):
                return orig["_apply_unit_action"](farm, private, idx, action, *a, **kw)
            op = action[0]
            inv = K._farmer_inventory(private, idx)
            before_inv = sum(inv.values())
            before_shed = sum(private["shed"].values())
            before_wheat = inv.get("WHEAT", 0)
            before = fingerprint(farm, private, idx)

            result = orig["_apply_unit_action"](farm, private, idx, action, *a, **kw)

            inst.issued[op] = inst.issued.get(op, 0) + 1
            if before is not None and fingerprint(farm, private, idx) == before:
                inst.noops[op] = inst.noops.get(op, 0) + 1
                if op in ("PICKUP", "DROP"):
                    pos, board = before[0], len(farm["tiles"])
                    if not K._is_shed_adjacent(pos, board):
                        why = "not at the shed"
                    elif farm["tiles"][pos[1]][pos[0]] == "LOCKED":
                        why = "standing on a LOCKED shed tile"
                    elif op == "DROP":
                        why = "nothing in hand"
                    elif private["shed"].get(action[1] if len(action) > 1 else "", 0) <= 0:
                        why = f"shed has no {action[1] if len(action) > 1 else '?'}"
                    else:
                        why = "unexplained"
                    key = (op, why)
                    inst.why[key] = inst.why.get(key, 0) + 1
            if op == "DROP":
                left = before_inv - sum(inv.values())
                if left > 0:
                    inst.drop_calls += 1
                    inst.drop_lost += left - (sum(private["shed"].values()) - before_shed)
            elif op == "FEED" and inv.get("WHEAT", 0) < before_wheat:
                inst.feeds += 1
            elif op == "HARVEST":
                gained = sum(inv.values()) - before_inv
                if gained > 0:
                    inst.harvested += gained
            return result

        def process_market(state, env):
            cap = max(1, int(K.get(env.configuration, "maxMarketOrdersPerTurn", 10)))
            for s in state:
                action = s.action if isinstance(s.action, dict) else {}
                orders = action.get("market", []) if isinstance(action, dict) else []
                if not isinstance(orders, list):
                    continue
                inst.orders_issued += len(orders)
                if len(orders) > cap:
                    inst.orders_dropped += len(orders) - cap
                    inst.turns_over_cap += 1
            return orig["_process_market"](state, env)

        def drop_inventories_to_shed(private, capacity):
            before = sum(sum(i.values()) for i in private["inventories"])
            shed_before = sum(private["shed"].values())
            result = orig["_drop_inventories_to_shed"](private, capacity)
            inst.eod_lost += before - (sum(private["shed"].values()) - shed_before)
            inst.shed_peak = max(inst.shed_peak, sum(private["shed"].values()))
            return result

        def commit_unit(op, item, price, farm, private, market, shed_capacity=100):
            result = orig["_commit_unit"](op, item, price, farm, private, market, shed_capacity)
            if not result and op in ("BUY_PRODUCT", "BUY_ANIMAL"):
                if sum(private["shed"].values()) >= shed_capacity:
                    inst.buys_blocked += 1
            shed = sum(private["shed"].values())
            inst.shed_peak = max(inst.shed_peak, shed)
            if shed >= shed_capacity:
                inst.shed_full_steps += 1
            return result

        def daily_refresh_animals(farm, day):
            living = [
                t for row in farm["tiles"] for t in row
                if isinstance(t, dict) and "animal" in t
            ]
            before = len(living)
            inst.animal_days += before
            inst.fed_animal_days += sum(1 for t in living if t["fed_today"])
            inst.cared_animal_days += sum(1 for t in living if t["cared_today"])
            # Care only banks when the animal was also fed that day.
            inst.banking_days += sum(1 for t in living if t["cared_today"] and t["fed_today"])
            # An unfed production day pays base only AND resets the bank to 0
            # (kaggriculture.py:804-806), so banked care is destroyed, not deferred.
            for t in living:
                a = K.ANIMALS[t["animal"]]
                since = (day + 1) - t["placed_day"] - a["first_yield_day"]
                if since >= 0 and since % a["interval"] == 0:
                    inst.production_days += 1
                    if t["fed_today"]:
                        inst.production_days_fed += 1
                    elif t.get("pending_care_bonus", 0) > 0:
                        inst.bonus_wiped += t["pending_care_bonus"]
                    # What this animal is about to earn, and how much of it the
                    # max_held cap will throw away because nobody harvested.
                    bonus = t.get("pending_care_bonus", 0) if t["fed_today"] else 0
                    gain = 1 + bonus
                    inst.produced += gain
                    room = max(0, a["max_held"] - t["yield_units"])
                    inst.capped_loss += max(0, gain - room)
            result = orig["_daily_refresh_animals"](farm, day)
            after = sum(
                1 for row in farm["tiles"] for t in row
                if isinstance(t, dict) and "animal" in t
            )
            inst.escapes += max(0, before - after)
            return result

        K._apply_unit_action = apply_unit_action
        K._drop_inventories_to_shed = drop_inventories_to_shed
        K._commit_unit = commit_unit
        K._daily_refresh_animals = daily_refresh_animals
        K._process_market = process_market
        return self

    def __exit__(self, *exc):
        for name, fn in self._originals.items():
            setattr(K, name, fn)
        return False


def audit_our_play(episodes=3):
    """Count, in real games, what the Part 1 rules cost us.

    The instrument counts both players, so figures are per two farms. What
    matters is whether they are zero.
    """
    print(f"\n=== Part 2: what our agent loses ({episodes} episodes) ===")
    import farmlib

    totals = Instrument()
    for seed in range(episodes):
        with Instrument() as inst:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([farmlib.make_agent(), farmlib.make_agent()])
        for field in ("drop_lost", "drop_calls", "eod_lost", "buys_blocked",
                      "feeds", "escapes", "animal_days", "fed_animal_days",
                      "cared_animal_days", "banking_days", "production_days",
                      "production_days_fed", "bonus_wiped", "orders_issued",
                      "orders_dropped", "turns_over_cap"):
            setattr(totals, field, getattr(totals, field) + getattr(inst, field))
        totals.shed_peak = max(totals.shed_peak, inst.shed_peak)
        for op, count in inst.issued.items():
            totals.issued[op] = totals.issued.get(op, 0) + count
        for op, count in inst.noops.items():
            totals.noops[op] = totals.noops.get(op, 0) + count
        for key, count in inst.why.items():
            totals.why[key] = totals.why.get(key, 0) + count

    n = episodes
    observe("units destroyed by DROP into a full shed", f"{totals.drop_lost / n:.1f} per episode",
            f"(over {totals.drop_calls / n:.0f} drops that moved anything)")
    observe("units destroyed by the end-of-day refresh", f"{totals.eod_lost / n:.1f} per episode")
    observe("purchases refused because the shed was full", f"{totals.buys_blocked / n:.1f} per episode")
    observe("peak shed occupancy", f"{totals.shed_peak} of 100")
    observe("FEED actions issued", f"{totals.feeds / n:.0f} per episode (both farms)")
    observe("animals lost to starvation", f"{totals.escapes / n:.1f} per episode")
    if totals.animal_days:
        pct = lambda a, b: f"{a}/{b} = {a / b:.0%}" if b else "n/a"
        observe("animal-days that ended fed", pct(totals.fed_animal_days, totals.animal_days),
                "(the cadence we actually play, not the one we intend)")
        observe("animal-days that ended cared", pct(totals.cared_animal_days, totals.animal_days))
        observe("animal-days that banked a care bonus", pct(totals.banking_days, totals.animal_days),
                "(needs fed AND cared the same day)")
        observe("production days that ended fed", pct(totals.production_days_fed, totals.production_days),
                "(unfed pays base only)")
        observe("care bonus destroyed by an unfed production day",
                f"{totals.bonus_wiped / n:.1f} units per episode")

    print("\n  --- actions that changed nothing ---")
    print(f"  {'op':<20} {'issued':>8} {'no-op':>8} {'waste':>7}")
    movement = set(K.FARMER_MOVES)
    total_issued = total_noop = 0
    for op in sorted(totals.issued, key=lambda o: -totals.noops.get(o, 0)):
        issued = totals.issued[op]
        noop = totals.noops.get(op, 0)
        if op not in movement and op != "PASS":
            total_issued += issued
            total_noop += noop
        print(f"  {op:<20} {issued // n:>8} {noop // n:>8} {noop / issued:>6.0%}")
    if total_issued:
        observe("wasted non-movement actions",
                f"{total_noop // n} of {total_issued // n} per episode"
                f" = {total_noop / total_issued:.0%}",
                "(both farms; movement and PASS excluded)")

    if totals.why:
        print("\n  --- why shed operations fail ---")
        for (op, why), count in sorted(totals.why.items(), key=lambda kv: -kv[1]):
            print(f"  {op:<8} {why:<34} {count // n:>5} per episode")

    print("\n  --- market orders ---")
    observe("orders issued", f"{totals.orders_issued / n:.0f} per episode")
    observe("orders silently truncated past the 10/turn cap",
            f"{totals.orders_dropped / n:.1f} per episode",
            f"(on {totals.turns_over_cap / n:.1f} turns)")
    return totals


def main():
    audit_feeding()
    audit_shed()
    audit_timing()
    audit_water_window()
    audit_our_play()

    failed = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} rule checks passed")
    if failed:
        print("\nFAILURES -- a documented rule does not hold:")
        for _, name, expected, actual, _note in failed:
            print(f"  {name}: expected {expected}, got {actual}")
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
