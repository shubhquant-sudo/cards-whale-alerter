"""Shared filesystem paths, resolved relative to the repo root."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
WATCHLIST_PATH = os.path.join(CONFIG_DIR, "watchlist.json")
BIBLE_PATH = os.path.join(CONFIG_DIR, "bible.md")
STATE_PATH = os.path.join(ROOT, "state", "state.json")
