#!/usr/bin/env python3
"""Multi-market ticker widget (rich + REST polling).

Usage:
    python ticker_tui.py BTC ETH HYPE
    python ticker_tui.py BTC ETH HYPE xyz:TSLA xyz:GOLD   # mixed native + HIP-3

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
_require_dep("rich")

from rich.columns import Columns  # noqa: E402
from rich.console import Console, Group  # noqa: E402
from rich.live import Live  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from _common import (  # noqa: E402
    info,
    normalize_coin,
    sparkline,
    fmt_price,
    fmt_pct,
    fmt_notional,
    MINT,
    MINT_BRIGHT,
    BID,
    ASK,
    ACCENT,
    MUTED,
)

SPARK_CANDLES = 22       # 22 x 1m = last ~22 minutes; fits the card width
CARD_WIDTH = 26


def group_by_dex(coins: list[str]) -> dict[str, list[str]]:
    by_dex: dict[str, list[str]] = {}
    for c in coins:
        dex = c.split(":", 1)[0] if ":" in c else ""
        by_dex.setdefault(dex, []).append(c)
    return by_dex


def fetch_prices(coins: list[str]) -> dict[str, str]:
    prices: dict[str, str] = {}
    for dex, members in group_by_dex(coins).items():
        try:
            data = info({"type": "allMids", "dex": dex})
        except Exception:
            continue
        for c in members:
            if c in data:
                prices[c] = data[c]
    return prices


def fetch_ctx(coins: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for dex, members in group_by_dex(coins).items():
        try:
            meta, ctxs = info({"type": "metaAndAssetCtxs", "dex": dex})
        except Exception:
            continue
        for i, asset in enumerate(meta["universe"]):
            if asset["name"] in members:
                out[asset["name"]] = ctxs[i] if i < len(ctxs) else {}
    return out


def fetch_sparkline(coin: str) -> list[float]:
    end = int(time.time() * 1000)
    # pull a slightly larger window than we'll display, then trim to the last N
    start = end - (SPARK_CANDLES + 2) * 60_000
    try:
        candles = info(
            {
                "type": "candleSnapshot",
                "req": {"coin": coin, "interval": "1m", "startTime": start, "endTime": end},
            }
        )
        closes = [float(c["c"]) for c in candles]
        return closes[-SPARK_CANDLES:]
    except Exception:
        return []


def card(coin: str, mid: str | None, ctx: dict, spark: list[float]) -> Panel:
    price = Text(fmt_price(mid) if mid else "--", style=f"bold {MINT_BRIGHT}", justify="center")

    change_text = Text("", justify="center")
    prev = ctx.get("prevDayPx")
    if mid and prev:
        try:
            pct = (float(mid) - float(prev)) / float(prev) * 100
            arrow = "▲" if pct >= 0 else "▼"
            color = BID if pct >= 0 else ASK
            change_text = Text(f"{arrow} {fmt_pct(pct)}", style=f"bold {color}", justify="center")
        except Exception:
            pass

    spark_str = sparkline(spark)
    if spark_str:
        spark_text = Text(spark_str, style=MINT, justify="center")
        spark_label = Text("last 22m · 1m bars", style=MUTED, justify="center")
    else:
        spark_text = Text("·" * 22, style=MUTED, justify="center")
        spark_label = Text("(no candles)", style=MUTED, justify="center")

    meta_parts: list[Text] = []
    funding = ctx.get("funding")
    if funding is not None:
        try:
            fr = float(funding)
            apr = fr * 24 * 365 * 100
            meta_parts.append(
                Text.assemble(
                    ("fnd ", MUTED),
                    (f"{fr:.4%}/h", ACCENT),
                    (f"  ({apr:+.1f}% APR)", MUTED),
                )
            )
        except Exception:
            pass
    vlm = ctx.get("dayNtlVlm")
    if vlm is not None:
        try:
            meta_parts.append(Text.assemble(("vol ", MUTED), (fmt_notional(vlm), "white")))
        except Exception:
            pass
    oi = ctx.get("openInterest")
    if oi is not None:
        try:
            meta_parts.append(Text.assemble(("oi  ", MUTED), (fmt_notional(oi), "white")))
        except Exception:
            pass

    body = Group(
        Text(""),
        price,
        change_text,
        Text(""),
        spark_text,
        spark_label,
        Text(""),
        *[Text.from_markup(t.markup, justify="center") for t in meta_parts],
    )
    return Panel(body, title=f" {coin} ", border_style=MINT, width=CARD_WIDTH, padding=(0, 1))


def main() -> int:
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not positional:
        print("usage: ticker_tui.py COIN [COIN ...]", file=sys.stderr)
        return 2
    coins = [normalize_coin(a) for a in positional]

    state: dict = {"prices": {}, "ctx": {}, "sparks": {c: [] for c in coins}}
    lock = threading.Lock()
    stop = threading.Event()

    def price_loop() -> None:
        while not stop.is_set():
            try:
                p = fetch_prices(coins)
                with lock:
                    state["prices"] = p
            except Exception:
                pass
            stop.wait(1.0)

    def ctx_loop() -> None:
        while not stop.is_set():
            try:
                c = fetch_ctx(coins)
                with lock:
                    state["ctx"] = c
            except Exception:
                pass
            stop.wait(5.0)

    def spark_loop() -> None:
        while not stop.is_set():
            for c in coins:
                if stop.is_set():
                    break
                try:
                    vs = fetch_sparkline(c)
                    with lock:
                        state["sparks"][c] = vs
                except Exception:
                    pass
            stop.wait(30.0)

    for fn in (price_loop, ctx_loop, spark_loop):
        threading.Thread(target=fn, daemon=True).start()

    console = Console()

    def render() -> Columns:
        with lock:
            prices = dict(state["prices"])
            ctx = dict(state["ctx"])
            sparks = {k: list(v) for k, v in state["sparks"].items()}
        cards = [card(c, prices.get(c), ctx.get(c, {}), sparks.get(c, [])) for c in coins]
        return Columns(cards, equal=True, expand=False)

    try:
        with Live(render(), console=console, refresh_per_second=4, screen=False) as live:
            while True:
                time.sleep(0.25)
                live.update(render())
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
