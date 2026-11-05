from typing import Optional, TextIO

from office.render.canvas import TRUECOLOR, Cell, encode

ENTER = "\033[?1049h\033[?25l\033[?7l"
LEAVE = "\033[0m\033[?7h\033[?25h\033[?1049l"
CLEAR_LINE = "\033[K"


class Screen:
    """Writes frames to the terminal: a header line, then the picture, sending only the cells that changed."""

    def __init__(self, out: TextIO, colours: str = TRUECOLOR):
        self.out, self.colours = out, colours
        self.header: Optional[str] = None
        self.rows: Optional[list[list[Cell]]] = None

    def enter(self) -> None:
        self.out.write(ENTER)
        self.out.flush()

    def leave(self) -> None:
        self.out.write(LEAVE)
        self.out.flush()

    def forget(self) -> None:
        self.header, self.rows = None, None

    def show(self, header: str, rows: list[list[Cell]]) -> int:
        """Draw the frame and return how many bytes it took."""
        payload = self.changes(header, rows)
        self.header, self.rows = header, rows
        if payload:
            self.out.write(payload)
            self.out.flush()
        return len(payload.encode())

    def changes(self, header: str, rows: list[list[Cell]]) -> str:
        if self.rows is None or len(self.rows) != len(rows) or len(self.rows[0]) != len(rows[0]):
            return "\033[H\033[2J" + header + CLEAR_LINE + "".join("\n" + encode(row, self.colours) for row in rows)
        parts = ["\033[1;1H" + header + CLEAR_LINE] if header != self.header else []
        for index, (row, old) in enumerate(zip(rows, self.rows)):
            if row != old:
                first, last = changed_span(row, old)
                parts.append("\033[%d;%dH%s" % (index + 2, first + 1, encode(row[first:last + 1], self.colours)))
        return "".join(parts)


def changed_span(row: list[Cell], old: list[Cell]) -> tuple[int, int]:
    """First and last differing cells of two rows that differ, by halving slices so the comparing stays in C."""
    low, high = 0, len(row)
    while high - low > 1:
        middle = (low + high) // 2
        if row[low:middle] == old[low:middle]:
            low = middle
        else:
            high = middle
    first, high = low, len(row)
    while high - low > 1:
        middle = (low + high) // 2
        if row[middle:high] == old[middle:high]:
            high = middle
        else:
            low = middle
    return first, low
