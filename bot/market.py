"""DexScreener market data: price, deepest-pool liquidity, 1h price change."""
import requests

DEXSCREENER = "https://api.dexscreener.com/latest/dex/tokens/{}"


def get_market(mint, timeout=20):
    """Return {price, main_liquidity_usd, price_change_h1, market_cap, fdv}.

    'main' = the single pair with the deepest USD liquidity (the price-setting
    pool — ~80% of CARDS liquidity sits in one Raydium CLMM/USDC pool).
    """
    r = requests.get(DEXSCREENER.format(mint), timeout=timeout)
    pairs = (r.json() or {}).get("pairs") or []
    if not pairs:
        return {"price": None, "main_liquidity_usd": None,
                "price_change_h1": None, "market_cap": None, "fdv": None}

    def liq(p):
        return ((p.get("liquidity") or {}).get("usd")) or 0

    main = max(pairs, key=liq)
    price = main.get("priceUsd")
    return {
        "price": float(price) if price is not None else None,
        "main_liquidity_usd": liq(main),
        "price_change_h1": (main.get("priceChange") or {}).get("h1"),
        "market_cap": main.get("marketCap"),
        "fdv": main.get("fdv"),
    }
