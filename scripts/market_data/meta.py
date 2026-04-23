#!/usr/bin/env python3
"""Dump Hyperliquid universe metadata (perps + spot).

Usage:
    python meta.py                      # native perps + spot summary
    python meta.py perps                # native perps only
    python meta.py spot                 # spot only
    python meta.py perps --json         # raw JSON
    python meta.py perps BTC ETH        # filter native perps universe
    python meta.py --dex xyz            # a HIP-3 dex's perp universe
    python meta.py --dex xyz xyz:AAPL   # filter within that dex

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


def show_perps(filters: set[str], as_json: bool, dex: str = "") -> None:
    meta, ctxs = info({"type": "metaAndAssetCtxs", "dex": dex})
    universe = meta["universe"]
    rows = []
    for i, asset in enumerate(universe):
        if filters and normalize_coin(asset["name"]) not in filters:
            continue
        ctx = ctxs[i] if i < len(ctxs) else {}
        rows.append({
            "coin": asset["name"],
            "szDecimals": asset["szDecimals"],
            "maxLeverage": asset.get("maxLeverage"),
            "markPx": ctx.get("markPx"),
            "midPx": ctx.get("midPx"),
            "funding": ctx.get("funding"),
            "openInterest": ctx.get("openInterest"),
            "dayNtlVlm": ctx.get("dayNtlVlm"),
            "onlyIsolated": asset.get("onlyIsolated", False),
        })

    if as_json:
        print(json.dumps(rows, indent=2))
        return

    print(f"{'coin':<10} {'szDec':>5} {'maxLev':>6} {'mark':>12} {'mid':>12} {'funding/hr':>14} {'OI':>14} {'24hVol':>16}")
    for r in rows:
        print(
            f"{r['coin']:<10} "
            f"{r['szDecimals']:>5} "
            f"{(r['maxLeverage'] or ''):>6} "
            f"{(r['markPx'] or ''):>12} "
            f"{(r['midPx'] or ''):>12} "
            f"{(r['funding'] or ''):>14} "
            f"{(r['openInterest'] or ''):>14} "
            f"{(r['dayNtlVlm'] or ''):>16}"
        )
    label = f"{dex!r} dex" if dex else "native"
    print(f"({len(rows)} {label} perp markets)")


def show_spot(filters: set[str], as_json: bool) -> None:
    meta, ctxs = info({"type": "spotMetaAndAssetCtxs"})
    universe = meta["universe"]
    tokens = {t["index"]: t for t in meta["tokens"]}

    rows = []
    for i, pair in enumerate(universe):
        name = pair["name"]
        if filters and normalize_coin(name) not in filters:
            continue
        ctx = ctxs[i] if i < len(ctxs) else {}
        base_idx, quote_idx = pair["tokens"]
        rows.append({
            "name": name,
            "base": tokens.get(base_idx, {}).get("name"),
            "quote": tokens.get(quote_idx, {}).get("name"),
            "markPx": ctx.get("markPx"),
            "midPx": ctx.get("midPx"),
            "prevDayPx": ctx.get("prevDayPx"),
            "dayNtlVlm": ctx.get("dayNtlVlm"),
        })

    if as_json:
        print(json.dumps(rows, indent=2))
        return

    print(f"{'pair':<18} {'base':<10} {'quote':<8} {'mark':>14} {'mid':>14} {'prevDay':>14} {'24hVol':>16}")
    for r in rows:
        print(
            f"{r['name']:<18} "
            f"{(r['base'] or ''):<10} "
            f"{(r['quote'] or ''):<8} "
            f"{(r['markPx'] or ''):>14} "
            f"{(r['midPx'] or ''):>14} "
            f"{(r['prevDayPx'] or ''):>14} "
            f"{(r['dayNtlVlm'] or ''):>16}"
        )
    print(f"({len(rows)} spot markets)")


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

    target = "both"
    if positional and positional[0].lower() in {"perps", "spot", "both"}:
        target = positional[0].lower()
        positional = positional[1:]
    if dex:
        target = "perps"  # HIP-3 is perps-only
    filters = {normalize_coin(a) for a in positional}

    if target in ("both", "perps"):
        show_perps(filters, as_json, dex=dex)
        if target == "both":
            print()
    if target in ("both", "spot"):
        show_spot(filters, as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
