---
name: hyperliquid
description: Query Hyperliquid — perps, spot, and HIP-3 builder-deployed dexes (XYZ stocks/commodities/FX, Felix, Ventuals, HyENA, Paragon, etc.) — for market data, user state, and live WebSocket feeds, or place orders via the Exchange endpoint. Use when the user asks about Hyperliquid prices, order books, funding rates, candles, open interest, positions, fills, portfolio, HIP-3 markets like `xyz:AAPL` or `flx:CRCL`, or wants to trade. Also includes live terminal TUI widgets (orderbook ladder, trade tape, multi-market ticker) that can pop into a floating macOS window as a desktop dashboard. Defaults to mainnet for reads, testnet for signed trade actions.
---

# Hyperliquid

Hyperliquid is an on-chain perpetuals and spot DEX. It exposes a JSON HTTP API and a WebSocket. The API is split into:

- **Info** (`POST /info`) — read-only, no auth. Market data, order books, user state, fills, funding, portfolio.
- **Exchange** (`POST /exchange`) — write actions. Every request must carry an EIP-712 signature from a private key.
- **WebSocket** (`/ws`) — real-time subscriptions (mids, book, trades, user events, fills, orders).

Base URLs:

| Env     | REST                                   | WebSocket                        |
|---------|----------------------------------------|----------------------------------|
| mainnet | `https://api.hyperliquid.xyz`          | `wss://api.hyperliquid.xyz/ws`   |
| testnet | `https://api.hyperliquid-testnet.xyz`  | `wss://api.hyperliquid-testnet.xyz/ws` |

## When to use this skill

Trigger on any of:
- "Hyperliquid", "HL", "HYPE" token, HLP (the community vault), or Hyperliquid-specific terms (perps, subaccounts, builder fees, agent wallets, HIP-3).
- Perp or spot market data: prices, book, candles, funding, open interest, volume, predicted funding.
- HIP-3 / builder-deployed dexes (e.g. XYZ stocks, Ventuals, Felix Exchange, HyENA, Paragon, dreamcash, Markets by Kinetiq, ABCDEx) and their coins in `dex:COIN` form (e.g. `xyz:AAPL`, `flx:CRCL`).
- User/account queries for a known wallet address: positions, margin summary, open orders, fills, portfolio P&L.
- Trading: place/cancel/modify orders, transfers, leverage changes, vault/staking actions.
- Building a bot, analytics dashboard, or alert system on Hyperliquid.

## Decision tree

1. **Market data only?** → use a `scripts/market_data/` script or call `/info` directly. See [references/info-api.md](references/info-api.md).
2. **HIP-3 / builder-deployed dex?** → start with `scripts/market_data/hip3_dexes.py` to enumerate or look up by deployer. Pass `--dex <name>` to `meta.py` / `all_mids.py`; for `order_book.py` / `candles.py` / `funding.py`, use `dex:COIN` form (e.g. `xyz:AAPL`). See [references/info-api.md](references/info-api.md) §"HIP-3".
3. **User/account state for a known wallet?** → `/info` endpoint, needs the address. See [references/info-api.md](references/info-api.md) §"User queries".
4. **Live / streaming data?** → WebSocket. See [references/websocket.md](references/websocket.md).
5. **Place, cancel, or modify an order?** → requires a private key. See [references/trading.md](references/trading.md) and `scripts/trading/`.
6. **Launch a spot token or run a HIP-3 dex?** → deployer-side actions on `/exchange`. See [references/deployer.md](references/deployer.md) — covers the full HIP-1/HIP-2 spot deploy sequence and every HIP-3 action (`registerAsset2`, `setOracle`, `haltTrading`, `setOpenInterestCaps`, `setFeeScale`, `setSubDeployers`, etc.).

## Safety rules (read before trading)

- **Market-data scripts default to mainnet** — that's where the real data lives.
- **Trading scripts default to testnet.** Only switch to mainnet when the user explicitly says so.
- **Never hardcode private keys.** Read them from the `HL_PRIVATE_KEY` env var or a gitignored config file.
- **Prefer agent wallets over master keys.** Agent (API) wallets can trade but cannot withdraw funds. Generate one at https://app.hyperliquid.xyz/API. Details in [references/trading.md](references/trading.md).
- **Confirm before any mainnet write action.** Print the full action (market, side, size, price, reduce-only flag) and require explicit user confirmation before signing on mainnet.
- **Do not blind-retry signed actions.** If an exchange request fails, surface the error. A retry with a stale nonce can double-fill.
- **Use the SDK for signing, not custom EIP-712 code.** The signing rules differ between trade actions and "human-readable" actions (transfers, withdrawals). The official Python SDK gets this right.

## Scripts

All scripts are standalone and runnable with `python <path>`. They read `HL_ENV` from the environment. **Market-data scripts default to `mainnet`; trading scripts default to `testnet`** — set `HL_ENV` explicitly to override.

