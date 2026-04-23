# Trading reference

Writing to Hyperliquid means signing an action with a private key and POSTing to `/exchange`. **Always use the official SDK for signing** — there are two different signing conventions (L1 actions vs. "user-signed" actions) and getting them wrong either bricks the request or opens you up to replay.

This file covers *trader-side* actions: placing, canceling, modifying orders; transfers; leverage. For *creator-side* actions — launching a spot token (HIP-1/HIP-2) or running a HIP-3 perp dex (`registerAsset2`, `setOracle`, `haltTrading`, `setOpenInterestCaps`, fee shares, sub-deployers, etc.) — see [deployer.md](deployer.md).

**URL:**
- Mainnet: `POST https://api.hyperliquid.xyz/exchange`
- Testnet: `POST https://api.hyperliquid-testnet.xyz/exchange`

---

## Agent wallets (recommended)

Do not run bots with your master wallet private key. Hyperliquid supports **agent (API) wallets**: a separate key you approve on-chain that can place/cancel orders and manage leverage, but **cannot withdraw funds**.

### Setup
1. Generate an agent wallet at https://app.hyperliquid.xyz/API (or programmatically with `approveAgent`).
2. Name it — the name is what you'll see in the UI and in signature prompts.
3. The UI returns a private key for the agent. Treat it like an API secret.
4. Set env:
   ```bash
   export HL_PRIVATE_KEY=0x<agent_key>
   export HL_ACCOUNT_ADDRESS=0x<master_address>
   ```
   The agent signs, but the action is attributed to the master account. The SDK needs both.

### Scope
Agents can: place/cancel/modify orders, change leverage, adjust isolated margin, run TWAPs, schedule cancel-all.
Agents cannot: withdraw, transfer USDC out of the account, update builder fees, approve other agents.

Approvals expire (default 6 months). Re-approve periodically or the bot will start getting `must deposit before performing actions` errors.

---

## Using the official SDK

```bash
pip install hyperliquid-python-sdk
```

### Read-only client (no key)
```python
from hyperliquid.info import Info
from hyperliquid.utils import constants

info = Info(constants.TESTNET_API_URL, skip_ws=True)
print(info.all_mids())
print(info.user_state("0x..."))
```

### Exchange client

```python
import os
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

env = os.environ.get("HL_ENV", "testnet")
base_url = constants.MAINNET_API_URL if env == "mainnet" else constants.TESTNET_API_URL

wallet = Account.from_key(os.environ["HL_PRIVATE_KEY"])
account_address = os.environ.get("HL_ACCOUNT_ADDRESS")  # only if agent wallet

exchange = Exchange(wallet, base_url, account_address=account_address)
```

---

## Order types

Hyperliquid orders have two layers: an `orderType` and a `tif` (time in force) or trigger spec.

### Limit order
```python
exchange.order(
    name="BTC",           # coin
    is_buy=True,
    sz=0.001,
    limit_px=110000.0,
    order_type={"limit": {"tif": "Gtc"}},  # "Alo" | "Gtc" | "Ioc"
    reduce_only=False,
)
```

TIF values:
- `"Gtc"` — good-till-canceled (resting limit)
- `"Ioc"` — fill what you can now, cancel the rest (this is how you do market orders)
- `"Alo"` — add-liquidity-only; post-only. Rejected if it would cross.

### "Market" order
Hyperliquid has no distinct market type. Use `Ioc` with a price that crosses aggressively:
```python
mid = float(info.all_mids()["BTC"])
exchange.market_open(name="BTC", is_buy=True, sz=0.001, px=None, slippage=0.01)
```
The SDK's `market_open` / `market_close` helpers wrap this correctly.

### Trigger orders (stop / take-profit)
```python
exchange.order(
    name="BTC",
    is_buy=False,
    sz=0.001,
    limit_px=100000.0,    # price to submit once triggered
    order_type={"trigger": {"isMarket": True, "triggerPx": 109000.0, "tpsl": "sl"}},
    reduce_only=True,
)
```
`tpsl`: `"sl"` (stop-loss) or `"tp"` (take-profit). `isMarket`: `true` = fire an IOC at `limitPx`; `false` = fire a resting limit.

### Client order IDs
Pass `cloid="0x..."` (32-byte hex) to tag an order. Use `cancel_by_cloid` and `orderStatus` with a cloid for idempotent retries.

---

## Cancels and modifies

```python
exchange.cancel("BTC", oid=12345)
exchange.cancel_by_cloid("BTC", cloid="0x...")
exchange.modify_order(oid=12345, name="BTC", is_buy=True, sz=0.002, limit_px=109500.0,
                      order_type={"limit": {"tif": "Gtc"}}, reduce_only=False)
exchange.bulk_cancel([{"coin": "BTC", "oid": 1}, {"coin": "ETH", "oid": 2}])
```

---

## Leverage & margin

```python
exchange.update_leverage(40, "BTC", is_cross=True)
exchange.update_isolated_margin(amount=100.0, name="BTC")  # add/remove USDC on isolated
```

---

## Safety features

### Dead man's switch
Schedule a cancel-all that fires if you don't check in before a given timestamp:
```python
exchange.schedule_cancel(int(time.time() * 1000) + 60_000)  # cancel everything in 60s
exchange.schedule_cancel(None)  # clear
```
The scheduled time must be at least 5 seconds in the future. Clearing also uses the same call with `None`.

### `expiresAfter` on individual actions
Include `expiresAfter` (ms timestamp) in the nonce to make an action auto-expire. Stale `expiresAfter` consumes 5x rate limit, so don't set it too aggressive.

---

## Nonces

- Must be within `(T - 2 days, T + 1 day)` of the server clock (ms).
- Must be strictly increasing per `(account, signer)`. The SDK manages this; if you DIY, use `int(time.time() * 1000)` and keep a local counter to dodge clock skew.
- A nonce is consumed once. If a signed request was accepted, **do not retry with the same nonce** — you may double-submit if the network hiccuped after the server saw it.

---

## Rate limits

- IP-level: ~1200 weighted requests/min per IP for unauthenticated calls.
- User-level: a request-credit budget keyed on volume. Check with `/info` `userRateLimit`. Address-scoped actions consume credits from the owner.
- WebSocket: 100 subscriptions and 2000 msg/min per connection.
- `reserveRequestWeight` action lets you buy additional weight with USDC if needed.

---

## Errors to watch for

| Response                            | Meaning                                                    |
|-------------------------------------|------------------------------------------------------------|
| `"Must deposit before performing actions"` | Account unfunded or agent wallet expired/unapproved. |
| `"Reduce only order would increase position"` | Your reduce-only order's direction doesn't shrink the position. |
| `"Price must be divisible by tick size"`     | Round `limit_px` to the market's tick (see `meta`).         |
| `"Order has invalid size"`          | Size not divisible by `10 ** -szDecimals`. Round down.    |
| `"Insufficient margin"`             | Not enough free collateral — check `clearinghouseState.withdrawable`. |
| `"L1 error: Order was never placed, ..."` | Typically a signing or nonce issue. Re-init the Exchange client. |

---

## Checklist before a mainnet trade

1. Confirm `HL_ENV=mainnet` is intentional.
2. Confirm the private key is the **agent wallet**, not the master.
3. Round sizes to `szDecimals` and prices to the market tick.
4. Double-check `is_buy`, `sz` (positive), `limit_px`, and `reduce_only`.
5. Print the full action and require an explicit user confirmation.
6. On error, surface the raw response. Never auto-retry the same signed request.
