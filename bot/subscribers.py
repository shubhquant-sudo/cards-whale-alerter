"""Password-gated subscriptions.

Each run polls Telegram for new messages (fits the 5-min cron — no always-on
server needed). A user who sends the access password (BOT_PASSWORD) is
subscribed; /stop unsubscribes. Subscribers are stored in state/subscribers.json
and committed back by the workflow, so the list persists across runs.
"""
import json
import os
import time

import requests

from . import telegram
from .paths import ROOT

SUBS_PATH = os.path.join(ROOT, "state", "subscribers.json")


def load():
    if not os.path.exists(SUBS_PATH):
        return {"subscribers": {}, "last_update_id": 0}
    with open(SUBS_PATH) as f:
        return json.load(f)


def save(data):
    os.makedirs(os.path.dirname(SUBS_PATH), exist_ok=True)
    with open(SUBS_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def process_signups(token, password):
    """Poll getUpdates and handle subscribe / unsubscribe. Returns updated data."""
    data = load()
    offset = (data.get("last_update_id") or 0) + 1
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 0,
                    "allowed_updates": '["message"]'},
            timeout=25,
        )
        updates = (r.json() or {}).get("result", [])
    except Exception as e:  # noqa: BLE001
        print("getUpdates failed:", e)
        return data

    changed = False
    for u in updates:
        data["last_update_id"] = max(data.get("last_update_id", 0), u.get("update_id", 0))
        changed = True
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None:
            continue
        key = str(cid)
        text = (msg.get("text") or "").strip()
        low = text.lower()
        name = chat.get("username") or chat.get("first_name") or chat.get("title") or ""
        subs = data["subscribers"]

        if low in ("/stop", "stop", "unsubscribe", "/unsubscribe"):
            if key in subs:
                del subs[key]
                telegram.send_message(token, cid,
                    "🔕 Unsubscribed. Send the access password again any time to re-subscribe.")
            else:
                telegram.send_message(token, cid, "You weren't subscribed.")
        elif password and text == password:
            if key not in subs:
                subs[key] = {"name": name, "joined": int(time.time())}
                telegram.send_message(token, cid,
                    "✅ Subscribed! You'll now receive $CARDS whale alerts.\n"
                    "Send /stop any time to unsubscribe.")
            else:
                telegram.send_message(token, cid, "You're already subscribed ✅")
        elif low in ("/start", "start", "/help", "help"):
            telegram.send_message(token, cid,
                "🃏 <b>$CARDS whale alerts</b>\n"
                "Send the access password to subscribe.")
        else:
            telegram.send_message(token, cid,
                "🔒 Wrong password. Send the access password to subscribe to $CARDS whale alerts.")

    if changed:
        save(data)
    return data


def recipient_ids(owner_chat_id=None):
    """Set of chat ids to broadcast to: all subscribers plus the owner (if set)."""
    ids = set(load().get("subscribers", {}).keys())
    if owner_chat_id:
        ids.add(str(owner_chat_id))
    return ids
