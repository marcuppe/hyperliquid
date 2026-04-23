# hyperliquid (agent skill)

An agent skill for [Hyperliquid](https://hyperliquid.xyz) — the on-chain perps + spot DEX. Drop this into your Claude Code / Claude Agent setup and your agent will know how to:

- Pull perp and spot market data: prices, order books, candles, funding, open interest
- Query user state: positions, margin, fills, portfolio
- Subscribe to live data via WebSocket
- Place and cancel orders (testnet by default; mainnet requires an explicit opt-in and confirmation)

## Install

One line — add the skill to your agent and you're done:

```bash
npx skills add <owner>/hyperliquid
```

Or clone into your `.claude/skills/` (Claude Code) or agent's skills directory.

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
    ├── market_data/          # runnable, no key required
    │   ├── all_mids.py
    │   ├── order_book.py
    │   ├── candles.py
    │   ├── funding.py
    │   └── meta.py
    └── trading/              # requires HL_PRIVATE_KEY
        ├── README.md
        ├── place_order.py
        └── cancel_order.py
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