**Market data** — no key, depends only on `requests`:

| Script                                  | What it does                                                 |
|-----------------------------------------|--------------------------------------------------------------|
| `scripts/market_data/all_mids.py`       | Snapshot of every coin's mid price (native or `--dex <name>`) |
| `scripts/market_data/order_book.py`     | L2 book (top levels) for a given coin (`BTC` or `xyz:AAPL`)   |
| `scripts/market_data/candles.py`        | Candlestick history (coin + interval + lookback)             |
| `scripts/market_data/funding.py`        | Funding rate history and predicted next funding              |
| `scripts/market_data/meta.py`           | Universe metadata (listed coins, decimals, leverage); `--dex` to scope |
| `scripts/market_data/hip3_dexes.py`     | List HIP-3 dexes, look up by deployer, inspect one dex       |

**Trading** — requires `hyperliquid-python-sdk` and `HL_PRIVATE_KEY`:

| Script                              | What it does                              |
|-------------------------------------|-------------------------------------------|
| `scripts/trading/place_order.py`    | Template limit order (testnet by default) |
| `scripts/trading/cancel_order.py`   | Cancel an order by `oid`                  |

**Live TUI widgets** — requires `rich` + `websocket-client`. See [scripts/widgets/README.md](scripts/widgets/README.md):

| Script                                   | What it shows                                                  |
|------------------------------------------|----------------------------------------------------------------|
| `scripts/widgets/ticker_tui.py`          | Multi-market card grid: price, 24h change, sparkline, funding  |
| `scripts/widgets/orderbook_tui.py`       | Live L2 ladder with colored size bars and spread in bps        |
| `scripts/widgets/tape_tui.py`            | Scrolling trade feed with rolling 1-min buy/sell/delta         |
| `scripts/widgets/launch.py`              | **macOS-only** dispatcher — spawns any widget in a new window  |

Quick launch (macOS):
```bash
python scripts/widgets/launch.py ticker BTC ETH HYPE xyz:TSLA
python scripts/widgets/launch.py orderbook xyz:AAPL
python scripts/widgets/launch.py tape BTC
```

First run prompts for Automation permission (one-time). On Linux/Windows, run widget scripts directly instead of through `launch.py`.

Env vars:
- `HL_ENV=mainnet|testnet` — default: `mainnet` for reads, `testnet` for signed actions
- `HL_PRIVATE_KEY=0x...` (required for trading scripts)
- `HL_ACCOUNT_ADDRESS=0x...` (required only when `HL_PRIVATE_KEY` is an agent wallet; set to the master wallet address)

## Installing dependencies (agent does this, not the user)

- **Market-data scripts** (`scripts/market_data/*`) — **stdlib only, no install needed**. Run them freely.
- **Widgets** (`scripts/widgets/*`) — need `rich` and `websocket-client`.
- **Trading** (`scripts/trading/*`) — need `hyperliquid-python-sdk` (pulls in `eth-account`).

Before the first widget or trading run, **install proactively** via Bash — don't wait for `ModuleNotFoundError` and make the user copy commands:

```bash
# widgets:
pip install --user --break-system-packages rich websocket-client

# trading:
pip install --user --break-system-packages hyperliquid-python-sdk
```

If the user has a venv / pyenv / uv, drop `--user --break-system-packages`. `pip install` is idempotent — re-running it when things are present is a no-op, so it's safe to run before every first-time attempt.

If a script *does* run without deps, it exits with a clear "install with: pip install …" line. When you see that in a tool result, run the suggested command and retry.

## Quick recipes

**Current mid price for BTC (perp):**
```python
import requests
r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "allMids"})
print(r.json()["BTC"])
```

**Open positions for a user:**
```python
requests.post("https://api.hyperliquid.xyz/info", json={
    "type": "clearinghouseState",
    "user": "0x...",
}).json()["assetPositions"]
```

**Last 24h funding for ETH:**
```python
import time, requests
end = int(time.time() * 1000)
start = end - 24 * 3600 * 1000
requests.post("https://api.hyperliquid.xyz/info", json={
    "type": "fundingHistory",
    "coin": "ETH",
    "startTime": start,
    "endTime": end,
}).json()
```

**L2 book for HYPE (top 5 levels):**
```python
book = requests.post("https://api.hyperliquid.xyz/info", json={
    "type": "l2Book", "coin": "HYPE", "nSigFigs": None, "mantissa": None,
}).json()
bids, asks = book["levels"]
for lvl in bids[:5]: print("bid", lvl["px"], lvl["sz"])
for lvl in asks[:5]: print("ask", lvl["px"], lvl["sz"])
```

For the full endpoint catalogue and response shapes, see [references/info-api.md](references/info-api.md).
