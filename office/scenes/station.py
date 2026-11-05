from typing import Hashable

from office.render.canvas import Canvas, Colour
from office.scenes.base import FrameView
from office.scenes.office import OfficeScene

HULL, PANEL_LINE, RIVET = (34, 40, 52), (26, 31, 41), (70, 80, 96)
GLOW, GLOW_DIM = (70, 210, 230), (40, 110, 130)
FLOOR_A, FLOOR_B, FLOOR_LINE = (72, 78, 90), (66, 72, 84), (52, 57, 68)
HAZARD_YELLOW, HAZARD_BLACK = (230, 190, 40), (30, 30, 30)
CONSOLE, CONSOLE_DARK, CONSOLE_LEG, POD = (210, 214, 222), (150, 156, 168), (110, 116, 128), (60, 66, 80)
SCREEN_DARK = (18, 30, 40)
SPACE, STAR, PORTHOLE = (8, 10, 24), (240, 240, 255), (120, 130, 145)
PLANET, PLANET_SHADE = (220, 120, 70), (170, 80, 50)
METAL, METAL_DARK, GLASS = (170, 178, 190), (90, 98, 112), (100, 200, 220)
NEON = (230, 70, 200)


class StationScene(OfficeScene):
    """The same floor plan aboard a space station: hull plating, portholes onto space, consoles for desks."""

    fill = HULL
    title = "🚀 the station"
    TITLES = {"coffee": "Coffee replicator", "arcade": "VR arcade", "cooler": "Water recycler", "lunch": "Food synthesiser",
              "books": "Data archive", "plant": "Hydroponics", "pingpong": "Zero-g ping-pong", "foosball": "Foosball"}
    nap_title = "Sleep pods"

    def background_key(self, view: FrameView) -> Hashable:
        return "space"

    def starry(self, view: FrameView) -> bool:
        return True

    def paint_wall(self, c: Canvas) -> None:
        c.rect(0, 0, self.w, self.wall_h, HULL)
        for x in range(0, self.w, 12):
            c.rect(x, 0, 1, self.wall_h, PANEL_LINE)
            c.dot(x + 2, 3, RIVET)
            c.dot(x + 2, self.wall_h - 4, RIVET)
        c.rect(0, 1, self.w, 1, GLOW_DIM)
        c.rect(0, self.wall_h - 1, self.w, 1, GLOW)

    def paint_floor(self, c: Canvas) -> None:
        for y in range(self.wall_h, self.h):
            for x in range(self.w):
                on_line = x % 8 == 0 or (y - self.wall_h) % 6 == 0
                c.dot(x, y, FLOOR_LINE if on_line else FLOOR_A if (x // 8 + (y - self.wall_h) // 6) % 2 else FLOOR_B)
        for x in range(self.door_x - 1, self.door_x + 7):
            for y in range(self.wall_h, self.wall_h + 2):
                c.dot(x, y, HAZARD_YELLOW if (x + y) % 4 < 2 else HAZARD_BLACK)

    def paint_door(self, c: Canvas) -> None:
        x = self.door_x
        c.rect(x - 1, 2, 8, self.wall_h - 3, METAL_DARK)
        c.rect(x, 4, 3, self.wall_h - 5, METAL)
        c.rect(x + 3, 4, 3, self.wall_h - 5, METAL)
        c.rect(x + 3, 4, 1, self.wall_h - 5, METAL_DARK)
        for i in range(6):
            c.dot(x + i, 3, HAZARD_YELLOW if i % 2 else HAZARD_BLACK)

    def portholes(self) -> list[tuple[int, int, int]]:
        radius = max(3, min(8, (self.wall_h - 5) // 2))
        return [(wx + 9, 2 + radius, radius) for wx in self.window_xs()]

    def paint_windows(self, c: Canvas, sky: Colour) -> None:
        for index, (cx, cy, radius) in enumerate(self.portholes()):
            disc(c, cx, cy, radius, PORTHOLE)
            disc(c, cx, cy, radius - 1, SPACE)
            if index == 1:
                disc(c, cx + radius // 3, cy + radius // 4, max(1, radius // 2), PLANET)
                disc(c, cx + radius // 3 + 1, cy + radius // 4 + 1, max(1, radius // 3), PLANET_SHADE)

    def draw_stars(self, c: Canvas, t: int) -> None:
        for index, (cx, cy, radius) in enumerate(self.portholes()):
            for n, (dx, dy) in enumerate(((-3, -2), (2, -4), (-1, 3), (4, 1), (-4, 1))):
                if abs(dx) < radius - 1 and abs(dy) < radius - 1 and (t // 20 + n + index) % 5:
                    c.dot(cx + dx, cy + dy, STAR)

    def paint_whiteboard(self, c: Canvas) -> None:
        bx = self.board_x
        c.rect(bx, 2, 14, self.wall_h - 5, GLOW_DIM)
        c.rect(bx + 1, 3, 12, self.wall_h - 7, SCREEN_DARK)
        for i in range(3):
            c.rect(bx + 2, 4 + i * 2, 4 + (i * 3) % 8, 1, GLOW)
        c.rect(self.lounge_x + 4, 2, 7, 4, SCREEN_DARK)

    def draw_clock_hand(self, c: Canvas, t: int) -> None:
        cx = self.lounge_x + 4
        for digit in range(2):
            c.rect(cx + 1 + digit * 4, 3, 2, 2, GLOW if (t // 30 + digit) % 3 else GLOW_DIM)
        if (t // 5) % 2:
            c.dot(cx + 3, 3, GLOW)

    def paint_bookshelf(self, c: Canvas) -> None:
        x, bottom = self.shelf_x, self.wall_h + 1
        top = max(2, bottom - 22)
        c.rect(x, top, 12, bottom - top, METAL_DARK)
        c.rect(x + 1, top + 1, 10, bottom - top - 2, SCREEN_DARK)
        lights = [(90, 220, 120), GLOW, (240, 180, 60)]
        for row, y in enumerate(range(top + 3, bottom - 2, 3)):
            for i in range(5):
                c.dot(x + 2 + i * 2, y, lights[(row + i) % len(lights)])

    def paint_cooler(self, c: Canvas) -> None:
        ox, oy = self.cooler
        c.rect(ox, oy, 5, 4, GLASS)
        c.rect(ox - 1, oy + 4, 7, 10, METAL)
        c.rect(ox, oy + 6, 5, 1, GLOW)

    def paint_pot(self, c: Canvas) -> None:
        px, py = self.plant
        c.rect(px, py + 5, 6, 5, METAL_DARK)
        c.rect(px + 1, py + 5, 4, 1, GLOW)

    def paint_coffee_counter(self, c: Canvas) -> None:
        mx, my = self.coffee
        c.rect(mx - 2, my + 7, 10, 2, CONSOLE)
        c.rect(mx - 2, my + 9, 10, 3, CONSOLE_DARK)
        c.rect(mx, my, 6, 7, POD)
        c.rect(mx + 1, my + 1, 4, 2, SCREEN_DARK)
        c.rect(mx + 1, my + 4, 4, 1, GLOW)
        c.rect(mx + 2, my + 5, 2, 2, (240, 240, 235))

    def paint_kitchen(self, c: Canvas) -> None:
        fx, floor = self.fridge_x, self.wall_h + 3
        c.rect(fx, floor - 17, 8, 17, METAL)
        c.rect(fx + 1, floor - 15, 6, 4, SCREEN_DARK)
        c.rect(fx + 2, floor - 14, 4, 1, GLOW)
        c.rect(fx, floor - 9, 8, 1, METAL_DARK)
        ox = self.oven_x
        c.rect(ox, self.wall_h - 1, 12, 2, CONSOLE)
        c.rect(ox, self.wall_h + 1, 12, 3, CONSOLE_DARK)
        c.rect(ox + 1, self.wall_h - 7, 9, 6, POD)
        c.rect(ox + 2, self.wall_h - 6, 5, 4, SCREEN_DARK)
        c.dot(ox + 8, self.wall_h - 5, GLOW)

    def paint_table(self, c: Canvas) -> None:
        tx, ty = self.table
        c.rect(tx, ty, 21, 6, (30, 60, 80))
        c.rect(tx, ty, 21, 1, GLOW)
        c.rect(tx, ty + 5, 21, 1, GLOW)
        c.rect(tx + 10, ty - 2, 1, 8, GLOW_DIM)
        c.rect(tx + 3, ty + 7, 15, 1, GLOW_DIM)

    def paint_foosball(self, c: Canvas) -> None:
        super().paint_foosball(c)
        fx, fy = self.foosball
        c.rect(fx + 1, fy + 1, 7, 4, (40, 80, 110))
        c.rect(fx + 9, fy + 1, 6, 4, (40, 80, 110))

    def paint_arcade(self, c: Canvas) -> None:
        ax, ay = self.arcade
        c.rect(ax, ay, 9, 15, (40, 44, 60))
        c.rect(ax, ay, 9, 2, NEON)
        c.rect(ax + 1, ay + 9, 7, 2, SCREEN_DARK)
        c.dot(ax + 3, ay + 9, NEON)
        c.dot(ax + 5, ay + 9, GLOW)

    def paint_couch(self, c: Canvas) -> None:
        sx, sy = self.couch
        for pod in range(2):
            x = sx + pod * 12
            c.rect(x, sy - 2, 11, 6, METAL)
            c.rect(x + 1, sy - 1, 9, 2, (60, 120, 140))
            c.rect(x + 1, sy + 1, 9, 2, POD)
            c.dot(x + 9, sy + 3, GLOW)

    @staticmethod
    def draw_chair(c: Canvas, desk: tuple[int, int]) -> None:
        ox, oy = desk
        c.rect(ox + 2, oy + 2, 7, 4, POD)
        c.rect(ox + 2, oy + 2, 7, 1, GLOW_DIM)

    @staticmethod
    def draw_desk(c: Canvas, desk: tuple[int, int]) -> None:
        ox, oy = desk
        top = oy + 7
        c.rect(ox, top, 15, 2, CONSOLE)
        c.rect(ox, top + 2, 15, 3, CONSOLE_DARK)
        c.rect(ox + 1, top + 4, 13, 1, GLOW_DIM)
        c.rect(ox + 6, top + 5, 3, 2, CONSOLE_LEG)
        c.rect(ox + 9, top - 5, 6, 4, METAL_DARK)
        c.dot(ox + 11, top - 1, METAL_DARK)
        c.rect(ox + 10, top - 4, 4, 2, SCREEN_DARK)
        c.dot(ox + 3, top, GLOW)
        c.dot(ox + 5, top, (230, 230, 230))


def disc(c: Canvas, cx: int, cy: int, radius: int, colour: Colour) -> None:
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                c.dot(x, y, colour)


SCENE = StationScene
