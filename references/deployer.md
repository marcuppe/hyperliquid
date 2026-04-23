# Deployer actions

Creator-side actions on the `/exchange` endpoint. Two families:

- **HIP-1 / HIP-2** — launch a spot token + trading pair
- **HIP-3** — launch (and run) your own perp dex

Every action here is signed like any L1 exchange action — nonce + signature + action. Use the SDK; the sign path is the same as for trades.

**Prereqs / notes:**
- All tuple arrays (`[[coin, value], …]`) in these actions **must be lexographically sorted by key** before signing, or the signature won't verify.
- Deployer can delegate narrow permissions to other wallets via `setSubDeployers` (HIP-3 only).
- Gas auction state: query via info endpoint (`perpDeployAuctionStatus`, `spotDeployState`, `spotPairDeployAuctionStatus`).

---

## HIP-1 / HIP-2 — launch a spot token

Five required steps in order, plus optional extras. Every action uses `type: "spotDeploy"` with a different variant object inside.

### 1. `registerToken2` — create the token

```json
{
  "type": "spotDeploy",
  "registerToken2": {
    "spec": {"name": "PURR", "szDecimals": 0, "weiDecimals": 5},
    "maxGas": 1000000000000,
    "fullName": "Purr Coin"
  }
}
```

- `maxGas`: your bid ceiling for the gas auction (8-decimal wei HYPE). Query `spotDeployState` first for the current gas price.
- `weiDecimals`: underlying precision (stored in the ledger).
- `szDecimals`: size precision for orders (must be ≤ `weiDecimals`).

Returns a `token` index you'll use in every subsequent step.

### 2. `userGenesis` — distribute initial balances (can call 0+ times)

```json
{
  "type": "spotDeploy",
  "userGenesis": {
    "token": 42,
    "userAndWei": [["0xabc...", "100000000000"], ["0xdef...", "50000000000"]],
    "existingTokenAndWei": [[1, "25000000000"]],
    "blacklistUsers": [["0xbad...", true]]
  }
}
```

- `userAndWei`: wallet → wei amount, each entry in wei (respects `weiDecimals`).
- `existingTokenAndWei`: pro-rata distribution keyed on holders of another token.
- `blacklistUsers`: wallets excluded from `existingTokenAndWei` distributions.
- Call as many times as needed to load all balances. Each call's totals are validated against the `maxSupply` checksum in step 3.

### 3. `genesis` — finalize supply

```json
{
  "type": "spotDeploy",
  "genesis": {
    "token": 42,
    "maxSupply": "1000000000000",
    "noHyperliquidity": false
  }
}
```

- `maxSupply`: total wei across all `userGenesis` calls — must match exactly.
- `noHyperliquidity: true` if you don't want on-book market making seeded in step 5; step 5 must then set `nOrders: 0`.

### 4. `registerSpot` — create the trading pair

```json
{
  "type": "spotDeploy",
  "registerSpot": {"tokens": [42, 0]}
}
```

`[42, 0]` = your token (base) paired against token `0` (USDC). Pairs between two existing non-USDC tokens go through their own independent Dutch auction (query `spotPairDeployAuctionStatus`).

### 5. `registerHyperliquidity` — seed market-maker liquidity

```json
{
  "type": "spotDeploy",
  "registerHyperliquidity": {
    "spot": 107,
    "startPx": "0.05",
    "orderSz": "1000",
    "nOrders": 50,
    "nSeededLevels": 10
  }
}
```

- `spot`: the spot market index from step 4.
- `startPx`, `orderSz`, `nOrders`: Hyperliquidity's laddered orders across price levels.
- `nSeededLevels`: how many levels already have resting liquidity (optional).
- If `noHyperliquidity: true` was set in step 3, `nOrders` **must** be `0`.

### Optional extras

#### `setDeployerTradingFeeShare` — your cut of trading fees

```json
{
  "type": "spotDeploy",
  "setDeployerTradingFeeShare": {
    "token": 42,
    "share": "10%"
  }
}
```

Range `"0%"`–`"100%"` (default `"100%"`). You can lower it later; you can't raise it.

#### `enableQuoteToken` / `enableAlignedQuoteToken`

```json
{"type": "spotDeploy", "enableQuoteToken": {"token": 42}}
{"type": "spotDeploy", "enableAlignedQuoteToken": {"token": 42}}
```

Marks your token as usable as a *quote* asset in other pairs (e.g. `FOO/PURR`).

---

## HIP-3 — launch and run a perp dex

Requires the deployer wallet to be staking **500k HYPE** on mainnet (may drop over time). Every action here uses `type: "perpDeploy"`.

### 1. `registerAsset2` — first-time dex init + first asset

```json
{
  "type": "perpDeploy",
  "registerAsset2": {
    "maxGas": 500000000000,
    "assetRequest": {
      "coin": "AAPL",
      "szDecimals": 3,
      "oraclePx": "268.15",
      "marginTableId": 1,
      "marginMode": "normal"
    },
    "dex": "xyz",
    "schema": {
      "fullName": "XYZ",
      "collateralToken": 0,
      "oracleUpdater": "0xabc..."
    }
  }
}
```

- First call for a new dex **must** include `schema`. Subsequent asset registrations on the same dex omit it.
- `marginMode`: `"normal"` | `"strictIsolated"` | `"noCross"`.
- `collateralToken`: spot-token index used as margin (typically `0` for USDC).
- `oracleUpdater`: wallet allowed to call `setOracle` (defaults to the deployer).
- First three assets per dex are free; further assets go through the shared HIP-3 Dutch auction (`perpDeployAuctionStatus`).

