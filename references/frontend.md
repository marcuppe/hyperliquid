# Building a Hyperliquid frontend

A practical orchestration guide: wire up market data, user state, and trading from a browser / desktop app. Depth on individual pieces lives in [info-api.md](info-api.md), [websocket.md](websocket.md), and [trading.md](trading.md) — this file is about how you **compose** them.

## Architecture at a glance

You'll typically run two long-lived WebSocket channels and a handful of signed `/exchange` POSTs:

```
 ┌─────────────────────────────────────────────────────────┐
 │  browser / desktop app                                  │
 │                                                         │
 │   WS #1 (market data)        WS #2 (user data)          │
 │   ─ allMids / l2Book /       ─ webData2  OR              │
 │     trades / candle / bbo      ─ orderUpdates             │
 │     / activeAssetCtx            + userFills + userEvents │
 │                                                         │
 │   HTTPS POST /info  (snapshots on reconnect)            │
 │   HTTPS POST /exchange  (signed actions)                │
 └─────────────────────────────────────────────────────────┘
                              │
                              ▼
            wss://api.hyperliquid.xyz/ws
            https://api.hyperliquid.xyz
```

Endpoints:

| Env     | REST                                   | WebSocket                              |
|---------|----------------------------------------|----------------------------------------|
| mainnet | `https://api.hyperliquid.xyz`          | `wss://api.hyperliquid.xyz/ws`         |
| testnet | `https://api.hyperliquid-testnet.xyz`  | `wss://api.hyperliquid-testnet.xyz/ws` |

Both the WS and REST are CORS-open, so a pure-browser app can talk to them directly.

---

## Market data stream

One WS connection, subscribe to whatever the UI needs. Everything is push-based; you render on message.

| UI element                            | Subscription                                         |
|---------------------------------------|------------------------------------------------------|
| Price tickers across many markets     | `allMids` (one sub, all coins)                       |
| L2 order book depth for one market    | `l2Book` with `coin`                                 |
| Top-of-book / NBBO                    | `bbo` with `coin` (cheaper than `l2Book`)            |
| Scrolling trade tape                  | `trades` with `coin`                                 |
| Candle chart                          | `candle` with `coin` + `interval`                    |
| Funding, open interest, mark/mid live | `activeAssetCtx` with `coin`                         |

Subscribe message shape (one line of JSON):

```js
ws.send(JSON.stringify({
  method: "subscribe",
  subscription: { type: "l2Book", coin: "BTC" }
}));
```

Inbound event shape: `{channel, data}`. Switch on `channel` in your handler.

**Tip: `allMids` is cheap but returns a firehose of every coin.** For a ticker grid you usually want to cache the full dict locally and re-render only the coins on screen. Don't spin up one `allMids` subscription per tile.

