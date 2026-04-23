#!/usr/bin/env python3
"""Funding rate history + predicted next funding for a Hyperliquid perp.

Usage:
    python funding.py BTC             # last 24h history + prediction
    python funding.py ETH 7d          # last 7 days of history
    python funding.py HYPE 24h --json
    python funding.py xyz:GOLD 24h    # HIP-3 market (dex:COIN)

Env:
    HL_ENV=mainnet|testnet  (default: mainnet)

Notes:
    - Funding accrues hourly. Rates are per-hour (not annualized).
    - To annualize, multiply by 24 * 365. An average hourly rate of 0.0001
      = 0.01% per hour ≈ 87.6% APR (funding paid by longs to shorts).
    - `predictedFundings` is only populated for coins that are listed on
      multiple venues; HIP-3 markets typically have no prediction.
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


def parse_lookback(spec: str) -> int:
    if not spec or spec[-1] not in UNIT_MS:
        raise ValueError(f"lookback must end in one of m|h|d|w, got {spec!r}")
    return int(spec[:-1]) * UNIT_MS[spec[-1]]


def normalize_coin(s: str) -> str:
    if ":" in s:
        dex, coin = s.split(":", 1)
        return f"{dex.lower()}:{coin.upper()}"
    return s.upper()


def info(payload: dict, timeout: float = 15.0):
    req = Request(
        f"{base_url()}/info",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print("usage: funding.py COIN [LOOKBACK]", file=sys.stderr)
        return 2

    coin = normalize_coin(args[0])
    lookback_spec = args[1] if len(args) > 1 else "24h"
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - parse_lookback(lookback_spec)

    history = info({"type": "fundingHistory", "coin": coin, "startTime": start_ms, "endTime": end_ms})
    predicted_raw = info({"type": "predictedFundings"})
    predicted = next(
        (venues for c, venues in predicted_raw if c == coin),
        None,
    )

    if as_json:
        print(json.dumps({"history": history, "predicted": predicted}, indent=2))
        return 0

    print(f"{coin} funding — last {lookback_spec} ({len(history)} entries)")
    if history:
        rates = [float(h["fundingRate"]) for h in history]
        avg = sum(rates) / len(rates)
        apr = avg * 24 * 365 * 100
        print(f"  avg rate: {avg:.6%} / hour  (~{apr:.2f}% APR)")
        print(f"  latest:   {history[-1]['fundingRate']} at "
              f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(history[-1]['time'] / 1000))} UTC")

    if predicted:
        print("\nPredicted next funding across venues:")
        for venue, data in predicted:
            if data is None:
                print(f"  {venue:<10} (no data)")
                continue
            rate = data.get("fundingRate")
            nxt = data.get("nextFundingTime")
            when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(nxt / 1000)) if nxt else "?"
            print(f"  {venue:<10}  rate={rate}  next={when} UTC")
    else:
        print("\n(no predicted-funding data for this coin)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
