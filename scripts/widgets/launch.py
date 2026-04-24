#!/usr/bin/env python3
"""Launch a Hyperliquid widget in a new macOS terminal window.

Usage:
    python launch.py <widget> [widget_args...]

Widgets:
    orderbook COIN
    ticker    COIN [COIN ...]
    tape      COIN

Env:
    HL_ENV=mainnet|testnet  (default: mainnet) — propagated to the new window.

macOS only. First run may prompt for Automation permission (System Settings
→ Privacy & Security → Automation → Claude Code / your terminal). Grant it
once and it stays granted.

To run a widget without spawning a new window (any OS), invoke its script
directly, e.g. `python scripts/widgets/ticker_tui.py BTC ETH`.
"""
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path

WIDGETS: dict[str, str] = {
    "orderbook": "orderbook_tui.py",
    "ticker":    "ticker_tui.py",
    "tape":      "tape_tui.py",
}

# Tunables that match the widget internals. Keep in sync with:
#   orderbook_tui.DEPTH_DEFAULT, tape_tui.TAPE_LEN_DEFAULT, ticker_tui.CARD_WIDTH
ORDERBOOK_DEPTH_DEFAULT = 16
TAPE_LEN_DEFAULT = 22
TICKER_CARD_STRIDE = 27          # card width (26) + gutter (1)
TICKER_ROWS_PER_CARD = 14        # content rows a single card needs
MAX_TICKER_CARDS_PER_ROW = 6     # wrap beyond this


def _parse_int_flag(argv: list[str], flag: str, default: int) -> int:
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            try:
                return int(argv[idx + 1])
            except ValueError:
                pass
    return default


def _positional_count(argv: list[str], flags_with_value: set[str]) -> int:
    """Count positional (non-flag) args, skipping flag values."""
    n = 0
    i = 0
    while i < len(argv):
        if argv[i] in flags_with_value and i + 1 < len(argv):
            i += 2
            continue
        if argv[i].startswith("--"):
            i += 1
            continue
        n += 1
        i += 1
    return n


def compute_size(widget: str, args: list[str]) -> tuple[int, int]:
    """Return (cols, rows) tailored to what's being rendered."""
    if widget == "ticker":
        coins = max(1, _positional_count(args, set()))
        per_row = min(coins, MAX_TICKER_CARDS_PER_ROW)
        rows_of_cards = (coins + per_row - 1) // per_row
        cols = per_row * TICKER_CARD_STRIDE + 1
        rows = rows_of_cards * TICKER_ROWS_PER_CARD + 2
        return cols, rows
    if widget == "orderbook":
        depth = _parse_int_flag(args, "--depth", ORDERBOOK_DEPTH_DEFAULT)
        # 2*depth levels + header/mid/seps/padding/border ≈ 2*depth + 10 rows
        return 58, 2 * depth + 10
    if widget == "tape":
        tape_len = _parse_int_flag(args, "--rows", TAPE_LEN_DEFAULT)
        # tape_len rows + summary/sep/padding/border ≈ tape_len + 8
        return 56, tape_len + 8
    return 80, 24


def build_command(script_path: Path, args: list[str]) -> str:
    env_prefix = ""
    if "HL_ENV" in os.environ:
        env_prefix = f"HL_ENV={shlex.quote(os.environ['HL_ENV'])} "
    py = shlex.quote(sys.executable)
    path = shlex.quote(str(script_path))
    extra = " ".join(shlex.quote(a) for a in args)
    inner = f"{env_prefix}{py} {path} {extra}".rstrip()
    # keep the window open on exit so errors / the final frame are visible
    return f"{inner}; echo; echo '[press enter to close]'; read"


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def spawn_terminal_app(cmd: str, title: str, size: tuple[int, int]) -> None:
    cols, rows = size
    escaped = _escape_applescript(cmd)
    title_esc = _escape_applescript(title)
    apple_script = f'''
tell application "Terminal"
    activate
    set newTab to do script "{escaped}"
    delay 0.2
    try
        set custom title of window 1 to "{title_esc}"
    end try
    try
        set number of columns of window 1 to {cols}
        set number of rows of window 1 to {rows}
    end try
end tell
'''
    subprocess.run(["osascript", "-e", apple_script], check=True)


def spawn_iterm(cmd: str, title: str, size: tuple[int, int]) -> None:
    cols, rows = size
    escaped = _escape_applescript(cmd)
    title_esc = _escape_applescript(title)
    apple_script = f'''
tell application "iTerm"
    activate
    set newWindow to (create window with default profile)
    tell current session of newWindow
        write text "{escaped}"
    end tell
    try
        tell newWindow
            set name to "{title_esc}"
        end tell
    end try
end tell
'''
    subprocess.run(["osascript", "-e", apple_script], check=True)


def main() -> int:
    if platform.system() != "Darwin":
        print("launch.py is macOS-only.", file=sys.stderr)
        print("Run the widget directly in your current terminal instead, e.g.", file=sys.stderr)
        print(f"  {sys.executable} {Path(__file__).parent / 'ticker_tui.py'} BTC ETH", file=sys.stderr)
        return 2

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(sys.argv) >= 2 else 2

    name = sys.argv[1]
    if name not in WIDGETS:
        print(f"unknown widget {name!r}. known: {', '.join(WIDGETS)}", file=sys.stderr)
        return 2

    script_name = WIDGETS[name]
    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"missing widget script: {script_path}", file=sys.stderr)
        return 2

    args = sys.argv[2:]
    size = compute_size(name, args)
    cmd = build_command(script_path, args)
    title = f"Hyperliquid · {name}"
    if args:
        title += " " + " ".join(args)

    term = os.environ.get("TERM_PROGRAM", "")
    if term == "iTerm.app":
        spawn_iterm(cmd, title, size)
    else:
        spawn_terminal_app(cmd, title, size)

    print(f"launched {name} widget in a new window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