For HIP-3 markets (`xyz:AAPL`, `flx:CRCL`), the `coin` field takes the prefixed form. `allMids` on a specific HIP-3 dex takes the optional `dex` field (the WS takes the same `dex` semantics as the info endpoint — see [info-api.md §HIP-3](info-api.md#hip-3-builder-deployed-dexes)).

---

## User state stream

Two realistic shapes, pick one:

### Option A — `webData2` (firehose)

One subscription, one shot, everything in it. This is what the official Hyperliquid web UI uses. Payload includes positions, open orders, balances, recent fills, perp + spot margin summary, agent wallet info, and more.

```js
ws.send(JSON.stringify({
  method: "subscribe",
  subscription: { type: "webData2", user: "0x..." }
}));
```

Pros: one sub, atomic state updates, everything you need to build a portfolio view.

Cons: big payload, opaque diffs (you get the full state, not just the delta). Fine for a single-user dashboard; overkill for a trading-bot UI.

### Option B — targeted subs

For fine-grained updates:

| Sub                         | Data                                                 |
|-----------------------------|------------------------------------------------------|
| `orderUpdates`              | Order lifecycle (`open`, `filled`, `canceled`, …)    |
| `userFills`                 | Individual fills                                     |
| `userEvents`                | Funding, liquidations, `nonUserCancel`              |
| `userFundings`              | Realized funding payments                            |
| `userNonFundingLedgerUpdates` | Deposits, transfers, withdrawals                   |
| `activeAssetData` (per-coin)| Per-asset leverage / margin for this user            |

Subscribe to just the ones your UI needs. Each one pushes only that event type.

### Bootstrap + reconcile

WS gives you the *stream*, not a starting snapshot. On connect you need a one-shot `/info` call to seed state before the first WS message arrives, then merge:

```js
// 1. snapshot
const [clearinghouse, openOrders, recentFills] = await Promise.all([
  infoPost({ type: "clearinghouseState", user }),
  infoPost({ type: "frontendOpenOrders", user }),
  infoPost({ type: "userFills", user, aggregateByTime: false }),
]);
seedStore(clearinghouse, openOrders, recentFills);

// 2. stream
ws.send(JSON.stringify({
  method: "subscribe",
  subscription: { type: "webData2", user }
}));
```

Do this again after every reconnect — WS does **not** backfill missed events.

---

## Placing orders from a frontend

Writes go to `POST /exchange` with `{action, nonce, signature}`. Browser frontends have two working patterns:

### Pattern 1 — sign every action with the user's master wallet

Simplest. User clicks "Place Order" → browser builds the action → user's wallet (MetaMask, Rabby, WalletConnect) pops a signature request → on confirm, POST to `/exchange`. The `signature` field is an EIP-712 signature over an L1-action or user-signed-action payload (see below).

Upside: no extra setup, works on first visit.
Downside: a prompt per action. Fine for transfers / withdrawals, terrible for active trading.

### Pattern 2 — agent wallet (what `app.hyperliquid.xyz` does)

Approve once, sign many times — silently.

1. Browser generates an ephemeral keypair (`ethers.Wallet.createRandom()` or `viem.generatePrivateKey()`).
2. Save the private key in IndexedDB or equivalent (not localStorage — more accessible to XSS, though that's still a concern with IDB; scope it carefully).
3. User signs an `approveAgent` action *once* with their master wallet. This action registers the agent's address on-chain.
4. From then on, every trade/cancel is signed by the agent key in the background, no wallet prompt.
5. Post actions as the agent, but **set `account_address` / `vaultAddress` to the master** so the action is attributed correctly.

Agents **cannot withdraw**. That's the point — even if the agent key leaks, funds are safe. Agents expire (default ~6 months); re-approve on expiry.

```js
// one-time master-signed approval
const approveAction = {
  type: "approveAgent",
  hyperliquidChain: "Mainnet",
  signatureChainId: "0xa4b1",      // Arbitrum — required for human-readable EIP-712
  agentAddress: agentWallet.address,
  agentName: "my-frontend",
  nonce: Date.now()
};
// user-signed (EIP-712 typed data) — MetaMask will show each field
const signature = await master.signTypedData(...);
await fetch("/exchange", { method: "POST",
  body: JSON.stringify({ action: approveAction, nonce: approveAction.nonce, signature }) });

// later, silent trades:
const order = {
  type: "order",
  orders: [{ a: 0, b: true, p: "75000", s: "0.001", r: false, t: {limit: {tif: "Gtc"}} }],
  grouping: "na"
};
const nonce = Date.now();
const sig = await signL1Action(agentWallet, order, nonce, /*vaultAddress*/ null, /*expiresAfter*/ null);
await fetch("/exchange", { method: "POST",
  body: JSON.stringify({ action: order, nonce, signature: sig, vaultAddress: masterAddress }) });
```

### The two signing conventions (what `signL1Action` is doing)

Hyperliquid uses two distinct EIP-712 signing paths:

- **L1 actions** — trades, cancels, modifies, leverage updates, scheduled-cancel, TWAP. Signed as an opaque `{source, connectionId}` struct so wallets don't have to display the action contents (high-frequency). The `connectionId` is `keccak256(msgpack(action) ‖ nonce ‖ vaultAddress? ‖ expiresAfter?)`. The EIP-712 domain is `{name: "Exchange", version: "1", chainId: 1337 (or 1336 testnet), verifyingContract: "0x0"}`. The struct is `Agent(string source, bytes32 connectionId)` with `source = "a"` on mainnet, `"b"` on testnet. The `msgpack` serialization has a canonical ordering — using a non-canonical encoder is the #1 source of signature failures.

- **User-signed actions** — USDC transfers, spot transfers, withdrawals, `approveAgent`, `approveBuilderFee`, staking deposits/withdrawals. Signed as proper typed EIP-712 data with readable field names (`HyperliquidTransaction:Withdraw`, `:UsdSend`, `:SpotSend`, `:ApproveAgent`, etc.), so any wallet UI shows the user exactly what they're authorizing. Uses Arbitrum's chainId (`0xa4b1` mainnet, `0x66eee` testnet) via `signatureChainId` so hardware wallets and mobile wallets accept it.

You almost never want to hand-roll either one. Use a library.

### JS/TS SDK options

- **[`@nktkas/hyperliquid`](https://github.com/nktkas/hyperliquid)** — community TypeScript SDK covering both signing paths and the full action catalogue. The most batteries-included option for browser + Node.
- **[CCXT](https://docs.ccxt.com/)** — if you already use CCXT for other venues, Hyperliquid has an integration. Less featureful for niche actions (HIP-3, agent approvals) but works for basic trading.
- **Hyperliquid's official [Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)** — for a Node/Bun backend you can shell out to a Python sidecar, but if you're already TS you're better off with the TS SDK above.

The community SDK gives you `signL1Action(wallet, action, nonce, vaultAddress, expiresAfter)` and `signUserSignedAction(wallet, action)` — call the right one for the action you're sending.

---

## Connection resilience (the boring part that makes or breaks your app)

- **Reconnect with exponential backoff** (1s → 2s → 4s → … → cap ~30s). Drop the old socket hard, don't try to resume.
- **Re-issue every subscription after reconnect.** The server does not remember them.
- **Re-fetch snapshots on reconnect** — `clearinghouseState`, open orders, fills. Missed WS events during the disconnect are not replayed.
- **Ping every ~30s** with `{"method": "ping"}`; drop the conn if no `{"channel": "pong"}` within 60s. Some networks silently half-close TCP.
- **Clock skew**: nonces must land within `(serverTime - 2d, serverTime + 1d)`. If your user's laptop clock is way off, you'll get signed-action rejections that look mysterious. Fetch server time via any info call if you need to correct.
- **Rate limits**: ~1200 weighted requests/min per IP unauthenticated, plus a per-address credit budget keyed on volume. `reserveRequestWeight` lets you buy more if you really need it.

---

## Other things worth knowing

- **POST over WS.** You can send `/info` and `/exchange` calls through the same WebSocket instead of HTTPS to save a TCP roundtrip per request:

  ```js
  ws.send(JSON.stringify({
    method: "post", id: 42,
    request: { type: "info", payload: { type: "allMids" } }
  }));
  ```

  Response arrives as `{channel: "post", data: {id: 42, response: {…}}}`.

- **Optimistic UI**. For orders, the right pattern is: assume success, render the order immediately with a "pending" state, flip to confirmed when `orderUpdates` arrives with the matching `cloid`. Use client order IDs (`cloid`) so you can correlate even if the server reorders.

- **HIP-3 markets.** Same API, same signing. Just `dex:COIN` naming. Your app doesn't need a special code path unless you want to visually group them separately.

- **Testnet**. Flip the two URLs and the `source` byte, and everything else is identical. Testnet USDC at [app.hyperliquid-testnet.xyz/drip](https://app.hyperliquid-testnet.xyz/drip).

---

## Reference links

- [Info endpoint catalogue](info-api.md) — every read you'd ever make
- [WebSocket details](websocket.md) — every sub with its full message shape
- [Trading / signing details](trading.md) — order types, TIF, agent wallets, error catalogue
- [Deployer actions](deployer.md) — only if you're launching a token or running a dex
