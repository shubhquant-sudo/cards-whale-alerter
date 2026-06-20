# CARDS Whale Alerter 🐳

A custom Telegram bot that watches the **$CARDS** (Collector Crypt) watchlist from
the on-chain intelligence report and fires a signal when the important wallets
**sell or move funds** — interpreted through the report's own logic ("the bible").

- **Watches:** the treasury, the market maker, the dormant whales, the top whales, and the main Raydium pool's liquidity.
- **Detects:** CARDS outflows (selling/moving), SOL outflows, a dormant whale waking up, accumulation, main-pool liquidity pulls, and 1h price dumps.
- **Explains:** every alert is written by Claude (`claude-opus-4-8` by default) using `config/bible.md` — the distilled conclusions of the PDF report — so each signal comes with a plain-English read, a suggested action, and a confidence level.
- **Runs free, 24/7** via GitHub Actions (~5 min cadence). Nothing runs on your Mac.

> Research tool, not financial advice. Trading low-float, concentrated tokens is high-risk.

## How it works

```
GitHub Actions (every ~5 min)
  └─ python -m bot.monitor
       ├─ market.py     DexScreener: price, main-pool liquidity, 1h change
       ├─ solana.py     RPC: each wallet's CARDS + SOL balance + last signature
       ├─ rules.py      diff vs state.json → events @ severity (the playbook)
       ├─ claude_signal.py  event + bible.md → Claude → alert text
       └─ telegram.py   send to your chat; commit updated state.json
```

The **first run** records baselines and sends a "monitoring started" message (no
false alerts). Every later run diffs the chain against `state/state.json`.

## Setup (see the chat for the guided, step-by-step version)

1. **Telegram bot:** message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. **Chat ID:** message your new bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `result[].message.chat.id`.
3. **Anthropic key:** from the Claude Console.
4. **(Recommended) RPC:** a free [Helius](https://helius.dev) key → `RPC_URL`.
5. **Local test:**
   ```bash
   pip install -r requirements.txt
   cp .env.example .env   # fill in the values
   export $(grep -v '^#' .env | xargs)
   DRY_RUN=1 python -m bot.monitor   # prints the startup summary instead of sending
   ```
6. **Deploy:** push this folder to a new GitHub repo, add the secrets
   (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`, optional `RPC_URL`)
   under **Settings → Secrets and variables → Actions**, then enable Actions and
   run the workflow once from the **Actions** tab.

## Tests

```bash
python tests/test_rules.py
```

## Tuning

Edit `config/watchlist.json` to add/remove wallets or change thresholds
(`cards_outflow_alert` in tokens, `sol_outflow_alert` in SOL). Edit
`config/bible.md` to change how Claude reasons about events.

## Limits

- GitHub Actions cron is ~5 min minimum (can lag under load). For sub-minute
  latency, run `bot.monitor` on an always-on worker or switch to Helius webhooks.
- v1 alerts on **balance deltas** (a CARDS decrease = sell or transfer-out). It
  does not yet classify "sold on Raydium" vs "sent to a CEX" — that needs
  transaction-level parsing (a paid indexer). Both are bearish for our purposes.
