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


def send_message(token, chat_id, text):
    """Low-level: send one HTML message to one chat. Honors DRY_RUN."""
    if os.environ.get("DRY_RUN") == "1":
        print(f"----- DRY_RUN -> {chat_id} -----\n{text}\n-------------------------------")
        return True
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=20,
        )
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            print(f"Telegram send to {chat_id} failed:", r.status_code, r.text[:200])
        return ok
    except Exception as e:  # noqa: BLE001 - one bad recipient shouldn't stop the rest
        print(f"Telegram send to {chat_id} errored:", e)
        return False


def broadcast(text, recipient_ids):
    """Send the same message to every recipient chat id. Returns count sent."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if os.environ.get("DRY_RUN") == "1":
        print(f"----- DRY_RUN broadcast to {len(recipient_ids)} recipient(s) -----\n"
              f"{text}\n--------------------------------------------------")
        return len(recipient_ids)
    sent = 0
    for cid in recipient_ids:
        if send_message(token, cid, text):
            sent += 1
    return sent
