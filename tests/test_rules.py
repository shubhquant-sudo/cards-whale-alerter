"""Unit tests for the rules engine — pure logic, no network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import rules  # noqa: E402

CONFIG = {
    "main_pool_address": "POOL",
    "liq_drop_pct": 0.20,
    "price_dump_pct": -10.0,
    "price_dump_reset_pct": -5.0,
    "wallets": [
        {"address": "TREASURY", "label": "Treasury", "role": "treasury",
         "cards_outflow_alert": 500000, "sol_outflow_alert": 5},
        {"address": "MM", "label": "MM", "role": "market_maker",
         "cards_outflow_alert": 2000000, "sol_outflow_alert": 2000},
        {"address": "DORMANT", "label": "Dormant", "role": "dormant_whale",
         "cards_outflow_alert": 100000, "sol_outflow_alert": 1},
        {"address": "WHALE", "label": "Whale", "role": "whale",
         "cards_outflow_alert": 200000, "sol_outflow_alert": 100},
    ],
}


def _kinds(events):
    return {(e["kind"], e["address"]): e for e in events}


def test_no_events_when_nothing_changes():
    prev = {"wallets": {"WHALE": {"cards": 1000000, "sol": 10, "last_sig": "a"}}, "market": {}}
    snaps = {"WHALE": {"cards": 1000000, "sol": 10, "last_sig": "a"}}
    assert rules.evaluate(prev, snaps, {"price": 0.29}, CONFIG) == []


def test_treasury_outflow_is_critical():
    prev = {"wallets": {"TREASURY": {"cards": 1_585_000_000, "sol": 7, "last_sig": "a"}}, "market": {}}
    snaps = {"TREASURY": {"cards": 1_584_000_000, "sol": 7, "last_sig": "b"}}  # -1M
    ev = _kinds(rules.evaluate(prev, snaps, {"price": 0.29}, CONFIG))
    assert ev[("CARDS_OUTFLOW", "TREASURY")]["severity"] == "CRITICAL"
    assert ev[("CARDS_OUTFLOW", "TREASURY")]["amount"] == 1_000_000


def test_small_treasury_move_below_threshold_is_silent():
    prev = {"wallets": {"TREASURY": {"cards": 1_585_000_000, "sol": 7, "last_sig": "a"}}, "market": {}}
    snaps = {"TREASURY": {"cards": 1_584_900_000, "sol": 7, "last_sig": "a"}}  # -100k < 500k
    assert rules.evaluate(prev, snaps, {"price": 0.29}, CONFIG) == []


def test_dormant_wake_fires_on_new_signature():
    prev = {"wallets": {"DORMANT": {"cards": 4_000_000, "sol": 1, "last_sig": "old"}}, "market": {}}
    snaps = {"DORMANT": {"cards": 4_000_000, "sol": 1, "last_sig": "new"}}
    ev = _kinds(rules.evaluate(prev, snaps, {"price": 0.29}, CONFIG))
    assert ("DORMANT_WAKE", "DORMANT") in ev
    assert ev[("DORMANT_WAKE", "DORMANT")]["severity"] == "HIGH"


def test_whale_inflow_is_info_accumulation():
    prev = {"wallets": {"WHALE": {"cards": 1_000_000, "sol": 10, "last_sig": "a"}}, "market": {}}
    snaps = {"WHALE": {"cards": 1_300_000, "sol": 10, "last_sig": "a"}}  # +300k
    ev = _kinds(rules.evaluate(prev, snaps, {"price": 0.29}, CONFIG))
    assert ev[("CARDS_INFLOW", "WHALE")]["severity"] == "INFO"


def test_pool_liquidity_drop_is_critical():
    prev = {"wallets": {}, "market": {"main_liquidity_usd": 3_750_000}}
    snaps = {}
    market = {"price": 0.29, "main_liquidity_usd": 2_700_000}  # -28%
    ev = _kinds(rules.evaluate(prev, snaps, market, CONFIG))
    assert ev[("POOL_LIQUIDITY_DROP", "POOL")]["severity"] == "CRITICAL"


def test_price_dump_hysteresis():
    prev = {"wallets": {}, "market": {"price_dump_flag": False}}
    market = {"price": 0.29, "price_change_h1": -12.0}
    ev = _kinds(rules.evaluate(prev, {}, market, CONFIG))
    assert ("PRICE_DUMP", "") in ev
    # once flagged, it should not re-fire
    prev2 = {"wallets": {}, "market": {"price_dump_flag": True}}
    assert rules.evaluate(prev2, {}, market, CONFIG) == []
    assert rules.next_price_dump_flag(prev2, {"price_change_h1": -3.0}, CONFIG) is False


def test_events_sorted_most_severe_first():
    prev = {"wallets": {
        "WHALE": {"cards": 1_000_000, "sol": 10, "last_sig": "a"},
        "TREASURY": {"cards": 1_585_000_000, "sol": 7, "last_sig": "a"},
    }, "market": {}}
    snaps = {
        "WHALE": {"cards": 700_000, "sol": 10, "last_sig": "a"},        # MEDIUM outflow
        "TREASURY": {"cards": 1_580_000_000, "sol": 7, "last_sig": "a"},  # CRITICAL outflow
    }
    events = rules.evaluate(prev, snaps, {"price": 0.29}, CONFIG)
    assert events[0]["severity"] == "CRITICAL"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
