#!/usr/bin/env python3
"""Print the top N levels of a Hyperliquid order book.

Usage:
    python order_book.py BTC            # native perp, top 10 per side (default)
    python order_book.py HYPE 5         # top 5 per side
    python order_book.py BTC 10 --json  # raw JSON
    python order_book.py xyz:AAPL 5     # HIP-3 market (dex:COIN)

Env:
    HL_ENV=mainnet|testnet  (default: mainnet)
"""
import json
import os
import sys
from urllib.request import Request, urlopen


def base_url() -> str:
    env = os.environ.get("HL_ENV", "mainnet")
    return "https://api.hyperliquid-testnet.xyz" if env == "testnet" else "https://api.hyperliquid.xyz"


def info(payload: dict, timeout: float = 10.0):
    req = Request(
        f"{base_url()}/info",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def normalize_coin(s: str) -> str:
    # HIP-3 markets are "<dex>:<COIN>"; dex is lowercase, coin is upper.
    if ":" in s:
        dex, coin = s.split(":", 1)
        return f"{dex.lower()}:{coin.upper()}"
    return s.upper()


def main() -> int:
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print("usage: order_book.py COIN [DEPTH]", file=sys.stderr)
        return 2

    coin = normalize_coin(args[0])
    depth = int(args[1]) if len(args) > 1 else 10

    book = info({"type": "l2Book", "coin": coin, "nSigFigs": None, "mantissa": None})

    if as_json:
        print(json.dumps(book, indent=2))
        return 0

    levels = book.get("levels") or [[], []]
    bids, asks = levels[0][:depth], levels[1][:depth]

    print(f"{coin}  t={book.get('time')}")
    print(f"{'px':>14}  {'sz':>14}  {'n':>4}   side")
    for lvl in reversed(asks):
        print(f"{lvl['px']:>14}  {lvl['sz']:>14}  {lvl['n']:>4}   ask")
    if bids and asks:
        best_bid = float(bids[0]["px"])
        best_ask = float(asks[0]["px"])
        spread = best_ask - best_bid
        spread_bps = spread / ((best_bid + best_ask) / 2) * 10_000
        print(f"{'':>14}  {'':>14}  {'':>4}   --- spread {spread:.6g} ({spread_bps:.2f} bps)")
    for lvl in bids:
        print(f"{lvl['px']:>14}  {lvl['sz']:>14}  {lvl['n']:>4}   bid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
