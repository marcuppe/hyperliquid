# hyperliquid (agent skill)

An agent skill for [Hyperliquid](https://hyperliquid.xyz) — the on-chain perps + spot DEX. Drop it into Claude Code or any Claude Agent SDK setup and the agent will know how to:

- Pull market data for native perps and spot: mids, L2 books, candles, funding (realized + predicted), open interest, 24h volume
- Query and inspect **HIP-3 builder-deployed dexes** (XYZ stocks/commodities/FX, Felix, Ventuals, HyENA, Markets by Kinetiq, ABCDEx, dreamcash, Paragon) and their `dex:COIN` markets like `xyz:AAPL` or `xyz:GOLD` — list all dexes, look up by deployer address, inspect any dex's markets + OI caps
- Query user state for any wallet address: positions, margin summary, open orders, fills, portfolio history
- Subscribe to live data via WebSocket (trades, L2 updates, user events)
- Place and cancel orders via the Exchange endpoint — testnet by default, mainnet requires explicit opt-in + confirmation, with agent-wallet guidance so you don't hand a bot your master key
- Launch **live TUI widgets** (`orderbook`, `ticker`, `tape`) in a floating terminal window on macOS — HL-mint colored L2 ladder, multi-market price cards with sparklines + funding, and a scrolling trade tape with rolling flow delta. Works with native coins *and* HIP-3 markets.

Example prompts once it's installed:

- *"What's BTC doing on Hyperliquid?"*
- *"Pull the last 7 days of funding for ETH."*
- *"Which HIP-3 dex is deployed by `0x88806a71d…`?"*
- *"Show me a live orderbook for `xyz:TSLA`."*
- *"Spawn a ticker with BTC, ETH, HYPE, and `xyz:GOLD`."*

## Install

One line — add the skill to your agent and you're done:

```bash
npx skills add marcuppe/hyperliquid
```

Or clone into your `.claude/skills/` (Claude Code) or agent's skills directory.

> **Note on the install-time security audit.** `skills.sh` runs an automated
> audit that currently flags this skill as `CRITICAL`. If you read the
> audit's own analysis text, it says the opposite — it confirms the package
> only calls Hyperliquid's official API, handles private keys via env vars,
> escapes all subprocess arguments with `shlex.quote`, and fetches only
> well-known PyPI dependencies. The CRITICAL verdict appears to be a
> rule-based false positive triggered by two things intrinsic to the skill:
> (1) Hyperliquid's API lives on a `.xyz` TLD, which several domain
> reputation feeds flag on principle; and (2) the trading script combines
> private-key reading with a network call to an exchange endpoint — the
> *shape* of key-stealing malware, even though this code sends signed
> orders you explicitly authored. The audit doesn't expose which file or
> which URLs it flagged, and the narrative analysis contradicts the
> verdict. Install with your eyes open, or clone and read the source (it's
> ~20 small Python files); don't just trust the badge.

**You don't need to pip-install anything up front.** Market-data scripts are standard-library-only and work immediately. For the live widgets and trading scripts the agent installs their small dep sets automatically the first time you ask for them — you just see one `pip install` line in the agent's tool output.

If you prefer to pre-install everything manually, `pip install -r requirements.txt` covers the widget + trading deps. On macOS system Python that's `pip install --user --break-system-packages -r requirements.txt`, or put them in a venv / pyenv / [uv](https://docs.astral.sh/uv/) project — any of the usual options.

## Structure

```
hyperliquid/
├── SKILL.md                  # agent-facing entry point
├── references/
│   ├── info-api.md           # every /info endpoint with exact payloads
│   ├── websocket.md          # WS subscription types and message shapes
│   └── trading.md            # signing, agent wallets, order types, safety
└── scripts/
    ├── market_data/          # runnable, no key required, stdlib-only
    │   ├── all_mids.py
    │   ├── order_book.py
    │   ├── candles.py
    │   ├── funding.py
    │   ├── meta.py
    │   └── hip3_dexes.py
    ├── trading/              # requires HL_PRIVATE_KEY
    │   ├── README.md
    │   ├── place_order.py
    │   └── cancel_order.py
    └── widgets/              # live TUI widgets (rich + websocket-client)
        ├── README.md
        ├── orderbook_tui.py
        ├── ticker_tui.py
        ├── tape_tui.py
        └── launch.py         # macOS dispatcher (spawns widgets in new window)
```

## Environment variables

| Var                   | Required for       | Default                            | Notes                                                            |
|-----------------------|--------------------|------------------------------------|------------------------------------------------------------------|
| `HL_ENV`              | nothing            | `mainnet` (reads) / `testnet` (trading) | `mainnet` or `testnet`                                      |
| `HL_PRIVATE_KEY`      | trading scripts    | —                                  | Hex-encoded private key (`0x...`); use an agent wallet, not master |
| `HL_ACCOUNT_ADDRESS`  | agent-wallet usage | —                                  | The master wallet address, if `HL_PRIVATE_KEY` is an agent key   |

## Dependencies (handled by the agent; listed here for transparency)

| Script type           | Python packages                          |
|-----------------------|------------------------------------------|
| Market data           | none — Python standard library only      |
| TUI widgets           | `rich`, `websocket-client`               |
| Trading               | `hyperliquid-python-sdk`, `eth-account`  |

## Safety

- **Read paths** (market data, widgets, user-state queries) default to **mainnet** — no key required, nothing can go wrong.
- **Signed paths** (place / cancel / modify orders) default to **testnet**. Switching to mainnet is an explicit `HL_ENV=mainnet` opt-in *and* the trading scripts require you to type `yes` before they submit.
- **Use an agent wallet, not your master key.** Hyperliquid's agent/API wallets can trade but cannot withdraw — the right credential to hand a bot. Full setup in [`references/trading.md`](references/trading.md) § *Agent wallets*.
- **Keys are read from `HL_PRIVATE_KEY` only** — never from config files you might commit. There is no key caching.

Read [`references/trading.md`](references/trading.md) before you ever point this at mainnet with a funded key.

## License

MIT
