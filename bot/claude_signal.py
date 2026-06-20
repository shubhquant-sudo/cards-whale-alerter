"""Turn a detected on-chain Event into a human signal, using the PDF 'bible'.

The bible is the system context; the event is the user turn. Claude interprets
the event strictly through the bible's conclusions. If no ANTHROPIC_API_KEY is
set (or the call fails / is refused), we fall back to a deterministic template
so alerts still go out.
"""
import json
import os

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-8"

SYSTEM = (
    "You are an on-chain alert analyst for the Solana token CARDS (Collector Crypt). "
    "You are given (1) a research 'bible' with firm conclusions about this token and a "
    "signal->action playbook, and (2) a single on-chain event just detected on a watched "
    "wallet or the market. Interpret the event STRICTLY through the bible's logic. "
    "Write a short Telegram alert of at most 6 short lines, in this order: "
    "one-line headline; what happened (with the numbers given); why it matters per the "
    "bible; a suggested action; and a final line 'Confidence: Low|Medium|High'. "
    "Plain text only — no markdown headers, no bullet symbols, no preamble like 'Here is'. "
    "Use only the numbers provided; never invent data. End nothing with a sales pitch; "
    "this is research, not financial advice."
)


def _fallback(event, market):
    price = market.get("price")
    lines = [f"{event['kind']} — {event.get('label', '')}".strip(" —")]
    if event["kind"] == "CARDS_OUTFLOW":
        lines.append(f"Out: {event['amount']:,.0f} CARDS (~${event.get('usd', 0):,.0f}); "
                     f"~{event.get('remaining', 0):,.0f} left.")
        lines.append("Per bible: outflow from this actor = potential distribution/sell pressure.")
    elif event["kind"] == "CARDS_INFLOW":
        lines.append(f"In: {event['amount']:,.0f} CARDS (~${event.get('usd', 0):,.0f}).")
        lines.append("Per bible: smart-wallet accumulation — possible bullish positioning.")
    elif event["kind"] == "DORMANT_WAKE":
        lines.append("A long-dormant whale just transacted.")
        lines.append("Per bible: highest-signal event after the treasury — expect a large move.")
    elif event["kind"] == "SOL_OUTFLOW":
        lines.append(f"SOL out: {event['amount']:,.2f}.")
        lines.append("Per bible: funds moving, often a precursor to a CEX deposit/sale.")
    elif event["kind"] == "POOL_LIQUIDITY_DROP":
        lines.append(f"Main-pool liquidity -{event['pct']:.0f}% "
                     f"(${event['old']:,.0f} -> ${event['new']:,.0f}).")
        lines.append("Per bible: LP pull often precedes a dump — reduce exposure.")
    elif event["kind"] == "PRICE_DUMP":
        lines.append(f"Price {event['pct']:.1f}% in the last hour.")
        lines.append("Per bible: thin float, whale-driven — watch the watchlist for the cause.")
    if price:
        lines.append(f"Spot ~${price}.")
    lines.append("Confidence: Medium")
    return "\n".join(lines)


def render(event, bible_text, market):
    """Return alert body text for one Event."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _fallback(event, market)
    try:
        import anthropic
        client = anthropic.Anthropic()
        user = (
            "=== BIBLE ===\n" + bible_text.strip()
            + "\n\n=== MARKET NOW ===\n" + json.dumps({
                "price": market.get("price"),
                "main_liquidity_usd": market.get("main_liquidity_usd"),
                "price_change_h1": market.get("price_change_h1"),
                "market_cap": market.get("market_cap"),
            })
            + "\n\n=== EVENT JUST DETECTED ===\n" + json.dumps(event)
            + "\n\nWrite the alert now."
        )
        resp = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=600,
            output_config={"effort": "low"},
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            return _fallback(event, market)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or _fallback(event, market)
    except Exception:  # noqa: BLE001 - never let the LLM layer drop an alert
        return _fallback(event, market)
