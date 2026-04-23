#!/usr/bin/env python3
"""Place a single limit order on Hyperliquid.

Usage:
    python place_order.py COIN SIDE SIZE PRICE [TIF] [--reduce-only]

    COIN     Market name (e.g. BTC, HYPE, ETH)
    SIDE     buy | sell
    SIZE     Order size in base units (e.g. 0.001)
    PRICE    Limit price (e.g. 110000)
    TIF      Gtc | Ioc | Alo   (default: Gtc)

Env:
    HL_ENV=testnet|mainnet  (default: testnet)
    HL_PRIVATE_KEY=0x...    (required — use an agent wallet, not your master key)
    HL_ACCOUNT_ADDRESS=0x...  (required if HL_PRIVATE_KEY is an agent wallet)

Safety:
    - Defaults to testnet.
    - On mainnet, prints the full action and requires explicit 'yes' confirmation.
    - Does not retry on error. If the call fails, inspect the response and
      decide what to do; a blind retry can double-fill.

Example:
    HL_ENV=testnet HL_PRIVATE_KEY=0x... \\
        python place_order.py BTC buy 0.001 100000 Gtc
"""
import os
import sys

try:
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
except ImportError as e:
    sys.stderr.write(
        "\nerror: missing dependency — hyperliquid-python-sdk not installed.\n"
        "install with:  pip install --user --break-system-packages hyperliquid-python-sdk\n"
        "(on a venv or pyenv, drop --user --break-system-packages)\n"
        f"(ImportError: {e})\n\n"
    )
    sys.exit(127)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    reduce_only = "--reduce-only" in sys.argv[1:]

    if len(args) < 4:
        print(__doc__, file=sys.stderr)
        return 2

    coin = args[0].upper()
    side = args[1].lower()
    if side not in {"buy", "sell"}:
        print(f"SIDE must be 'buy' or 'sell', got {side!r}", file=sys.stderr)
        return 2
    is_buy = side == "buy"
    size = float(args[2])
    price = float(args[3])
    tif = args[4] if len(args) > 4 else "Gtc"
    if tif not in {"Gtc", "Ioc", "Alo"}:
        print(f"TIF must be Gtc | Ioc | Alo, got {tif!r}", file=sys.stderr)
        return 2

    env = os.environ.get("HL_ENV", "testnet")
    base_url = constants.MAINNET_API_URL if env == "mainnet" else constants.TESTNET_API_URL

    pk = os.environ.get("HL_PRIVATE_KEY")
    if not pk:
        print("HL_PRIVATE_KEY is required", file=sys.stderr)
        return 2
    account_address = os.environ.get("HL_ACCOUNT_ADDRESS") or None

    wallet = Account.from_key(pk)

    print("=" * 60)
    print(f"  env:     {env}")
    print(f"  signer:  {wallet.address}")
    if account_address:
        print(f"  account: {account_address}  (agent wallet signs on its behalf)")
    print(f"  action:  {'BUY ' if is_buy else 'SELL'} {size} {coin} @ {price}  TIF={tif}"
          f"{'  reduce-only' if reduce_only else ''}")
    print("=" * 60)

    if env == "mainnet":
        confirm = input("Type 'yes' to submit this order on MAINNET: ").strip().lower()
        if confirm != "yes":
            print("aborted.")
            return 1

    exchange = Exchange(wallet, base_url, account_address=account_address)
    result = exchange.order(
        name=coin,
        is_buy=is_buy,
        sz=size,
        limit_px=price,
        order_type={"limit": {"tif": tif}},
        reduce_only=reduce_only,
    )

    print("response:", result)

    status = (result or {}).get("status")
    if status != "ok":
        print("order failed; do not retry blindly — inspect the response above.", file=sys.stderr)
        return 1

    statuses = result["response"]["data"]["statuses"]
    for s in statuses:
        if "resting" in s:
            print(f"resting  oid={s['resting']['oid']}")
        elif "filled" in s:
            f = s["filled"]
            print(f"filled   oid={f['oid']}  sz={f['totalSz']}  avgPx={f['avgPx']}")
        elif "error" in s:
            print(f"error    {s['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
