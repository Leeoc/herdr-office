from functools import lru_cache
from itertools import repeat
from typing import Optional

Colour = tuple[int, int, int]
Cell = tuple[Colour, Colour, str]
HALF_BLOCK = "▀"


class Canvas:
    """A pixel grid shown two pixels per terminal cell, with text labels laid over whole cells.

    While `light` is set, every pixel drawn is lit by it, so a cached night background and the
    people drawn over it share one lighting.
    """

    def __init__(self, w: int, h: int, fill: Colour):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]
        self.text: dict[tuple[int, int], tuple[str, Colour]] = {}
        self.light = None
        self.base: Optional["Canvas"] = None
        self.dirty: dict[int, list[int]] = {}
        self._cells: Optional[list[list[Cell]]] = None

    @classmethod
    def over(cls, base: "Canvas", light=None) -> "Canvas":
        """A canvas starting as a copy of `base`, which can reuse base's rows wherever they stay untouched."""
        canvas = cls.__new__(cls)
        canvas.h, canvas.w = base.h, base.w
        canvas.px = [row[:] for row in base.px]
        canvas.text, canvas.light, canvas.base = {}, light, base
        canvas.dirty = {}
        return canvas

    def dot(self, x, y, colour: Colour) -> None:
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = self.light.apply(colour, x, y) if self.light else colour
            span = self.dirty.get(y >> 1)
            if span is None:
                self.dirty[y >> 1] = [x, x]
            elif x < span[0]:
                span[0] = x
            elif x > span[1]:
                span[1] = x

    def rect(self, x, y, w: int, h: int, colour: Colour) -> None:
        for yy in range(int(y), int(y) + h):
            for xx in range(int(x), int(x) + w):
                self.dot(xx, yy, colour)

    def label(self, x, cell_row: int, text: str, fg: Colour) -> None:
        for i, ch in enumerate(text):
            self.text[(int(x) + i, cell_row)] = (ch, fg)

    def cells(self) -> list[list[Cell]]:
        """Each terminal row as (foreground, background, character) cells."""
        if self.base is None and self._cells is not None:
            return self._cells
        texted = {cy for _, cy in self.text}
        rows = [self.row_cells(cy, cy in texted) for cy in range(self.h // 2)]
        for (x, cy), (ch, fg) in self.text.items():
            if 0 <= x < self.w and 0 <= cy < len(rows):
                rows[cy][x] = (fg, rows[cy][x][1], ch)
        if self.base is None:
            self._cells = rows
        return rows

    def row_cells(self, cy: int, will_change: bool) -> list[Cell]:
        top, bottom = self.px[2 * cy], self.px[2 * cy + 1]
        if self.base is None:
            return list(zip(top, bottom, repeat(HALF_BLOCK, self.w)))
        base_row = self.base.cells()[cy]
        span = self.dirty.get(cy)
        if span is None:
            return base_row[:] if will_change else base_row
        row = base_row[:]
        first, last = span[0], span[1] + 1
        row[first:last] = zip(top[first:last], bottom[first:last], repeat(HALF_BLOCK, last - first))
        return row


TRUECOLOR, COLOURS_256 = "truecolor", "256"
CUBE = (0, 95, 135, 175, 215, 255)


def encode(cells: list[Cell], colours: str = TRUECOLOR) -> str:
    """Cells as terminal output, setting colours only where they change."""
    parts, last = [], None
    pair = colour_pair if colours == TRUECOLOR else colour_pair_256
    for fg, bg, ch in cells:
        if (fg, bg) != last:
            parts.append(pair(fg, bg))
            last = (fg, bg)
        parts.append(ch)
    return "".join(parts) + "\033[0m"


def colour_pair(fg: Colour, bg: Colour) -> str:
    return "\033[38;2;%d;%d;%dm\033[48;2;%d;%d;%dm" % (*fg, *bg)


def colour_pair_256(fg: Colour, bg: Colour) -> str:
    return "\033[38;5;%dm\033[48;5;%dm" % (xterm_256(fg), xterm_256(bg))


@lru_cache(maxsize=4096)
def xterm_256(colour: Colour) -> int:
    """The nearest of the 256-colour palette's colour cube and grey ramp."""
    steps = [min(range(6), key=lambda i: abs(CUBE[i] - c)) for c in colour]
    cube = tuple(CUBE[i] for i in steps)
    grey_step = min(23, max(0, round((sum(colour) / 3 - 8) / 10)))
    grey = (8 + grey_step * 10,) * 3
    if distance(colour, grey) < distance(colour, cube):
        return 232 + grey_step
    return 16 + 36 * steps[0] + 6 * steps[1] + steps[2]


def distance(a: Colour, b: Colour) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))
