"""Shared helpers for the Hyperliquid TUI widgets."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Callable
from urllib.request import Request, urlopen

try:
    import websocket  # type: ignore
except ImportError:
    websocket = None  # type: ignore


def _require_dep(*_modules: str) -> None:
    missing = []
    for name in _modules:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        pip_names = " ".join({"websocket": "websocket-client"}.get(m, m) for m in missing)
        sys.stderr.write(
            "\nerror: missing dependency — "
            f"{', '.join(missing)} not installed.\n"
            f"install with:  pip install --user --break-system-packages {pip_names}\n"
            "(on a venv or pyenv, drop --user --break-system-packages)\n\n"
        )
        sys.exit(127)


# HL brand-ish palette, chosen to pop on a dark terminal.
MINT = "#97fce4"
MINT_BRIGHT = "#d4fff4"
BID = "#34d399"
ASK = "#f87171"
ACCENT = "#e879f9"
MUTED = "#9ca3af"
DIM = "#4b5563"


def base_url_rest() -> str:
    env = os.environ.get("HL_ENV", "mainnet")
    return "https://api.hyperliquid-testnet.xyz" if env == "testnet" else "https://api.hyperliquid.xyz"


def base_url_ws() -> str:
    env = os.environ.get("HL_ENV", "mainnet")
    return "wss://api.hyperliquid-testnet.xyz/ws" if env == "testnet" else "wss://api.hyperliquid.xyz/ws"


def normalize_coin(s: str) -> str:
    if ":" in s:
        dex, coin = s.split(":", 1)
        return f"{dex.lower()}:{coin.upper()}"
    return s.upper()


def info(payload: dict, timeout: float = 10.0) -> object:
    req = Request(
        f"{base_url_rest()}/info",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class WSClient(threading.Thread):
    """Daemon thread that holds a Hyperliquid WebSocket open, auto-reconnects,
    and forwards every inbound JSON event to `on_message`."""

    def __init__(self, subscriptions: list[dict], on_message: Callable[[dict], None]):
        super().__init__(daemon=True)
        self.subscriptions = subscriptions
        self.on_message = on_message
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        if websocket is None:
            return
        backoff = 1.0
        while not self.stop_event.is_set():
            ws = None
            try:
                ws = websocket.create_connection(base_url_ws(), timeout=10)
                for sub in self.subscriptions:
                    ws.send(json.dumps({"method": "subscribe", "subscription": sub}))
                backoff = 1.0
                while not self.stop_event.is_set():
                    raw = ws.recv()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event.get("channel") == "pong":
                        continue
                    try:
                        self.on_message(event)
                    except Exception:
                        pass
            except Exception:
                time.sleep(min(backoff, 10))
                backoff *= 2
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass


def fmt_price(p: float | str | None) -> str:
    if p is None or p == "":
        return "--"
    if isinstance(p, str):
        try:
            p = float(p)
        except ValueError:
            return p
    if p < 1:
        digits = 6
    elif p < 1000:
        digits = 2
    else:
        digits = 0
    return f"{p:,.{digits}f}"


def fmt_size(s: float | str, digits: int = 4) -> str:
    if isinstance(s, str):
        s = float(s)
    return f"{s:,.{digits}f}"


def fmt_pct(p: float, digits: int = 2) -> str:
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.{digits}f}%"


def fmt_notional(v: float | str | None) -> str:
    if v is None or v == "":
        return "--"
    v = float(v)
    if abs(v) >= 1e9:
        return f"{v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v/1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"{v/1e3:.2f}K"
    return f"{v:.0f}"


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1e-9
    out = []
    for v in values:
        idx = int((v - lo) / span * (len(blocks) - 1))
        out.append(blocks[max(0, min(idx, len(blocks) - 1))])
    return "".join(out)
