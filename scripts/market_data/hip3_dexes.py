#!/usr/bin/env python3
"""List and inspect HIP-3 (builder-deployed) perp dexes.

Usage:
    python hip3_dexes.py                           # list every dex + deployer
    python hip3_dexes.py --deployer 0x...          # find the dex for a deployer
    python hip3_dexes.py <dex_name>                # detailed view of one dex
    python hip3_dexes.py <dex_name> --limits       # include perpDexLimits
    python hip3_dexes.py --auction                 # show the HIP-3 deploy auction status
    python hip3_dexes.py --json                    # raw JSON (with any of the above)

Env:
    HL_ENV=mainnet|testnet  (default: mainnet)

Notes:
    - Index 0 in the `perpDexs` response is `null` — that represents the native
      Hyperliquid perps venue. The "perp dex index" used in asset-ID math is
      that array position, so the first HIP-3 dex has index 1.
    - Asset ID formula for a HIP-3 coin:
        100000 + perp_dex_index * 10000 + index_in_dex_meta
"""
import json
import os
import sys
from urllib.request import Request, urlopen


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


def list_dexes(as_json: bool) -> int:
    dexes = info({"type": "perpDexs"})
    if as_json:
        print(json.dumps(dexes, indent=2))
        return 0

    print(f"{'idx':>3}  {'name':<10}  {'fullName':<24}  {'deployer':<44}  assets")
    for i, d in enumerate(dexes):
        if d is None:
            print(f"{i:>3}  {'(native)':<10}  {'Hyperliquid perps':<24}  {'':<44}  -")
            continue
        n = len(d.get("assetToStreamingOiCap") or [])
        print(f"{i:>3}  {d['name']:<10}  {d['fullName']:<24}  {d['deployer']:<44}  {n}")
    return 0


def find_by_deployer(addr: str, as_json: bool) -> int:
    addr = addr.lower()
    dexes = info({"type": "perpDexs"})
    matches = [
        (i, d) for i, d in enumerate(dexes)
        if d is not None and d["deployer"].lower() == addr
    ]
    if not matches:
        print(f"no HIP-3 dex deployed by {addr}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps([{"perpDexIndex": i, **d} for i, d in matches], indent=2))
        return 0
    for i, d in matches:
        print(f"perpDexIndex={i}  name={d['name']!r}  fullName={d['fullName']!r}")
        print(f"  deployer:       {d['deployer']}")
        print(f"  feeRecipient:   {d.get('feeRecipient')}")
        print(f"  oracleUpdater:  {d.get('oracleUpdater')}")
        print(f"  deployerFeeScale: {d.get('deployerFeeScale')}")
        print(f"  #assets (OI caps): {len(d.get('assetToStreamingOiCap') or [])}")
    return 0


def show_dex(name: str, include_limits: bool, as_json: bool) -> int:
    dexes = info({"type": "perpDexs"})
    idx = next((i for i, d in enumerate(dexes) if d is not None and d["name"] == name), None)
    if idx is None:
        print(f"no HIP-3 dex named {name!r} (try: python hip3_dexes.py)", file=sys.stderr)
        return 1
    dex = dexes[idx]

    meta, ctxs = info({"type": "metaAndAssetCtxs", "dex": name})
    markets = []
    for i, asset in enumerate(meta["universe"]):
        ctx = ctxs[i] if i < len(ctxs) else {}
        asset_id = 100_000 + idx * 10_000 + i
        markets.append({
            "coin": asset["name"],
            "assetId": asset_id,
            "szDecimals": asset["szDecimals"],
            "maxLeverage": asset.get("maxLeverage"),
            "onlyIsolated": asset.get("onlyIsolated", False),
            "markPx": ctx.get("markPx"),
            "midPx": ctx.get("midPx"),
            "funding": ctx.get("funding"),
            "openInterest": ctx.get("openInterest"),
            "dayNtlVlm": ctx.get("dayNtlVlm"),
        })

    limits = info({"type": "perpDexLimits", "dex": name}) if include_limits else None

    if as_json:
        print(json.dumps({"perpDexIndex": idx, "dex": dex, "markets": markets, "limits": limits}, indent=2))
        return 0

    print(f"{dex['fullName']}  (name={name!r}, perpDexIndex={idx})")
    print(f"  deployer:       {dex['deployer']}")
    print(f"  feeRecipient:   {dex.get('feeRecipient')}")
    print(f"  oracleUpdater:  {dex.get('oracleUpdater')}")
    print(f"  deployerFeeScale: {dex.get('deployerFeeScale')}")
    print()
    print(f"  {'coin':<22} {'assetId':>7} {'szD':>3} {'lev':>4} {'iso':>4}  {'mark':>14} {'funding/hr':>14} {'24hVol':>18}")
    for m in markets:
        print(
            f"  {m['coin']:<22} "
            f"{m['assetId']:>7} "
            f"{m['szDecimals']:>3} "
            f"{(m['maxLeverage'] or ''):>4} "
            f"{('Y' if m['onlyIsolated'] else ''):>4}  "
            f"{(m['markPx'] or ''):>14} "
            f"{(m['funding'] or ''):>14} "
            f"{(m['dayNtlVlm'] or ''):>18}"
        )
    print(f"  ({len(markets)} markets)")

    if limits:
        print()
        print("  perpDexLimits:")
        print(f"    totalOiCap:     {limits.get('totalOiCap')}")
        print(f"    oiSzCapPerPerp: {limits.get('oiSzCapPerPerp')}")
        print(f"    maxTransferNtl: {limits.get('maxTransferNtl')}")
    return 0


def show_auction(as_json: bool) -> int:
    status = info({"type": "perpDeployAuctionStatus"})
    if as_json:
        print(json.dumps(status, indent=2))
        return 0
    print("HIP-3 perp deploy auction")
    for k in ("startTimeSeconds", "durationSeconds", "startGas", "currentGas", "endGas"):
        print(f"  {k}: {status.get(k)}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    include_limits = "--limits" in argv

    if "--auction" in argv:
        return show_auction(as_json)

    if "--deployer" in argv:
        try:
            addr = argv[argv.index("--deployer") + 1]
        except IndexError:
            print("--deployer requires an address", file=sys.stderr)
            return 2
        return find_by_deployer(addr, as_json)

    positional = [a for a in argv if not a.startswith("--")]
    if positional:
        return show_dex(positional[0], include_limits, as_json)
    return list_dexes(as_json)


if __name__ == "__main__":
    sys.exit(main())
