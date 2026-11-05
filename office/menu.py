from dataclasses import dataclass
from typing import Optional

from office.render.canvas import Canvas

PAPER, HIGHLIGHT = (246, 244, 236), (200, 222, 246)
INK, DIM, OFF_INK = (34, 38, 46), (110, 114, 125), (160, 70, 70)
TITLE = "Office"
HINT = "↑↓ move · space change · m close"


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    value: str
    switch: bool = False


class Menu:
    """The settings panel: a list of things to switch, moved through with the keys or clicked."""

    def __init__(self):
        self.open = False
        self.cursor = 0
        self.left = self.top_row = self.width = 0

    def toggle(self) -> None:
        self.open = not self.open

    def press(self, key: str, items: list[MenuItem]) -> Optional[str]:
        """Handle a key while open; returns the key of the item to change, if any."""
        if key in ("up", "k"):
            self.cursor = (self.cursor - 1) % len(items)
        elif key in ("down", "j"):
            self.cursor = (self.cursor + 1) % len(items)
        elif key in ("enter", "space"):
            return items[self.cursor].key
        elif key in ("esc", "m", "q"):
            self.open = False
        return None

    def click(self, col: int, cell_row: int, items: list[MenuItem]) -> Optional[str]:
        """Handle a click while open; a click outside the panel closes it."""
        index = cell_row - self.top_row - 2
        if not (self.left <= col < self.left + self.width and 0 <= index < len(items)):
            if not (self.left <= col < self.left + self.width and self.top_row <= cell_row <= self.top_row + len(items) + 3):
                self.open = False
            return None
        self.cursor = index
        return items[index].key

    def draw(self, canvas: Canvas, items: list[MenuItem]) -> None:
        label_width = max(len(item.label) for item in items)
        lines = [line_for(item, label_width) for item in items]
        self.width = max(len(HINT), *(len(line) for line in lines)) + 4
        self.left = max(0, (canvas.w - self.width) // 2)
        self.top_row = 1
        rows = len(items) + 4
        canvas.rect(self.left, self.top_row * 2, self.width, rows * 2, PAPER)
        canvas.label(self.left + 2, self.top_row, TITLE, INK)
        for index, (item, line) in enumerate(zip(items, lines)):
            row = self.top_row + 2 + index
            if index == self.cursor:
                canvas.rect(self.left + 1, row * 2, self.width - 2, 2, HIGHLIGHT)
            canvas.label(self.left + 2, row, line, OFF_INK if item.switch and item.value == "off" else INK)
        canvas.label(self.left + 2, self.top_row + rows - 1, HINT, DIM)


def line_for(item: MenuItem, label_width: int) -> str:
    if item.switch:
        return "[%s] %s" % ("x" if item.value == "on" else " ", item.label)
    return "    %s  %s" % (item.label.ljust(label_width), item.value)
