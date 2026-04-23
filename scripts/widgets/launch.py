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

WIDGETS: dict[str, tuple[str, tuple[int, int]]] = {
    # name: (script_filename, (cols, rows))
    "orderbook": ("orderbook_tui.py", (60, 40)),
    "ticker":    ("ticker_tui.py",    (112, 16)),
    "tape":      ("tape_tui.py",      (64, 40)),
}


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

    script_name, size = WIDGETS[name]
    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"missing widget script: {script_path}", file=sys.stderr)
        return 2

    args = sys.argv[2:]
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
