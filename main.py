"""Submission entry point.

Kaggle calls `agent(obs)` from this module. The decision logic lives in
farmlib.py so Phase C can fork it into a strategy portfolio without duplicating
it; submit as a tar.gz with both files at the root.

Default config is the Phase A recommendation -- see docs/ for the derivation of
every number in farmlib.Config.
"""

import os
import sys

# Kaggle unpacks the submission into /kaggle_simulations/agent/ and imports this
# file from an arbitrary working directory, so the sibling module is not
# necessarily importable. Put our own directory on the path before touching it.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from farmlib import Config, make_agent  # noqa: E402

_agent = make_agent(Config())


def agent(obs):
    return _agent(obs)
