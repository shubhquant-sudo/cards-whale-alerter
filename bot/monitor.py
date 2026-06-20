"""Entry point: poll the watchlist, diff against saved state, alert on events.

Run:  python -m bot.monitor
First run records baselines and sends a "monitoring started" summary (no false
alerts). Every later run diffs the chain against the saved state, runs the rules
engine, and sends a Claude-written alert per event.
"""
import datetime
import json
import os

from . import market as market_mod
from . import rules
from . import solana
from . import state as state_mod
from . import telegram
from . import claude_signal
from .paths import BIBLE_PATH, WATCHLIST_PATH


def _load_config():
    with open(WATCHLIST_PATH) as f:
        return json.load(f)


def _load_bible():
    with open(BIBLE_PATH) as f:
        return f.read()


def _snapshot_wallets(config):
    """Current {address: {cards, sol, last_sig, last_active_ts}} for every wallet."""
    mint = config["mint"]
    snaps = {}
    for w in config["wallets"]:
        addr = w["address"]
        try:
            cards = solana.get_cards_balance(addr, mint)
            sol = solana.get_sol_balance(addr)
            last_sig, last_ts = solana.get_last_signature(addr)
            snaps[addr] = {"cards": cards, "sol": sol,
                           "last_sig": last_sig, "last_active_ts": last_ts}
        except Exception as e:  # noqa: BLE001 - one bad wallet shouldn't kill the run
            print(f"WARN snapshot failed for {addr}: {e}")
    return snaps


def _startup_summary(config, snaps, market):
    n = len(snaps)
    price = market.get("price")
    lines = [
        "\U0001F0CF <b>CARDS whale alerter — monitoring started</b>",
        f"Watching {n} wallets + the main Raydium pool.",
        f"Spot ~${price} · main-pool liq ~${(market.get('main_liquidity_usd') or 0):,.0f}",
        "",
        "You'll get an alert when the treasury moves, a dormant whale wakes, "
        "a watched wallet sells/moves funds, or pool liquidity drops.",
    ]
    return "\n".join(lines)


def run():
    config = _load_config()
    bible = _load_bible()
    prev = state_mod.load()

    market = market_mod.get_market(config["mint"])
    snaps = _snapshot_wallets(config)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_state = {
        "initialized": True,
        "last_run": now,
        "wallets": snaps,
        "market": {
            "main_liquidity_usd": market.get("main_liquidity_usd"),
            "price": market.get("price"),
            "price_change_h1": market.get("price_change_h1"),
            "price_dump_flag": rules.next_price_dump_flag(prev, market, config),
        },
    }

    if not prev.get("initialized"):
        telegram.send(_startup_summary(config, snaps, market))
        state_mod.save(new_state)
        print("Initialized baselines for", len(snaps), "wallets.")
        return

    events = rules.evaluate(prev, snaps, market, config)
    print(f"{now}: {len(events)} event(s) detected.")
    sent = 0
    for ev in events:
        body = claude_signal.render(ev, bible, market)
        if telegram.send(telegram.format_message(ev, body)):
            sent += 1
    print(f"Sent {sent}/{len(events)} alert(s).")

    # Save state even if some sends failed, to avoid re-alerting in a loop.
    state_mod.save(new_state)


if __name__ == "__main__":
    run()
