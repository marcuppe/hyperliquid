# Hyperliquid TUI widgets

Rich-powered terminal widgets you can pop into a floating window and park on your desktop. They read from Hyperliquid's public API — no private key needed.

## ⚠️  macOS only (for `launch.py`)

The `launch.py` dispatcher uses AppleScript to spawn and size new Terminal.app / iTerm2 windows. On Linux or Windows, `launch.py` will refuse to run, but **the widgets themselves still work** — just invoke their scripts directly in your current terminal.

**First run will prompt for Automation permission** the first time AppleScript tries to control Terminal.app or iTerm. The macOS prompt looks like:

> "Claude Code" wants access to control "Terminal"

Grant it. You only have to do it once. You can pre-grant it at **System Settings → Privacy & Security → Automation** → enable *Terminal* (or *iTerm*) under whatever app is running `launch.py`. If you skip the prompt during a demo, the window won't spawn.

## Install

```bash
pip install rich websocket-client requests
# On recent macOS system Python (PEP 668):
pip install --user --break-system-packages rich websocket-client requests
```

## Usage

**In a new window (macOS):**
```bash
python scripts/widgets/launch.py ticker BTC ETH HYPE xyz:TSLA
python scripts/widgets/launch.py orderbook xyz:AAPL
python scripts/widgets/launch.py tape BTC
```

**In your current terminal (any OS):**
```bash
python scripts/widgets/ticker_tui.py BTC ETH HYPE
python scripts/widgets/orderbook_tui.py BTC
python scripts/widgets/tape_tui.py BTC
```

Quit a widget with `Ctrl-C`.

## Widgets

| Name         | What it shows                                                                 |
|--------------|-------------------------------------------------------------------------------|
| `ticker`     | Multi-market card grid: mid price, 24h change, sparkline, funding rate, 24h volume, OI. REST-polled. |
| `orderbook`  | Live L2 ladder with size-proportional bars, colored bid/ask, and live spread in bps. WebSocket. |
| `tape`       | Scrolling trade feed with side coloring, large-fill highlighting, rolling 1-min buy/sell/delta. WebSocket. |

All three accept HIP-3 coins in `dex:COIN` form (e.g. `xyz:AAPL`, `flx:CRCL`).

## Default window sizes

| Widget    | Size (cols × rows) |
|-----------|--------------------|
| ticker    | 112 × 14           |
| orderbook | 60 × 40            |
| tape      | 64 × 40            |

Drag them onto a second monitor, tile two or three, and it looks like a trading desk.

## Env

| Var      | Default   | Notes                                                              |
|----------|-----------|--------------------------------------------------------------------|
| `HL_ENV` | `mainnet` | `mainnet` or `testnet`. `launch.py` propagates it to the new window. |

## Notes for demos

- The dispatcher uses `sys.executable`, so the spawned window uses the same Python as the caller — `rich` / `websocket-client` must be installed in that interpreter.
- If a widget crashes, the window shows `[press enter to close]` so the error stays on screen.
- The WebSocket widgets (`orderbook`, `tape`) auto-reconnect silently with exponential backoff.
- The ticker is pure REST polling (1s for mids, 5s for context, 30s for sparklines). Simpler and reliable.
- No `q` keybinding yet — use `Ctrl-C` to quit.
- There's no windowed launcher on Linux/Windows yet. Contributions welcome; implementation would swap the AppleScript block for `gnome-terminal -- …`, `kitty @ launch …`, WSL-specific calls, etc.
