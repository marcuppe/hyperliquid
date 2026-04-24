# WebSocket reference

Real-time feeds over a single WebSocket connection. Send JSON subscribe messages, receive JSON events.

**URLs:**
- Mainnet: `wss://api.hyperliquid.xyz/ws`
- Testnet: `wss://api.hyperliquid-testnet.xyz/ws`

## Protocol

### Subscribe
```json
{"method": "subscribe", "subscription": {"type": "trades", "coin": "SOL"}}
```

### Unsubscribe
```json
{"method": "unsubscribe", "subscription": {"type": "trades", "coin": "SOL"}}
```

### Heartbeat
Send every ~30s to keep the connection alive:
```json
{"method": "ping"}
```
The server replies with `{"channel": "pong"}`.

### Message envelope
Inbound events look like:
```json
{"channel": "<type>", "data": <payload>}
```

---

## Subscription types

### Public (market data)

| Type           | Params                               | Channel name   | Data                                                                 |
|----------------|--------------------------------------|----------------|----------------------------------------------------------------------|
| `allMids`      | none                                 | `allMids`      | `{"mids": {"BTC": "...", "ETH": "...", ...}}`                        |
| `l2Book`       | `coin`, optional `nSigFigs`, `mantissa` | `l2Book`    | Same shape as the info `l2Book` response                             |
| `trades`       | `coin`                               | `trades`       | Array of `{coin, side, px, sz, time, hash, tid, users: [buyer, seller]}` |
| `bbo`          | `coin`                               | `bbo`          | Best bid/offer: `{coin, time, bbo: [bidLevel, askLevel]}`            |
| `candle`       | `coin`, `interval`                   | `candle`       | Candle object (same shape as info `candleSnapshot`), updated on close & tick |
| `activeAssetCtx` | `coin`                             | `activeAssetCtx` | Live asset context: mark, mid, funding, OI, etc.                   |

### User-scoped (no auth — they key on a public address)

| Type                            | Params                                  | Data                                                                                                                   |
|---------------------------------|-----------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| `webData3`                      | `user`                                  | Consolidated frontend state (positions + orders + balances + margin + fills). Firehose used by the Hyperliquid web UI. |
| `notification`                  | `user`                                  | System notifications (liquidation, fills, funding, deposits, etc.)                                                     |
| `userEvents`                    | `user`                                  | `{fills?: [...], funding?: {...}, liquidation?: {...}, nonUserCancel?: [...]}`                                         |
| `userFills`                     | `user`, optional `aggregateByTime`      | Array of fills (same shape as info `userFills`)                                                                        |
| `orderUpdates`                  | `user`                                  | Array of `{order, status, statusTimestamp}`                                                                            |
| `userFundings`                  | `user`                                  | Funding events as they occur                                                                                           |
| `userNonFundingLedgerUpdates`   | `user`                                  | Deposits, transfers, withdrawals                                                                                       |
| `activeAssetData`               | `user`, `coin`                          | Per-asset live data for this user (leverage, margin)                                                                   |
| `clearinghouseState`            | `user`, optional `dex`                  | Live perp clearinghouse (positions + margin summary). Same shape as the info endpoint.                                 |
| `openOrders`                    | `user`, optional `dex`                  | Live open-orders snapshot. Same shape as info `openOrders`.                                                            |
| `spotState`                     | `user`, optional `isPortfolioMargin`    | Live spot balances + margin state                                                                                      |
| `allDexsClearinghouseState`     | `user`                                  | Clearinghouse state across native + every HIP-3 dex the user has positions on. One sub, all margin contexts.           |

### TWAP

| Type                   | Params                              | Data                          |
|------------------------|-------------------------------------|-------------------------------|
| `userTwapSliceFills`   | `user`                              | TWAP slice fills              |
| `userTwapHistory`      | `user`                              | TWAP orders lifecycle         |
| `twapStates`           | `user`, optional `dex`              | Live in-flight TWAP orders    |

> **Note:** `webData2` was the previous-generation firehose and is no longer documented. Use `webData3`.

---

## Example: stream trades for HYPE

```python
import json, asyncio, websockets

async def main():
    async with websockets.connect("wss://api.hyperliquid.xyz/ws") as ws:
        await ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": "HYPE"},
        }))
        async for msg in ws:
            event = json.loads(msg)
            if event.get("channel") == "trades":
                for t in event["data"]:
                    print(t["time"], t["side"], t["sz"], "@", t["px"])

asyncio.run(main())
```

## Example: user event firehose

```python
await ws.send(json.dumps({
    "method": "subscribe",
    "subscription": {"type": "userEvents", "user": "0x..."},
}))
```

---

## Reconnect pattern

The server can drop your socket at any time. A correct client:

1. Reconnects with exponential backoff (start ~1s, cap ~30s).
2. Re-sends every active subscription after reconnect.
3. Treats any gap as data loss. For user-scoped data, re-fetch current state from `/info` (e.g. `clearinghouseState`, `openOrders`, `userFills`) after reconnecting.
4. Sends a ping every 30s and drops the connection if no reply in 60s.

The docs explicitly call this out: "all automated users should handle disconnects from the server."

## POST actions over WebSocket

You can also send info/exchange requests over the same socket to avoid extra HTTP connections:

```json
{"method": "post", "id": 1, "request": {"type": "info", "payload": {"type": "allMids"}}}
```

Response arrives as `{"channel": "post", "data": {"id": 1, "response": {...}}}`. Useful for low-latency bots. Signing rules for `exchange` are identical to the HTTP path.
