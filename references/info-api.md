# Info endpoint reference

The Info endpoint is a single `POST https://api.hyperliquid.xyz/info` (or the testnet equivalent) that takes a JSON body with a `"type"` field. No auth, no signing.

All examples below show the request body only. Send as JSON, parse JSON back.

Grouped by concern:

- [Market-wide](#market-wide)
- [Per-coin market data](#per-coin-market-data)
- [HIP-3 (builder-deployed dexes)](#hip-3-builder-deployed-dexes)
- [User state — perps](#user-state--perps)
- [User state — spot](#user-state--spot)
- [User history](#user-history)
- [Orders](#orders)
- [Vaults, staking, referrals](#vaults-staking-referrals)
- [Misc](#misc)

---

## Market-wide

### `allMids` — mid price for every coin
```json
{"type": "allMids", "dex": ""}
```
Response: `{"BTC": "113400.5", "ETH": "2412.7", ...}` (all strings).

### `meta` — perp universe metadata
```json
{"type": "meta", "dex": ""}
```
Response: `{"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40, ...}], "marginTables": [...]}`.

Use this to discover listed coins and their size precision (`szDecimals`).

### `metaAndAssetCtxs` — metadata + live per-asset context
```json
{"type": "metaAndAssetCtxs", "dex": ""}
```
Response: `[metaObject, [assetCtx, ...]]` — contexts are parallel to `universe` and include `markPx`, `midPx`, `funding`, `openInterest`, `oraclePx`, `premium`, `dayNtlVlm`, `prevDayPx`.

### `spotMeta` — spot universe metadata
```json
{"type": "spotMeta"}
```
Response: `{"tokens": [...], "universe": [{"name": "PURR/USDC", "tokens": [1, 0], ...}]}`.

### `spotMetaAndAssetCtxs`
```json
{"type": "spotMetaAndAssetCtxs"}
```
Response: `[metaObject, [{midPx, markPx, dayNtlVlm, prevDayPx}, ...]]`.

### `perpsAtOpenInterestCap`
```json
{"type": "perpsAtOpenInterestCap", "dex": ""}
```
Response: `["COIN", ...]` — coins currently capped and rejecting OI-increasing orders.

### `predictedFundings` — next-hour funding prediction across venues
```json
{"type": "predictedFundings"}
```
Response: nested array, `[["AVAX", [["BinPerp", {"fundingRate": "0.0001", "nextFundingTime": ...}], ...]], ...]`.

---

## Per-coin market data

### `l2Book` — order book snapshot (up to 20 levels/side)
```json
{"type": "l2Book", "coin": "BTC", "nSigFigs": null, "mantissa": null}
```
Response: `{"coin": "BTC", "time": 1754450974231, "levels": [[bidLevel, ...], [askLevel, ...]]}` where each level is `{"px": "...", "sz": "...", "n": <count>}`.

`nSigFigs` (2–5) aggregates price precision; `mantissa` sub-buckets within a sig-fig. Pass both as `null` for the native tick.

### `candleSnapshot` — candlesticks (max 5000 per request)
```json
{"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "15m", "startTime": 1681923600000, "endTime": 1681924499999}}
```
Valid intervals: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`.

Response: `[{"t": openTs, "T": closeTs, "o": open, "h": high, "l": low, "c": close, "v": volume, "n": tradeCount, "s": coin, "i": interval}, ...]`.

### `fundingHistory` — realized funding for a coin
```json
{"type": "fundingHistory", "coin": "ETH", "startTime": 1683849600076, "endTime": 1683936000076}
```
Response: `[{"coin": "ETH", "fundingRate": "...", "premium": "...", "time": ...}, ...]`. `endTime` optional; default is now.

### `tokenDetails` — spot token info
```json
{"type": "tokenDetails", "tokenId": "0x..."}
```
Response: `{name, maxSupply, totalSupply, circulatingSupply, szDecimals, weiDecimals, midPx, markPx, prevDayPx, deployer, deployTime, ...}`.

---

## HIP-3 (builder-deployed dexes)

HIP-3 lets a third party ("deployer") stake HYPE and run an independent perp venue on Hyperliquid's infrastructure. Each venue is called a **dex**, has its own order books, margining, oracle, and fee recipient, and uses Hyperliquid's matching engine.

### `perpDexs` — list every HIP-3 dex
```json
{"type": "perpDexs"}
```
Response: `[null, dex1, dex2, ...]`. Index `0` is `null` and represents the **native** Hyperliquid perps venue. Indices `1+` are HIP-3 dexes, each:

```json
{
  "name": "xyz",
  "fullName": "XYZ",
  "deployer": "0x...",
  "oracleUpdater": "0x..." | null,
  "feeRecipient": "0x..." | null,
  "deployerFeeScale": "1.0",
  "lastDeployerFeeScaleChangeTime": "1970-01-01T00:00:00",
  "subDeployers": [["setOracle", ["0x..."]]],
  "assetToStreamingOiCap": [["xyz:AAPL", "50000000.0"], ...],
  "assetToFundingMultiplier": [["xyz:TSLA", "1.0"], ...],
  "assetToFundingInterestRate": [...]
}
```

Use this to:
- Enumerate all HIP-3 venues.
- Find the dex deployed by a specific address (`deployer` field).
- Get the array index — the **`perpDexIndex`** — needed for asset-ID math.

### `perpDexLimits` — per-dex OI and transfer caps
```json
{"type": "perpDexLimits", "dex": "xyz"}
```
Response: `{totalOiCap, oiSzCapPerPerp, maxTransferNtl, coinToOiCap: [[coin, cap], ...]}`. **`dex` must be non-empty here** — native perps don't have this notion.

### `perpDeployAuctionStatus` — Dutch auction for new listings
```json
{"type": "perpDeployAuctionStatus"}
```
Response: `{startTimeSeconds, durationSeconds, startGas, currentGas, endGas}`. The first three assets on a new dex deploy freely; after that, assets across all HIP-3 dexes compete in a shared Dutch auction denominated in HYPE.

### Querying a specific HIP-3 dex

Most info endpoints accept a `"dex"` field:

| Endpoint                          | Behavior with non-empty `dex`                      |
|-----------------------------------|----------------------------------------------------|
| `meta`, `metaAndAssetCtxs`        | Returns that dex's universe + live contexts        |
| `allMids`                         | Returns mids for that dex only, keys in `dex:COIN` format |
| `clearinghouseState`              | User's positions & margin within that dex (isolated per-dex) |
| `openOrders`, `frontendOpenOrders`| Active orders on that dex                          |
| `userAbstraction`, `userDexAbstraction` | HIP-3 abstraction state                      |
| `perpsAtOpenInterestCap`          | Coins on that dex currently at OI cap              |

Endpoints that take a single `coin` (no separate `dex`) use the **prefixed** form:

| Endpoint         | Coin format                                              |
|------------------|----------------------------------------------------------|
| `l2Book`         | `"coin": "xyz:AAPL"`                                     |
| `candleSnapshot` | `"req": {"coin": "xyz:TSLA", ...}`                       |
| `fundingHistory` | `"coin": "xyz:GOLD"`                                     |
| `orderStatus`    | Not needed — `oid` is globally unique                    |

Cross-dex endpoints that ignore the dex grouping:

| Endpoint                        | Note                                                     |
|---------------------------------|----------------------------------------------------------|
| `userFills`, `userFillsByTime`  | Returns fills across every dex; `coin` field is prefixed |
| `userFunding`                   | Cross-dex; each entry's `delta.coin` is prefixed         |
| `userNonFundingLedgerUpdates`   | Cross-dex                                                |
| `portfolio`                     | Combined account value                                   |

### Asset IDs

- Native perp: `assetId = index_in_meta` (BTC = 0, ETH = 4, …).
- HIP-3 perp: `assetId = 100_000 + perpDexIndex * 10_000 + index_in_dex_meta`.
- Spot: `assetId = 10_000 + spotInfo["index"]`.

You only need raw asset IDs when signing orders manually. The SDK takes the human-readable name (`"xyz:AAPL"`) and handles the mapping.

### Gotchas

- `perpDexs[0]` is always `null`. Don't iterate it without a skip.
- Deployer addresses in `perpDexs` come back checksummed; compare case-insensitively.
- Margin is **isolated per dex**. A user with positions on native BTC and `xyz:AAPL` has two separate clearinghouse states — fetch both.
- `predictedFundings` typically has no entries for HIP-3 coins (prediction relies on external-venue data).

---

## User state — perps

### `clearinghouseState` — positions + margin summary
```json
{"type": "clearinghouseState", "user": "0x...", "dex": ""}
```
Response: `{"assetPositions": [...], "marginSummary": {...}, "crossMarginSummary": {...}, "withdrawable": "...", "time": ...}`.

Each `assetPosition` has `type` (`"oneWay"`) and `position` with `coin`, `szi` (signed size, `-` = short), `entryPx`, `positionValue`, `unrealizedPnl`, `leverage: {type, value}`, `liquidationPx`, `marginUsed`, `returnOnEquity`, `cumFunding`.

### `userRateLimit`
```json
{"type": "userRateLimit", "user": "0x..."}
```
Response: `{"cumVlm": "...", "nRequestsUsed": N, "nRequestsCap": N, "nRequestsSurplus": N}`.

### `userFees`
```json
{"type": "userFees", "user": "0x..."}
```
Response: per-day volume, full fee schedule (maker/taker, spot, VIP/MM tiers, staking discount, referral discount), plus the user's effective rates.

### `userRole`
```json
{"type": "userRole", "user": "0x..."}
```
Response: `{"role": "user" | "agent" | "vault" | "subaccount" | "missing"}` with supporting data.

### `subAccounts`
```json
{"type": "subAccounts", "user": "0x..."}
```
Response: array of subaccounts with names, addresses, and balance summaries.

### `userAbstraction` / `userDexAbstraction`
```json
{"type": "userAbstraction", "user": "0x..."}
{"type": "userDexAbstraction", "user": "0x...", "dex": "..."}
```
HIP-3 / account-abstraction state.

### `maxBuilderFee`
```json
{"type": "maxBuilderFee", "user": "0x...", "builder": "0x..."}
```
Response: integer in tenths of a basis point (e.g. `1` = 0.001%).

### `approvedBuilders`
```json
{"type": "approvedBuilders", "user": "0x..."}
```
Response: `[{"builder": "0x...", "maxFeeRate": "..."}]`.

---

## User state — spot

### `spotClearinghouseState`
```json
{"type": "spotClearinghouseState", "user": "0x..."}
```
Response: `{"balances": [{"coin": "PURR", "token": 1, "hold": "0.0", "total": "123.4", "entryNtl": "..."}]}`.

### `spotDeployState`
```json
{"type": "spotDeployState", "user": "0x..."}
```
Response: tokens the user is currently deploying (HIP-1 auction state) plus `gasAuction` status.

### `spotPairDeployAuctionStatus`
```json
{"type": "spotPairDeployAuctionStatus"}
```
Response: the shared Dutch auction state for registering a new trading *pair* between two already-existing spot tokens (separate from the token-registration auction exposed by `spotDeployState`).

---

## User history

### `userFills` — recent fills (up to 2000)
```json
{"type": "userFills", "user": "0x...", "aggregateByTime": false}
```
Response: `[{"coin", "side": "B"|"A", "px", "sz", "time", "startPosition", "dir": "Open Long"|..., "closedPnl", "hash", "oid", "tid", "fee", "feeToken", "builderFee", "crossed"}]`.

`side`: `B` = buy/long, `A` = ask/sell/short.

### `userFillsByTime` — fills in a window (paginated)
```json
{"type": "userFillsByTime", "user": "0x...", "startTime": 1681222254710, "endTime": 1681230000000, "aggregateByTime": false}
```
Page forward by setting `startTime` to the last fill's `time + 1`.

### `userFunding` — funding payments received/paid
```json
{"type": "userFunding", "user": "0x...", "startTime": 1681222254710, "endTime": 1681308654710}
```
Response: `[{"time", "hash", "delta": {"coin", "fundingRate", "szi", "usdc"}}]`. Positive `usdc` = received.

### `userNonFundingLedgerUpdates` — everything except funding
```json
{"type": "userNonFundingLedgerUpdates", "user": "0x...", "startTime": ..., "endTime": ...}
```
Deposits, withdrawals, transfers, spot↔perp moves, vault deposits, etc.

### `userTwapSliceFills`
```json
{"type": "userTwapSliceFills", "user": "0x..."}
```
Response: TWAP sub-order fills.

### `portfolio` — account value & PnL over time
```json
{"type": "portfolio", "user": "0x..."}
```
Response: `[["day", {accountValueHistory, pnlHistory, vlm}], ["week", ...], ..., ["perpAllTime", ...]]`.

Windows: `day`, `week`, `month`, `allTime`, `perpDay`, `perpWeek`, `perpMonth`, `perpAllTime`.

---

## Orders

### `openOrders` — active orders (basic)
```json
{"type": "openOrders", "user": "0x...", "dex": ""}
```
Response: `[{"coin", "limitPx", "oid", "side", "sz", "timestamp"}]`.

### `frontendOpenOrders` — active orders + TP/SL/trigger details
```json
{"type": "frontendOpenOrders", "user": "0x...", "dex": ""}
```
Adds `orderType`, `origSz`, `reduceOnly`, `triggerPx`, `triggerCondition`, `isTrigger`, `isPositionTpsl`.

### `historicalOrders` — last 2000 orders (any status)
```json
{"type": "historicalOrders", "user": "0x..."}
```
Response: `[{"order": {...}, "status": "filled"|"canceled"|"open"|..., "statusTimestamp": ...}]`.

### `orderStatus`
```json
{"type": "orderStatus", "user": "0x...", "oid": 91490942}
```
Can also pass `"oid": "0x<cloid>"` to look up by client order ID. Response: `{"status": "order"|"unknownOid", "order": {...}}`.

---

## Vaults, staking, referrals

### `vaultDetails`
```json
{"type": "vaultDetails", "vaultAddress": "0x..."}
```
Response: vault name, leader, PnL, followers, APR, performance history.

### `userVaultEquities`
```json
{"type": "userVaultEquities", "user": "0x..."}
```
Response: `[{"vaultAddress", "equity", "lockedUntil"}]`.

### `delegations`
```json
{"type": "delegations", "user": "0x..."}
```
Response: `[{"validator", "amount", "lockedUntilTimestamp"}]`.

### `delegatorSummary`
```json
{"type": "delegatorSummary", "user": "0x..."}
```
Response: total delegated, pending withdrawal, reward balance.

### `delegatorHistory` / `delegatorRewards`
```json
{"type": "delegatorHistory", "user": "0x..."}
{"type": "delegatorRewards", "user": "0x..."}
```

### `referral`
```json
{"type": "referral", "user": "0x..."}
```
Response: referrer chain, referred users, fee rewards.

---

## Misc

### `borrowLendUserState`
```json
{"type": "borrowLendUserState", "user": "0x..."}
```
Per-asset borrow/lend positions and health factor.

### `borrowLendReserveState`
```json
{"type": "borrowLendReserveState"}
```
Protocol-wide reserves, utilization, rates.

### `alignedQuoteTokenInfo`
```json
{"type": "alignedQuoteTokenInfo"}
```

---

## Tips

- **Prices are strings.** Convert with `Decimal` or `float`; never compare with `==`.
- **Timestamps are ms since epoch.** `int(time.time() * 1000)`.
- **User addresses are lowercased 0x-prefixed hex.** API rejects checksummed input in some versions — lowercase to be safe.
- **Default `dex: ""`** means the canonical Hyperliquid book. Non-empty values are for HIP-3 builder-deployed perps.
- **Rate limits are per-IP for unauthenticated calls** and per-user for address-scoped calls. Check `userRateLimit` if you're running into 429s.
- **Paginate fills by time**, not by offset. Each page, set the new `startTime` to `last_fill["time"] + 1`.
