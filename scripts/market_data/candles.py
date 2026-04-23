#!/usr/bin/env python3
"""Fetch candlestick history for a Hyperliquid market.

Usage:
    python candles.py BTC 1h 24h           # 1h candles for the last 24 hours
    python candles.py ETH 15m 6h --json    # raw JSON
    python candles.py HYPE 1d 30d          # daily candles, last 30 days
    python candles.py xyz:TSLA 1h 24h      # HIP-3 market (dex:COIN)

Valid intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d, 3d, 1w, 1M.
Lookback format: <number><unit> where unit is m|h|d|w (e.g. 30m, 12h, 7d, 2w).
Server caps at 5000 candles per request.

Env:
    HL_ENV=mainnet|testnet  (default: mainnet)
"""
import json
import os
import sys
import time
from urllib.request import Request, urlopen

UNIT_MS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def base_url() -> str:
    env = os.environ.get("HL_ENV", "mainnet")
    return "https://api.hyperliquid-testnet.xyz" if env == "testnet" else "https://api.hyperliquid.xyz"


def info(payload: dict, timeout: float = 15.0):
    req = Request(
        f"{base_url()}/info",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def parse_lookback(spec: str) -> int:
    if not spec or spec[-1] not in UNIT_MS:
        raise ValueError(f"lookback must end in one of m|h|d|w, got {spec!r}")
    return int(spec[:-1]) * UNIT_MS[spec[-1]]


def normalize_coin(s: str) -> str:
    if ":" in s:
        dex, coin = s.split(":", 1)
        return f"{dex.lower()}:{coin.upper()}"
    return s.upper()


def main() -> int:
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]

    if len(args) < 2:
        print("usage: candles.py COIN INTERVAL [LOOKBACK]", file=sys.stderr)
        return 2

    coin = normalize_coin(args[0])
    interval = args[1]
    lookback_spec = args[2] if len(args) > 2 else "24h"
    lookback_ms = parse_lookback(lookback_spec)

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - lookback_ms

    candles = info({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end_ms},
    })

    if as_json:
        print(json.dumps(candles, indent=2))
        return 0

    if not candles:
        print("no candles returned", file=sys.stderr)
        return 1

    print(f"{coin}  {interval}  {len(candles)} candles  (lookback {lookback_spec})")
    print(f"{'openTime (UTC)':<20}  {'open':>12}  {'high':>12}  {'low':>12}  {'close':>12}  {'vol':>12}  {'n':>5}")
    for c in candles:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(c["t"] / 1000))
        print(f"{ts:<20}  {c['o']:>12}  {c['h']:>12}  {c['l']:>12}  {c['c']:>12}  {c['v']:>12}  {c['n']:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
