#!/usr/bin/env python3
"""Print the current mid price for every Hyperliquid market.

Usage:
    python all_mids.py                    # native perps, alphabetical
    python all_mids.py BTC ETH HYPE       # just these (native)
    python all_mids.py --json             # raw JSON
    python all_mids.py --dex xyz          # all mids on the 'xyz' HIP-3 dex
    python all_mids.py --dex xyz xyz:AAPL xyz:TSLA

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
    if ":" in s:
        dex, coin = s.split(":", 1)
        return f"{dex.lower()}:{coin.upper()}"
    return s.upper()


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    dex = ""
    positional: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--dex" and i + 1 < len(argv):
            dex = argv[i + 1]
            i += 2
        elif argv[i].startswith("--"):
            i += 1
        else:
            positional.append(argv[i])
            i += 1

    filters = {normalize_coin(a) for a in positional}

    mids = info({"type": "allMids", "dex": dex})

    if filters:
        mids = {k: v for k, v in mids.items() if k in filters}

    if as_json:
        print(json.dumps(mids, indent=2))
        return 0

    if not mids:
        print("no matching coins", file=sys.stderr)
        return 1

    width = max(len(k) for k in mids)
    for coin in sorted(mids):
        print(f"{coin:<{width}}  {mids[coin]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
