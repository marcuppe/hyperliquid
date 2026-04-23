# hyperliquid (agent skill)

An agent skill for [Hyperliquid](https://hyperliquid.xyz) — the on-chain perps + spot DEX. Drop this into your Claude Code / Claude Agent setup and your agent will know how to:

- Pull perp and spot market data: prices, order books, candles, funding, open interest
- Query user state: positions, margin, fills, portfolio
- Subscribe to live data via WebSocket
- Place and cancel orders (testnet by default; mainnet requires an explicit opt-in and confirmation)

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

This skill **defaults to testnet** for any action that signs with a key. Do not point it at mainnet with a funded key unless you have read `references/trading.md` and understand what each script does.

## License

MIT
