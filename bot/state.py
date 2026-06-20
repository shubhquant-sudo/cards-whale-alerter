"""Load/save the JSON state file (committed back by the GitHub Action)."""
import json
import os

from .paths import STATE_PATH


def load():
    if not os.path.exists(STATE_PATH):
        return {"initialized": False, "wallets": {}, "market": {}}
    with open(STATE_PATH) as f:
        return json.load(f)


def save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
