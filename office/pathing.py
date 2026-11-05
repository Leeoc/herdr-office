import heapq
from collections import deque
from dataclasses import dataclass

Point = tuple[float, float]
Cell = tuple[int, int]
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
TURN_COST = 3


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    def overlaps(self, other: "Rect") -> bool:
        return self.x < other.x + other.w and other.x < self.x + self.w and self.y < other.y + other.h and other.y < self.y + self.h

    def moved(self, dx: float, dy: float) -> "Rect":
        return Rect(int(self.x + dx), int(self.y + dy), self.w, self.h)


class WalkGrid:
    """Where a person can stand, on a coarse grid of anchor positions, and the routes between them.

    `bounds` is the area a person's anchor may occupy and `footprint` is the part of the body,
    relative to the anchor, that must stay clear of every obstacle.
    """

    def __init__(self, bounds: Rect, obstacles: list[Rect], footprint: Rect, cell: int = 2):
        self.bounds, self.cell = bounds, cell
        self.cols, self.rows = max(1, bounds.w // cell), max(1, bounds.h // cell)
        self.open = [[not any(footprint.moved(*self.point((c, r))).overlaps(o) for o in obstacles)
                      for c in range(self.cols)] for r in range(self.rows)]

    def point(self, cell: Cell) -> Point:
        return float(self.bounds.x + cell[0] * self.cell), float(self.bounds.y + cell[1] * self.cell)

    def cell_of(self, point: Point) -> Cell:
        col = round((point[0] - self.bounds.x) / self.cell)
        row = round((point[1] - self.bounds.y) / self.cell)
        return min(max(col, 0), self.cols - 1), min(max(row, 0), self.rows - 1)

    def is_open(self, cell: Cell) -> bool:
        return self.open[cell[1]][cell[0]]

    def nearest_open(self, start: Cell) -> Cell:
        seen, queue = {start}, deque([start])
        while queue:
            cell = queue.popleft()
            if self.is_open(cell):
                return cell
            for nxt in self.neighbours(cell):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return start

    def neighbours(self, cell: Cell):
        for dc, dr in STEPS:
            col, row = cell[0] + dc, cell[1] + dr
            if 0 <= col < self.cols and 0 <= row < self.rows:
                yield col, row

    def route(self, start: Point, goal: Point) -> list[Point]:
        """Waypoints from `start` to `goal`, around obstacles, each one a straight horizontal or vertical walk."""
        first, last = self.nearest_open(self.cell_of(start)), self.nearest_open(self.cell_of(goal))
        cells = self.search(first, last) or [first, last]
        return [self.point(c) for c in corners(cells)] + [goal]

    def search(self, start: Cell, goal: Cell) -> list[Cell]:
        """A* over cells that charges for turns, so people walk in long straight lines rather than staircases."""
        frontier = [(0, 0, start, None)]
        came_from = {(start, None): None}
        cost = {(start, None): 0}
        order = 0
        while frontier:
            _, _, cell, heading = heapq.heappop(frontier)
            if cell == goal:
                return self.unwind(came_from, (cell, heading))
            for nxt in self.neighbours(cell):
                if not self.is_open(nxt):
                    continue
                step = (nxt[0] - cell[0], nxt[1] - cell[1])
                new_cost = cost[(cell, heading)] + 1 + (TURN_COST if heading not in (None, step) else 0)
                if new_cost < cost.get((nxt, step), 1 << 30):
                    cost[(nxt, step)] = new_cost
                    came_from[(nxt, step)] = (cell, heading)
                    order += 1
                    estimate = abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1])
                    heapq.heappush(frontier, (new_cost + estimate, order, nxt, step))
        return []

    @staticmethod
    def unwind(came_from: dict, state) -> list[Cell]:
        cells = []
        while state is not None:
            cells.append(state[0])
            state = came_from[state]
        return cells[::-1]


def corners(cells: list[Cell]) -> list[Cell]:
    if len(cells) < 3:
        return cells
    kept = [cells[0]]
    for before, here, after in zip(cells, cells[1:], cells[2:]):
        if (here[0] - before[0], here[1] - before[1]) != (after[0] - here[0], after[1] - here[1]):
            kept.append(here)
    kept.append(cells[-1])
    return kept
