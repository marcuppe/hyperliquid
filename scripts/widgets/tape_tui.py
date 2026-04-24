#!/usr/bin/env python3
"""Scrolling trade tape widget (rich + WebSocket).

Usage:
    python tape_tui.py BTC                 # default: 22 rows of tape
    python tape_tui.py xyz:TSLA
    python tape_tui.py BTC --rows 32       # longer tape (needs taller window)

Env:
    HL_ENV=mainnet|testnet  (default: mainnet)

Quit: Ctrl-C.
"""
import sys
import threading
import time
from collections import deque
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
    MUTED,
    DIM,
)

TAPE_LEN_DEFAULT = 22


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
        if argv[i] == "--rows" and i + 1 < len(argv):
            i += 2
            continue
        if argv[i].startswith("--"):
            i += 1
            continue
        positional.append(argv[i])
        i += 1

    if not positional:
        print("usage: tape_tui.py COIN [--rows N]", file=sys.stderr)
        return 2
    coin = normalize_coin(positional[0])
    tape_len = _parse_int_flag(argv, "--rows", TAPE_LEN_DEFAULT)

    tape: deque = deque(maxlen=tape_len)
    recent: deque = deque()  # (epoch_s, side, sz, px) for rolling 1m
    lock = threading.Lock()

    def on_msg(event: dict) -> None:
        if event.get("channel") != "trades":
            return
        now = time.time()
        with lock:
            for t in event["data"]:
                tape.appendleft(t)
                recent.append((t["time"] / 1000.0, t["side"], float(t["sz"]), float(t["px"])))
            cutoff = now - 60
            while recent and recent[0][0] < cutoff:
                recent.popleft()

    ws = WSClient(subscriptions=[{"type": "trades", "coin": coin}], on_message=on_msg)
    ws.start()

    console = Console()

    def render() -> Panel:
        with lock:
            items = list(tape)
            recs = list(recent)

        if not items:
            body = Align.center(Text("waiting for trades…", style=MUTED), vertical="middle")
            return Panel(
                body,
                title=f" Hyperliquid · {coin} tape ",
                border_style=MINT,
                height=tape_len + 6,
                padding=(1, 2),
            )

        max_sz = max((float(t["sz"]) for t in items), default=1.0)

        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(justify="right", width=8)   # time
        tbl.add_column(justify="center", width=2)  # glyph
        tbl.add_column(justify="right", width=12)  # size
        tbl.add_column(justify="right", width=12)  # price

        for t in items:
            tstr = time.strftime("%H:%M:%S", time.localtime(t["time"] / 1000))
            sz = float(t["sz"])
            is_buy = t["side"] == "B"
            color = BID if is_buy else ASK
            glyph = "▲" if is_buy else "▼"
            big = (sz / max_sz) > 0.5
            style = f"bold {color}" if big else color
            tbl.add_row(
                Text(tstr, style=MUTED),
                Text(glyph, style=style),
                Text(f"{sz:.4f}", style=style),
                Text(t["px"], style=style),
            )

        buy_sz = sum(r[2] for r in recs if r[1] == "B")
        sell_sz = sum(r[2] for r in recs if r[1] == "A")
        delta = buy_sz - sell_sz
        summary = Text.assemble(
            ("1m buy ", MUTED), (f"{buy_sz:.4f}  ", BID),
            ("sell ", MUTED), (f"{sell_sz:.4f}  ", ASK),
            ("Δ ", MUTED),
            (f"{delta:+.4f}", BID if delta >= 0 else ASK),
        )
        body = Group(tbl, Text(""), Text("─" * 36, style=DIM), summary)
        return Panel(
            body,
            title=f" Hyperliquid · {coin} tape ",
            border_style=MINT,
            padding=(1, 2),
        )

    try:
        with Live(render(), console=console, refresh_per_second=6, screen=False) as live:
            while True:
                time.sleep(0.15)
                live.update(render())
    except KeyboardInterrupt:
        pass
    finally:
        ws.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
