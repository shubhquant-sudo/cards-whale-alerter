"""Deterministic rules engine — encodes the PDF 'bible' playbook.

Pure functions: given the previous saved state, the current snapshots, and the
current market reading, return a list of Event dicts. No network, no I/O — so it
is fully unit-testable. The Claude layer turns each Event into prose; this layer
decides WHAT fires and at WHAT severity.
"""

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}

# (role, outflow) -> severity, straight from the bible.
_OUTFLOW_SEVERITY = {
    "treasury": "CRITICAL",
    "pool": "CRITICAL",
    "dormant_whale": "HIGH",
    "market_maker": "MEDIUM",
    "whale": "MEDIUM",
}


def _ev(severity, kind, address, label, role, **detail):
    e = {"severity": severity, "kind": kind, "address": address,
         "label": label, "role": role}
    e.update(detail)
    return e


def evaluate(prev_state, snapshots, market, config):
    """Return a list of Event dicts, sorted most-severe first.

    prev_state: previously saved state dict (wallets + market).
    snapshots:  {address: {cards, sol, last_sig, last_active_ts}} current values.
    market:     {price, main_liquidity_usd, price_change_h1, ...} current values.
    config:     parsed watchlist.json.
    """
    events = []
    meta_by_addr = {w["address"]: w for w in config.get("wallets", [])}
    prev_wallets = (prev_state or {}).get("wallets", {})
    price = market.get("price") or 0.0

    # ---- per-wallet rules -------------------------------------------------
    for addr, snap in snapshots.items():
        meta = meta_by_addr.get(addr, {})
        role = meta.get("role", "whale")
        label = meta.get("label", addr[:6] + "…")
        old = prev_wallets.get(addr)
        if not old:
            continue  # no baseline yet → nothing to diff against

        cards_thr = meta.get("cards_outflow_alert", 200000)
        sol_thr = meta.get("sol_outflow_alert", 50)

        d_cards = (old.get("cards") or 0) - (snap.get("cards") or 0)  # +ve = outflow
        d_sol = (old.get("sol") or 0) - (snap.get("sol") or 0)

        # Dormant wallet waking up — highest-signal event after the treasury.
        if (role == "dormant_whale" and old.get("last_sig")
                and snap.get("last_sig") and snap["last_sig"] != old["last_sig"]):
            events.append(_ev(
                "HIGH", "DORMANT_WAKE", addr, label, role,
                note="Dormant wallet transacted after a long idle period.",
                cards=snap.get("cards"), usd=(snap.get("cards") or 0) * price))

        # CARDS outflow = selling or moving funds out.
        if d_cards >= cards_thr:
            sev = _OUTFLOW_SEVERITY.get(role, "MEDIUM")
            events.append(_ev(
                sev, "CARDS_OUTFLOW", addr, label, role,
                amount=d_cards, usd=d_cards * price, remaining=snap.get("cards")))
        # CARDS inflow = accumulation (only meaningful actors, low priority).
        elif (-d_cards) >= cards_thr and role in ("dormant_whale", "market_maker", "whale"):
            events.append(_ev(
                "INFO", "CARDS_INFLOW", addr, label, role,
                amount=-d_cards, usd=(-d_cards) * price, remaining=snap.get("cards")))

        # SOL outflow = moving funds (often a precursor to a CEX deposit/sale).
        if d_sol >= sol_thr:
            sev = "MEDIUM" if role == "treasury" else "INFO"
            events.append(_ev(sev, "SOL_OUTFLOW", addr, label, role, amount=d_sol))

    # ---- market rules -----------------------------------------------------
    prev_market = (prev_state or {}).get("market") or {}

    old_liq = prev_market.get("main_liquidity_usd")
    new_liq = market.get("main_liquidity_usd")
    if old_liq and new_liq and old_liq > 0:
        drop = (old_liq - new_liq) / old_liq
        if drop >= config.get("liq_drop_pct", 0.20):
            events.append(_ev(
                "CRITICAL", "POOL_LIQUIDITY_DROP",
                config.get("main_pool_address", ""), "Main Raydium CLMM pool", "pool",
                pct=drop * 100, old=old_liq, new=new_liq))

    # Price dump with hysteresis so it fires once per dump, not every run.
    ch = market.get("price_change_h1")
    dumped = bool(prev_market.get("price_dump_flag"))
    if ch is not None and ch <= config.get("price_dump_pct", -10.0) and not dumped:
        events.append(_ev(
            "HIGH", "PRICE_DUMP", "", "CARDS market", "market", pct=ch))

    events.sort(key=lambda e: SEVERITY_ORDER.get(e["severity"], 9))
    return events


def next_price_dump_flag(prev_state, market, config):
    """Hysteresis state for the price-dump rule (set on the way down, cleared on recovery)."""
    prev = bool(((prev_state or {}).get("market") or {}).get("price_dump_flag"))
    ch = market.get("price_change_h1")
    if ch is None:
        return prev
    if ch <= config.get("price_dump_pct", -10.0):
        return True
    if ch >= config.get("price_dump_reset_pct", -5.0):
        return False
    return prev
