import os
import re
import select
import sys
import time
from typing import Optional

MOUSE_ON, MOUSE_OFF = "\033[?1000h\033[?1006h", "\033[?1006l\033[?1000l"
CLICK = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
KEY = re.compile(r"\x1b\[<[\d;]+[Mm]|\x1b\[[\d;?]*([A-Za-z~])|\x1bO([A-Za-z])|(\x1b)|(.)", re.S)
NAMED_KEYS = {"A": "up", "B": "down", "C": "right", "D": "left", "Z": "backtab", "\t": "tab", "\r": "enter", "\n": "enter",
              " ": "space", "\x1b": "esc"}
DOUBLE_CLICK_SECONDS = 0.45
ESCAPE_GRACE = 0.02


def parse(raw: str) -> tuple[list[tuple[int, int]], list[str]]:
    """Left-button presses as zero-based (column, row) cells, and the keys pressed as names or characters."""
    clicks = [(int(col) - 1, int(row) - 1) for button, col, row, kind in CLICK.findall(raw) if kind == "M" and button == "0"]
    keys = []
    for match in KEY.finditer(raw):
        token = match.group(1) or match.group(2) or match.group(3) or match.group(4)
        if token:
            keys.append(NAMED_KEYS.get(token, token))
    return clicks, keys


def read_raw(timeout: float) -> str:
    """Input arriving within `timeout` seconds, returned as soon as some has come and the rest of its sequence with it."""
    buffer, end = "", time.monotonic() + timeout
    while True:
        wait = end - time.monotonic() if not buffer else ESCAPE_GRACE
        if wait <= 0 or not select.select([sys.stdin], [], [], wait)[0]:
            return buffer
        chunk = os.read(sys.stdin.fileno(), 1024).decode(errors="ignore")
        if not chunk:
            return buffer
        buffer += chunk


class Terminal:
    """Raw keys and mouse reporting for as long as the office runs, restored afterwards."""

    def __init__(self):
        self.saved = None

    def __enter__(self) -> "Terminal":
        if sys.stdin.isatty():
            import termios
            import tty
            self.saved = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        sys.stdout.write(MOUSE_ON)
        return self

    def __exit__(self, *exc) -> None:
        sys.stdout.write(MOUSE_OFF)
        if self.saved:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.saved)

    def interactive(self) -> bool:
        return self.saved is not None


class DoubleClick:
    """Spots a second click on the same thing soon after the first."""

    def __init__(self):
        self.last: tuple[float, Optional[str]] = (0.0, None)

    def press(self, target: Optional[str], now: float) -> bool:
        double = target is not None and self.last[1] == target and now - self.last[0] < DOUBLE_CLICK_SECONDS
        self.last = (0.0, None) if double else (now, target)
        return double
