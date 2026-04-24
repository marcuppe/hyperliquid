#!/usr/bin/env python3
"""Live L2 orderbook widget (rich + WebSocket).

Usage:
    python orderbook_tui.py BTC                    # default: 10 levels/side
    python orderbook_tui.py xyz:AAPL               # HIP-3 market
    python orderbook_tui.py BTC --depth 14         # deeper ladder (needs taller window)

Env:
    HL_ENV=mainnet|testnet  (default: mainnet)

Quit: Ctrl-C.
"""
import sys
import threading
import time
from pathlib import Path

# Preflight: fail fast with a clear install command if deps are missing.
sys.path.insert(0, str(Path(__file__).parent))
from _common import _require_dep  # noqa: E402
_require_dep("rich", "websocket")

from rich.align import Align  # noqa: E402
from rich.console import Console, Group  # noqa: E402
from rich.live import Live  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from _common import (  # noqa: E402
    WSClient,
    normalize_coin,
    MINT,
    BID,
    ASK,
    ACCENT,
    MUTED,
    DIM,
)

DEPTH_DEFAULT = 16
BAR_WIDTH = 22


def _parse_int_flag(argv: list[str], flag: str, default: int) -> int:
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            try:
                return int(argv[idx + 1])
            except ValueError:
                pass
    return default


def main() -> int:
    argv = sys.argv[1:]
    positional: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--depth" and i + 1 < len(argv):
            i += 2
            continue
        if argv[i].startswith("--"):
            i += 1
            continue
        positional.append(argv[i])
        i += 1

    if not positional:
        print("usage: orderbook_tui.py COIN [--depth N]", file=sys.stderr)
        return 2
    coin = normalize_coin(positional[0])
    depth = _parse_int_flag(argv, "--depth", DEPTH_DEFAULT)

    state: dict = {"book": None, "prev_mid": None}
    lock = threading.Lock()

    def on_msg(event: dict) -> None:
        if event.get("channel") != "l2Book":
            return
        with lock:
            state["book"] = event["data"]

    ws = WSClient(subscriptions=[{"type": "l2Book", "coin": coin}], on_message=on_msg)
    ws.start()

    console = Console()

    def render() -> Panel:
        with lock:
            snap = state["book"]
            prev_mid = state["prev_mid"]

        if snap is None:
            body = Align.center(Text("connecting…", style=MUTED), vertical="middle")
            return Panel(
                body,
                title=f" Hyperliquid · {coin} ",
                border_style=MINT,
                height=depth * 2 + 8,
                padding=(1, 2),
            )

        bids = snap["levels"][0][:depth]
        asks = snap["levels"][1][:depth]
        all_sz = [float(lvl["sz"]) for lvl in bids + asks] or [1.0]
        max_sz = max(all_sz)

        best_bid = float(bids[0]["px"]) if bids else None
        best_ask = float(asks[0]["px"]) if asks else None
        mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
        spread = best_ask - best_bid if (best_bid is not None and best_ask is not None) else None
        spread_bps = (spread / mid * 10_000) if (spread is not None and mid) else None

        # detect direction of last change
        arrow = ""
        arrow_style = MUTED
        if mid is not None and prev_mid is not None and mid != prev_mid:
            arrow = "▲" if mid > prev_mid else "▼"
            arrow_style = BID if mid > prev_mid else ASK
        if mid is not None and mid != prev_mid:
            with lock:
                state["prev_mid"] = mid

        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(justify="right", style=MUTED, width=12)   # size
        tbl.add_column(justify="left", width=BAR_WIDTH)           # bar
        tbl.add_column(justify="right", width=12)                 # price

        def bar_for(sz: float) -> str:
            n = max(1, int(sz / max_sz * BAR_WIDTH))
            return "█" * n

        for lvl in reversed(asks):
            sz = float(lvl["sz"])
            tbl.add_row(
                Text(f"{sz:.4f}", style=MUTED),
                Text(bar_for(sz), style=ASK),
                Text(lvl["px"], style=ASK),
            )
        tbl.add_row(Text(""), Text("─" * BAR_WIDTH, style=DIM), Text(""))
        if spread is not None and mid is not None:
            tbl.add_row(
                Text("mid", style=MUTED),
                Align.center(
                    Text(f"spread {spread:g}  ({spread_bps:.2f} bps)", style=ACCENT),
                    width=BAR_WIDTH,
                ),
                Text(f"{mid:g}", style=f"bold {MINT}"),
            )
        tbl.add_row(Text(""), Text("─" * BAR_WIDTH, style=DIM), Text(""))
        for lvl in bids:
            sz = float(lvl["sz"])
            tbl.add_row(
                Text(f"{sz:.4f}", style=MUTED),
                Text(bar_for(sz), style=BID),
                Text(lvl["px"], style=BID),
            )

        ts = time.strftime("%H:%M:%S", time.localtime(snap.get("time", 0) / 1000))
        header = Text.assemble(
            ("BID ", BID), ("●  ", BID),
            (f"{best_bid:g}" if best_bid is not None else "--", "white"),
            ("     ", ""),
            (f"{best_ask:g}" if best_ask is not None else "--", "white"),
            ("  ●", ASK), (" ASK", ASK),
            ("          ", ""),
            (arrow, arrow_style),
            ("   ", ""),
            (f"t={ts}", MUTED),
        )

        body = Group(header, Text(""), tbl)
        return Panel(
            body,
            title=f" Hyperliquid · {coin} ",
            border_style=MINT,
            padding=(1, 2),
        )

    try:
        with Live(render(), console=console, refresh_per_second=10, screen=False) as live:
            while True:
                time.sleep(0.1)
                live.update(render())
    except KeyboardInterrupt:
        pass
    finally:
        ws.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
