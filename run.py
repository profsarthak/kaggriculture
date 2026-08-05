"""Run one local episode and print the result.

    python run.py            # our agent vs the built-in starter
    python run.py random     # our agent vs the random agent
"""

import sys

from kaggle_environments import make

opponent = sys.argv[1] if len(sys.argv) > 1 else "starter"

env = make("kaggriculture", debug=True)
env.run(["main.py", opponent])

final = env.steps[-1]
print()
for i, state in enumerate(final):
    who = "us" if i == 0 else opponent
    print(f"player {i} ({who}): reward={state.reward} status={state.status}")

with open("replay.json", "w") as f:
    import json

    json.dump(env.toJSON(), f)
print("\nwrote replay.json")
