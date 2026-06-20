"""Send formatted alerts to Telegram (or print them in DRY_RUN mode)."""
import html
import os
import requests

EMOJI = {"CRITICAL": "\U0001F534", "HIGH": "\U0001F7E0",
         "MEDIUM": "\U0001F7E1", "INFO": "\U0001F7E2"}

MINT = "CARDSccUMFKoPRZxt5vt3ksUbxEFEcnZ3H2pd3dKxYjp"


def format_message(event, body_text):
    sev = event.get("severity", "INFO")
    emoji = EMOJI.get(sev, "ℹ️")
    label = html.escape(event.get("label", ""))
    addr = event.get("address", "")
    body = html.escape(body_text)

    parts = [f"{emoji} <b>{sev} · {html.escape(event.get('kind', ''))}</b>"]
    if label:
        parts.append(label)
    if addr:
        parts.append(f"<code>{html.escape(addr)}</code>")
    parts.append("")
    parts.append(body)
    parts.append("")
    links = [f'<a href="https://dexscreener.com/solana/{MINT}">chart</a>']
    if addr:
        links.insert(0, f'<a href="https://solscan.io/account/{addr}">wallet</a>')
    parts.append("\U0001F517 " + " · ".join(links))
    return "\n".join(parts)


def send(text):
    """Send one HTML message. Honors DRY_RUN=1 (prints instead of sending)."""
    if os.environ.get("DRY_RUN") == "1":
        print("----- DRY_RUN message -----\n" + text + "\n---------------------------")
        return True
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text,
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=20,
    )
    ok = r.ok and r.json().get("ok", False)
    if not ok:
        print("Telegram send failed:", r.status_code, r.text[:300])
    return ok