`registerAsset` (no `2`) is the older variant; use `registerAsset2`.

### 2. `setOracle` — update oracle + mark prices

```json
{
  "type": "perpDeploy",
  "setOracle": {
    "dex": "xyz",
    "oraclePxs": [["AAPL", "268.15"], ["TSLA", "390.22"]],
    "markPxs": [[["AAPL", "268.16"]], [["TSLA", "390.25"]]],
    "externalPerpPxs": [["AAPL", "268.17"]]
  }
}
```

- Callable by the deployer or the `oracleUpdater`.
- **Minimum 2.5 seconds between calls per dex.**
- Mark-price moves are clamped to ±1% from the previous `markPx`.
- `oraclePxs` / `externalPerpPxs` arrays must be lexographically sorted.

### 3. `haltTrading` — pause/resume an asset

```json
{
  "type": "perpDeploy",
  "haltTrading": {"coin": "AAPL", "isHalted": true}
}
```

Also the mechanism for settling dated contracts — halt, then re-register the slot with different specs.

### 4. Funding configuration

```json
{"type": "perpDeploy", "setFundingMultipliers": [["AAPL", "1.0"], ["TSLA", "2.0"]]}
{"type": "perpDeploy", "setFundingInterestRates": [["AAPL", "0.0003"]]}
```

- `setFundingMultipliers`: scale factor `0`–`10`.
- `setFundingInterestRates`: 8-hour rate, `-0.01`–`0.01`.

### 5. Risk and fees

```json
{"type": "perpDeploy", "setOpenInterestCaps": [["AAPL", 100000000]]}
{"type": "perpDeploy", "setMarginTableIds": [["AAPL", 1]]}
{"type": "perpDeploy", "setMarginModes": [["AAPL", "strictIsolated"]]}
{"type": "perpDeploy", "setFeeRecipient": {"dex": "xyz", "feeRecipient": "0xabc..."}}
{"type": "perpDeploy", "setFeeScale": {"dex": "xyz", "scale": "1.5"}}
```

- `setOpenInterestCaps`: per-asset notional cap. **Minimum 1,000,000 or half current OI**, whichever is larger.
- `setFeeScale`: range `0.0`–`3.0`. **Mainnet: one change per 30 days.**
- `setMarginModes`: tighten (not loosen) margin rules. `"strictIsolated"` blocks withdrawing margin while a position is open.

### 6. Growth mode and metadata

```json
{"type": "perpDeploy", "setGrowthModes": [["AAPL", true]]}
{
  "type": "perpDeploy",
  "setPerpAnnotation": {
    "coin": "AAPL",
    "category": "Stocks",
    "description": "Apple Inc. perpetual",
    "displayName": "AAPL",
    "keywords": ["tech", "stocks"]
  }
}
```

- `setGrowthModes`: once-per-30-days.
- `setPerpAnnotation`: `category` ≤ 15 chars, `description` ≤ 400, `displayName` ≤ 9, `keywords` ≤ 2 items of ≤ 10 chars each.

### 7. Delegate narrow permissions — `setSubDeployers`

```json
{
  "type": "perpDeploy",
  "setSubDeployers": {
    "dex": "xyz",
    "subDeployers": [
      {"variant": "setOracle", "user": "0xoracle...", "allowed": true}
    ]
  }
}
```

Grants a specific wallet the right to execute one action variant on your dex (e.g. a dedicated oracle-pusher bot). Only the deployer can call this.

---

## Querying state during deployment

From the `/info` endpoint (no signing required):

| Query                              | Use                                                        |
|------------------------------------|------------------------------------------------------------|
| `spotDeployState`                  | Current HIP-1 gas auction + your in-flight token states    |
| `spotPairDeployAuctionStatus`      | Gas auction for adding pairs between existing spot tokens  |
| `perpDeployAuctionStatus`          | Shared HIP-3 Dutch auction for new perp assets             |
| `perpDexs`                         | All HIP-3 dexes (to find your own `perpDexIndex` + view your settings) |
| `perpDexLimits` (`dex` required)   | Live OI caps, transfer limits for a given dex              |

---

## Safety rules for deployer ops

- **Dry-run on testnet first.** Testnet has the same action shapes; burn your mistakes there.
- **Keep the deployer key cold.** The trading/agent-wallet pattern doesn't apply here — deployer actions need the actual deployer key. Sign locally; never ship the key to a hosted runner.
- **Rate-limit your own `setOracle`**. 2.5s enforced; respect it or you'll get rejections and eat rate-limit weight.
- **Don't leak keys in `fullName`, `description`, or other free-text fields**. These are stored on-chain-visible state.
- **Sort your tuples.** Every array-of-pairs action fails signing verification if unsorted. The SDK handles this; DIY code forgets.
- **Watch the cooldowns.** `setFeeScale`, `setGrowthModes` are one-change-per-30-days on mainnet. Plan the change.

---

## SDK coverage

The Python SDK exposes `Exchange.perp_deploy(...)` and `Exchange.spot_deploy(...)` with variant helpers that map to each action above. Check the [signing module](https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/main/hyperliquid/utils/signing.py) to see how the nested variants serialize. For anything not yet wrapped, you can drop to `Exchange._post_action(...)` with the raw dict.

---

## Links

- [HIP-1/2 spot deploy docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/deploying-hip-1-and-hip-2-assets)
- [HIP-3 deployer actions docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions)
- [HIP-3 overview (why dexes exist)](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals)
