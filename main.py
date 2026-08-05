"""Submission entry point.

Kaggle calls `agent(obs)` from this module. The decision logic lives in
farmlib.py so Phase C can fork it into a strategy portfolio without duplicating
it; submit as a tar.gz with both files at the root.

Default config is the Phase A recommendation -- see docs/ for the derivation of
every number in farmlib.Config.
"""

from farmlib import Config, make_agent

_agent = make_agent(Config())


def agent(obs):
    return _agent(obs)
