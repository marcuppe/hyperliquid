#!/usr/bin/env python3
"""Cancel a Hyperliquid order by oid.

Usage:
    python cancel_order.py COIN OID

Env:
    HL_ENV=testnet|mainnet  (default: testnet)
    HL_PRIVATE_KEY=0x...    (required — use an agent wallet)
    HL_ACCOUNT_ADDRESS=0x...  (required if HL_PRIVATE_KEY is an agent wallet)

Example:
    HL_ENV=testnet HL_PRIVATE_KEY=0x... \\
        python cancel_order.py BTC 91490942
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
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    coin = args[0].upper()
    try:
        oid = int(args[1])
    except ValueError:
        print(f"OID must be an integer, got {args[1]!r}", file=sys.stderr)
        return 2

    env = os.environ.get("HL_ENV", "testnet")
    base_url = constants.MAINNET_API_URL if env == "mainnet" else constants.TESTNET_API_URL

    pk = os.environ.get("HL_PRIVATE_KEY")
    if not pk:
        print("HL_PRIVATE_KEY is required", file=sys.stderr)
        return 2
    account_address = os.environ.get("HL_ACCOUNT_ADDRESS") or None

    wallet = Account.from_key(pk)

    print(f"[{env}] cancel {coin} oid={oid}  signer={wallet.address}")
    if env == "mainnet":
        confirm = input("Type 'yes' to cancel on MAINNET: ").strip().lower()
        if confirm != "yes":
            print("aborted.")
            return 1

    exchange = Exchange(wallet, base_url, account_address=account_address)
    result = exchange.cancel(coin, oid)
    print("response:", result)

    if (result or {}).get("status") != "ok":
        return 1
    statuses = result["response"]["data"]["statuses"]
    for s in statuses:
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
