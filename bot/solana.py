"""Minimal Solana JSON-RPC helpers (read-only) using `requests`.

Tries the configured RPC_URL first (a free Helius/QuickNode key is strongly
recommended for reliability), then falls back to public endpoints.
"""
import os
import requests

_DEFAULT_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def _endpoints():
    custom = os.environ.get("RPC_URL", "").strip()
    return ([custom] if custom else []) + _DEFAULT_ENDPOINTS


def _rpc(method, params, timeout=25):
    last_err = None
    for url in _endpoints():
        try:
            r = requests.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=timeout,
            )
            data = r.json()
            if "result" in data:
                return data["result"]
            last_err = data.get("error", data)
        except Exception as e:  # noqa: BLE001 - we want to try the next endpoint
            last_err = e
    raise RuntimeError(f"RPC {method} failed on all endpoints: {last_err}")


def get_sol_balance(address):
    """SOL balance in whole SOL."""
    res = _rpc("getBalance", [address])
    return (res.get("value", 0) or 0) / 1e9


def get_cards_balance(owner, mint):
    """Sum the owner's CARDS across all its token accounts (uiAmount)."""
    res = _rpc(
        "getTokenAccountsByOwner",
        [owner, {"mint": mint}, {"encoding": "jsonParsed"}],
    )
    total = 0.0
    for acc in res.get("value", []):
        info = acc["account"]["data"]["parsed"]["info"]
        amt = info["tokenAmount"].get("uiAmount") or 0
        total += amt
    return total


def get_last_signature(address):
    """Most recent (signature, blockTime) for an address, or (None, None)."""
    res = _rpc("getSignaturesForAddress", [address, {"limit": 1}])
    if not res:
        return None, None
    top = res[0]
    return top.get("signature"), top.get("blockTime")
