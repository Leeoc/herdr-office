import math
import random
from typing import Callable, Hashable, Optional

from office.pathing import Rect
from office.people.person import Person
from office.people.venue import Activity, Game, Point
from office.render.canvas import Canvas, Colour
from office.scenes.base import FrameView, Scene

WALL, WALL_LINE, SKIRT = (70, 82, 102), (62, 73, 92), (52, 42, 36)
PLANK_A, PLANK_B, PLANK_GAP = (152, 113, 82), (143, 105, 76), (120, 88, 63)
DESK, DESK_DARK, DESK_LEG = (184, 139, 101), (140, 98, 66), (110, 76, 52)
MONITOR, SCREEN_OFF, CHAIR, CHAIR_EDGE = (38, 42, 50), (28, 32, 38), (48, 48, 58), (88, 88, 104)
PANTS, SHOE, EYE = (52, 62, 92), (28, 28, 30), (40, 32, 30)
ALARM_RED, PADDLE_RED = (255, 70, 70), (200, 50, 50)
DAY_SKY, DUSK_SKY, NIGHT_SKY = (135, 200, 240), (240, 150, 100), (25, 30, 62)
STAR, FRAME_GREY = (240, 240, 200), (205, 205, 215)
LABEL_INKS = {"working": (240, 200, 90), "done": (120, 220, 130), "blocked": (255, 90, 90)}
IDLE_INK = (150, 155, 165)
BALLOON, BALLOON_SHINE, STRING = (235, 70, 110), (255, 170, 190), (210, 210, 210)
SCREENS = {"done": (90, 200, 110)}
SHELF_WOOD, SHELF_BACK = (110, 74, 48), (64, 42, 28)
SPINES = [(200, 70, 70), (70, 120, 200), (230, 190, 80), (90, 160, 100), (170, 100, 190), (220, 140, 80)]
FRIDGE, FRIDGE_EDGE, METAL = (225, 230, 235), (170, 176, 184), (200, 200, 206)
OVEN_DARK, OVEN_LIT, FOOD = (40, 40, 48), (250, 210, 110), (200, 90, 60)
CAN, WATER = (70, 140, 200), (120, 180, 240)
FOOS_GREEN, FOOS_LINE, ROD = (60, 130, 70), (225, 235, 225), (170, 170, 180)
RED_TEAM, BLUE_TEAM, BALL_WHITE = (210, 60, 60), (60, 110, 210), (250, 250, 240)
READING_BOOK, READING_COVER = (240, 240, 230), (200, 60, 60)


class OfficeScene(Scene):
    """An open-plan office: rows of desks, a door, windows, and a lounge with coffee, ping-pong and an arcade."""

    fill = WALL
    title = "🏢 the office"
    TITLES = {"coffee": "Coffee machine", "arcade": "Arcade", "cooler": "Water cooler", "lunch": "Fridge and microwave",
              "books": "Bookshelf", "plant": "Watering the plant", "pingpong": "Ping-pong", "foosball": "Foosball"}
    nap_title = "Couch"
    SLOT_W, SLOT_H = 20, 18
    DESK_W = 15

    def __init__(self, w: int, h: int, closed: frozenset[str] = frozenset()):
        self.closed = closed
        self.wall_h = max(10, int(h * 0.26) // 2 * 2)
        self.lounge_w = max(30, min(56, w // 3))
        self.lounge_x = w - self.lounge_w
        self.door_x = 3
        cols = max(1, (self.lounge_x - 6) // self.SLOT_W)
        rows = max(1, (h - self.wall_h - 4) // self.SLOT_H)
        self.desks = [(4 + c * self.SLOT_W, self.wall_h + 3 + r * self.SLOT_H) for r in range(rows) for c in range(cols)]
        self.couch = (self.lounge_x + 6, h - 9)
        self.cooler = (self.lounge_x + self.lounge_w - 9, self.wall_h - 4)
        self.board_x = max(2, self.lounge_x - 18)
        self.coffee = (self.cooler[0] - 12, self.wall_h - 8)
        self.table = (self.lounge_x + self.lounge_w // 2 - 10, self.wall_h + 20)
        self.arcade = (self.lounge_x + self.lounge_w - 11, h - 24)
        self.plant = (self.lounge_x + 2, self.wall_h + 1)
        self.shelf_x = self.board_x - 16
        self.fridge_x = self.lounge_x + 11
        self.oven_x = self.lounge_x + 20
        self.foosball = (self.lounge_x + self.lounge_w // 2 - 8, self.table[1] + 22)
        self.places = self.lay_out_activities()
        self.lay_out_games()
        super().__init__(w, h, closed)

    def has(self, amenity: str) -> bool:
        return amenity not in self.closed

    def lay_out_activities(self) -> tuple[Activity, ...]:
        floor_y = float(self.wall_h + 1)
        return (
            Activity("coffee", self.TITLES["coffee"], ((float(self.coffee[0]), floor_y),), (3.6, 7.2), 0.25, gives_mug=True),
            Activity("arcade", self.TITLES["arcade"], ((float(self.arcade[0] + 1), float(self.arcade[1] + 7)),), (18.0, 36.0), 0.17),
            Activity("cooler", self.TITLES["cooler"], ((float(self.cooler[0] - 7), floor_y),
                                                (float(self.cooler[0]), float(self.wall_h + 11))), (4.8, 10.8), 0.13),
            Activity("lunch", self.TITLES["lunch"], ((float(self.oven_x + 2), floor_y),), (8.0, 15.0), 0.12),
            Activity("books", self.TITLES["books"], ((float(self.shelf_x + 3), float(self.wall_h - 6)),), (6.0, 12.0), 0.12, pose="read"),
            Activity("plant", self.TITLES["plant"], ((float(self.plant[0] + 7), float(self.wall_h + 2)),), (3.0, 5.0), 0.06,
                     pose="water"),
        )

    def lay_out_games(self) -> None:
        tx, ty = self.table
        fx, fy = self.foosball
        self.game_list = (
            Game("pingpong", self.TITLES["pingpong"], ((float(tx - 7), float(ty - 4)), (float(tx + 22), float(ty - 4))), (1, -1), 108, 58),
            Game("foosball", self.TITLES["foosball"], ((float(fx - 6), float(fy - 6)), (float(fx - 6), float(fy)),
                                          (float(fx + 17), float(fy - 6)), (float(fx + 17), float(fy))), (1, 1, -1, -1), 150, 60),
        )

    def desk_count(self) -> int:
        return len(self.desks)

    def seat(self, desk: int) -> Point:
        ox, oy = self.desks[desk]
        return float(ox + 4), float(oy + 1)

    def desk_stand(self, desk: int) -> Point:
        x, y = self.seat(desk)
        return x, y - 2

    def entrance(self) -> Point:
        return float(self.door_x), float(self.wall_h - 6)

    def nap_spot(self, index: int) -> Point:
        return float(self.couch[0] + 2 + (index % 2) * 10), float(self.couch[1] - 1)

    def meeting_spot(self, index: int) -> Point:
        return float(self.board_x - 1 + (index % 3) * 6), float(self.wall_h - 7 + (index // 3) * 10)

    def wander_spot(self, rng: random.Random) -> Point:
        return self.open_spot_in(Rect(self.lounge_x + 2, self.wall_h + 2, self.w - 10 - self.lounge_x, self.h - 24 - self.wall_h), rng)

    def activities(self) -> tuple[Activity, ...]:
        return self.places

    def games(self) -> tuple[Game, ...]:
        return self.game_list

    def floor(self) -> Rect:
        top = self.wall_h - 7
        return Rect(0, top, self.w - 6, self.h - 8 - top)

    def obstacles(self) -> list[Rect]:
        tx, ty = self.table
        ax, ay = self.arcade
        sx, sy = self.couch
        mx, my = self.coffee
        furniture = {
            "cooler": [Rect(self.cooler[0] - 1, self.wall_h, 7, 10)],
            "plant": [Rect(self.plant[0], self.plant[1] + 5, 6, 5)],
            "coffee": [Rect(mx - 2, my + 7, 10, 5)],
            "pingpong": [Rect(tx, ty, 21, 9)],
            "arcade": [Rect(ax, ay + 4, 9, 9)],
            "naps": [Rect(sx - 2, sy - 3, 28, 9)],
            "lunch": [Rect(self.fridge_x, self.wall_h, 8, 4), Rect(self.oven_x, self.wall_h - 1, 12, 5)],
            "foosball": [Rect(*self.foosball, 16, 7)],
        }
        desks = [Rect(ox, oy + 9, self.DESK_W, 5) for ox, oy in self.desks]
        return desks + [rect for name, rects in furniture.items() if self.has(name) for rect in rects]

    def desk_at(self, px: int, py: int) -> Optional[int]:
        return next((i for i, (ox, oy) in enumerate(self.desks) if ox <= px < ox + self.DESK_W and oy <= py < oy + 14), None)

    def person_at(self, px: int, py: int, people: list[Person]) -> Optional[Person]:
        hit = next((p for p in people if touches(p, px, py) or touches(p, px, py + 1)), None)
        desk = self.desk_at(px, py) if hit is None else None
        return hit or next((p for p in people if desk is not None and p.desk == desk), None)

    def pet_spot(self, t: int) -> tuple[int, int, int]:
        span = max(10, self.w - 12)
        pos = t % (2 * span)
        facing = 1 if pos < span else -1
        return 2 + (pos if facing == 1 else 2 * span - pos), self.h - 3, facing

    def lamps(self, view: FrameView) -> list[Point]:
        if not view.night:
            return []
        return [(ox + 1, oy + 4) for ox, oy in self.working_desks(view.people)]

    def working_desks(self, people: list[Person]) -> list[tuple[int, int]]:
        return [self.desks[p.desk] for p in people if p.desk is not None and p.status == "working" and p.desk < len(self.desks)]

    def background_key(self, view: FrameView) -> Hashable:
        return self.sky(view.hour, view.night)

    @staticmethod
    def sky(hour: int, night: bool) -> Colour:
        sky = DAY_SKY if 8 <= hour < 17 else DUSK_SKY if 17 <= hour < 20 or 6 <= hour < 8 else NIGHT_SKY
        if night and sky == DAY_SKY:
            return NIGHT_SKY
        return DAY_SKY if not night and sky == NIGHT_SKY else sky

    def starry(self, view: FrameView) -> bool:
        return self.sky(view.hour, view.night) == NIGHT_SKY

    def paint_background(self, c: Canvas, view: FrameView) -> None:
        self.paint_wall(c)
        self.paint_floor(c)
        self.paint_door(c)
        self.paint_windows(c, self.sky(view.hour, view.night))
        self.paint_whiteboard(c)
        if self.has("books"):
            self.paint_bookshelf(c)
        self.paint_lounge(c)
        self.paint_desks(c)

    def paint_wall(self, c: Canvas) -> None:
        c.rect(0, 0, self.w, self.wall_h, WALL)
        for x in range(0, self.w, 8):
            c.rect(x, 0, 1, self.wall_h, WALL_LINE)
        c.rect(0, self.wall_h - 1, self.w, 1, SKIRT)

    def paint_floor(self, c: Canvas) -> None:
        for y in range(self.wall_h, self.h):
            for x in range(self.w):
                offset = x + (y // 3) * 7
                c.dot(x, y, PLANK_GAP if offset % 14 == 0 else PLANK_A if (offset // 14) % 2 else PLANK_B)

    def paint_door(self, c: Canvas) -> None:
        c.rect(self.door_x - 1, 2, 8, self.wall_h - 3, (96, 66, 46))
        c.rect(self.door_x, 3, 6, self.wall_h - 4, (122, 84, 58))
        c.dot(self.door_x + 5, self.wall_h // 2, (230, 200, 90))

    def window_xs(self) -> range:
        return range(16, max(17, self.board_x - 37), 34)

    def paint_windows(self, c: Canvas, sky: Colour) -> None:
        for wx in self.window_xs():
            c.rect(wx, 2, 18, self.wall_h - 5, FRAME_GREY)
            c.rect(wx + 1, 3, 16, self.wall_h - 7, sky)
            c.rect(wx + 8, 3, 1, self.wall_h - 7, FRAME_GREY)

    def paint_whiteboard(self, c: Canvas) -> None:
        bx = self.board_x
        c.rect(bx, 2, 14, self.wall_h - 5, (235, 238, 240))
        for i, colour in enumerate([(60, 120, 220), (220, 70, 70), (60, 160, 90)]):
            c.rect(bx + 2, 4 + i * 2, 4 + (i * 3) % 8, 1, colour)
        cx = self.lounge_x + 4
        c.rect(cx, 2, 5, 5, (235, 235, 235))
        c.dot(cx + 2, 4, (30, 30, 30))

    def paint_lounge(self, c: Canvas) -> None:
        painters = {"cooler": self.paint_cooler, "plant": self.paint_pot, "coffee": self.paint_coffee_counter,
                    "lunch": self.paint_kitchen, "pingpong": self.paint_table, "foosball": self.paint_foosball,
                    "arcade": self.paint_arcade, "naps": self.paint_couch}
        for name, paint in painters.items():
            if self.has(name):
                paint(c)

    def paint_cooler(self, c: Canvas) -> None:
        ox, oy = self.cooler
        c.rect(ox, oy, 5, 4, (120, 190, 240))
        c.rect(ox - 1, oy + 4, 7, 10, (225, 232, 240))
        c.dot(ox + 1, oy + 7, (80, 120, 220))
        c.dot(ox + 3, oy + 7, (220, 80, 80))

    def paint_pot(self, c: Canvas) -> None:
        px, py = self.plant
        c.rect(px, py + 5, 6, 5, (165, 92, 60))

    def paint_coffee_counter(self, c: Canvas) -> None:
        mx, my = self.coffee
        c.rect(mx - 2, my + 7, 10, 2, DESK)
        c.rect(mx - 2, my + 9, 10, 3, DESK_DARK)
        c.rect(mx, my, 6, 7, (52, 54, 62))
        c.rect(mx + 1, my + 1, 4, 2, (30, 30, 34))
        c.rect(mx + 2, my + 5, 2, 2, (240, 240, 235))

    def paint_bookshelf(self, c: Canvas) -> None:
        x, bottom = self.shelf_x, self.wall_h + 1
        top = max(2, bottom - 22)
        c.rect(x, top, 12, bottom - top, SHELF_WOOD)
        c.rect(x + 1, top + 1, 10, bottom - top - 2, SHELF_BACK)
        for shelf, y in enumerate(range(bottom - 2, top + 3, -6)):
            c.rect(x + 1, y, 10, 1, SHELF_WOOD)
            for i in range(9):
                height = 3 + (i * 7 + shelf) % 2
                c.rect(x + 1 + i + (i > 4), y - height, 1, height, SPINES[(i + shelf * 2) % len(SPINES)])

    def paint_kitchen(self, c: Canvas) -> None:
        fx, floor = self.fridge_x, self.wall_h + 3
        c.rect(fx, floor - 17, 8, 17, FRIDGE)
        c.rect(fx, floor - 11, 8, 1, FRIDGE_EDGE)
        c.rect(fx + 6, floor - 15, 1, 3, FRIDGE_EDGE)
        c.rect(fx + 6, floor - 9, 1, 4, FRIDGE_EDGE)
        ox = self.oven_x
        c.rect(ox, self.wall_h - 1, 12, 2, DESK)
        c.rect(ox, self.wall_h + 1, 12, 3, DESK_DARK)
        c.rect(ox + 1, self.wall_h - 7, 9, 6, METAL)
        c.rect(ox + 2, self.wall_h - 6, 5, 4, OVEN_DARK)
        c.dot(ox + 8, self.wall_h - 6, (90, 90, 96))
        c.dot(ox + 8, self.wall_h - 4, (90, 90, 96))

    def paint_foosball(self, c: Canvas) -> None:
        fx, fy = self.foosball
        c.rect(fx, fy, 16, 6, FOOS_GREEN)
        c.rect(fx, fy, 16, 1, FOOS_LINE)
        c.rect(fx, fy + 5, 16, 1, FOOS_LINE)
        c.rect(fx + 8, fy + 1, 1, 4, FOOS_LINE)
        for i, rod_x in enumerate((fx + 3, fx + 6, fx + 10, fx + 13)):
            c.rect(rod_x, fy - 1, 1, 8, ROD)
            c.dot(rod_x, fy + 2, RED_TEAM if i % 2 == 0 else BLUE_TEAM)
            c.dot(rod_x, fy + 4, RED_TEAM if i % 2 == 0 else BLUE_TEAM)
        c.rect(fx + 1, fy + 6, 1, 3, DESK_LEG)
        c.rect(fx + 14, fy + 6, 1, 3, DESK_LEG)

    def paint_table(self, c: Canvas) -> None:
        tx, ty = self.table
        c.rect(tx, ty, 21, 6, (38, 112, 88))
        c.rect(tx, ty, 21, 1, (230, 235, 235))
        c.rect(tx, ty + 5, 21, 1, (230, 235, 235))
        c.rect(tx + 10, ty - 2, 1, 8, (235, 235, 235))
        c.rect(tx + 1, ty + 6, 1, 3, DESK_LEG)
        c.rect(tx + 19, ty + 6, 1, 3, DESK_LEG)

    def paint_arcade(self, c: Canvas) -> None:
        ax, ay = self.arcade
        c.rect(ax, ay, 9, 15, (70, 44, 130))
        c.rect(ax, ay, 9, 2, (250, 200, 60))
        c.rect(ax + 1, ay + 9, 7, 2, (40, 28, 80))
        c.dot(ax + 3, ay + 9, (230, 60, 60))
        c.dot(ax + 5, ay + 9, (60, 140, 230))

    def paint_couch(self, c: Canvas) -> None:
        sx, sy = self.couch
        c.rect(sx, sy - 3, 24, 3, (110, 55, 66))
        c.rect(sx, sy, 24, 4, (134, 66, 80))
        c.rect(sx - 2, sy - 2, 2, 6, (110, 55, 66))
        c.rect(sx + 24, sy - 2, 2, 6, (110, 55, 66))
        c.rect(sx + 2, sy + 4, 1, 2, DESK_LEG)
        c.rect(sx + 21, sy + 4, 1, 2, DESK_LEG)

    def paint_foreground(self, c: Canvas, view: FrameView) -> None:
        t = view.t
        self.draw_alarm(c, view.alarm and (t // 3) % 2 == 0)
        if self.starry(view):
            self.draw_stars(c, t)
        self.draw_clock_hand(c, t)
        busy = {p.state for p in view.people if p.arrived()}
        if self.has("plant"):
            self.draw_plant(c, t, "plant" in busy)
        if self.has("coffee"):
            self.draw_coffee_machine(c, t)
        if self.has("arcade"):
            self.draw_arcade_screen(c, t, "arcade" in busy)
        self.draw_microwave(c, t, "lunch" in busy)
        if "books" in busy:
            c.rect(self.shelf_x + 4, self.wall_h - 6, 1, 4, SHELF_BACK)
        for _, draw in sorted(self.drawables(view), key=lambda item: item[0]):
            draw(c)
        self.draw_pingpong_ball(c, view)
        self.draw_foosball_ball(c, view)

    def drawables(self, view: FrameView) -> list[tuple[float, Callable[[Canvas], None]]]:
        # Sorted by the row each thing stands on. Desks are in the cached background and are
        # drawn again only when someone stands behind one.
        owners = {p.desk: p for p in view.people if p.desk is not None and p.desk < len(self.desks)}
        sprites = [(sprite_box(p), self.baseline(p)) for p in view.people]
        items = []
        for index, desk in enumerate(self.desks):
            owner = owners.get(index)
            if self.hidden_behind(desk, sprites):
                items.append((desk[1] + 5, lambda c, d=desk: self.draw_chair(c, d)))
                items.append((desk[1] + 13, lambda c, d=desk: self.draw_desk(c, d)))
            if owner is not None:
                items.append((desk[1] + 13.5, lambda c, d=desk, o=owner: self.draw_desk_life(c, d, o, view)))
        for person in view.people:
            items.append((self.baseline(person), lambda c, p=person: self.draw_person(c, p, view.t, view.confetti)))
        if view.pet is not None:
            x, y, facing = self.pet_spot(view.t)
            items.append((y, lambda c: self.draw_pet(c, view.pet, x, y, facing, view.t)))
        return items

    @staticmethod
    def baseline(person: Person) -> float:
        return person.y + (1 if person.pose() == "lie" else 7)

    @staticmethod
    def hidden_behind(desk: tuple[int, int], sprites: list[tuple[Rect, float]]) -> bool:
        ox, oy = desk
        whole = Rect(ox, oy + 2, 15, 12)
        nearby = [(box, baseline) for box, baseline in sprites if box.overlaps(whole)]
        if not nearby:
            return False
        parts = ((Rect(ox + 2, oy + 2, 7, 4), oy + 5), (Rect(ox + 9, oy + 2, 6, 5), oy + 13), (Rect(ox, oy + 7, 15, 7), oy + 13))
        return any(box.overlaps(part) and baseline < part_baseline for box, baseline in nearby for part, part_baseline in parts)

    def draw_alarm(self, c: Canvas, on: bool) -> None:
        c.rect(self.door_x + 1, 0, 4, 2, (255, 60, 60) if on else (90, 40, 40))
        if on:
            for gx in range(self.door_x - 3, self.door_x + 9):
                c.dot(gx, 2, (150, 70, 80))

    def draw_stars(self, c: Canvas, t: int) -> None:
        for wx in self.window_xs():
            c.dot(wx + 3 + (t // 40) % 3, 4, STAR)
            c.dot(wx + 12, 5, STAR)

    def draw_clock_hand(self, c: Canvas, t: int) -> None:
        cx = self.lounge_x + 4
        c.dot(cx + 2, 3, (30, 30, 30))
        c.dot(cx + 3 if (t // 30) % 2 else cx + 1, 4, (200, 50, 50))

    def draw_plant(self, c: Canvas, t: int, watered: bool) -> None:
        px, py = self.plant
        for i, (dx, dy) in enumerate([(1, 0), (4, 1), (2, 2), (0, 3), (5, 3), (3, 4), (-1, 1), (6, 2)]):
            c.dot(px + dx, py + dy - 1 + (1 if (t // 25 + i) % 7 == 0 else 0), (60, 150 + i * 6, 70))
        if watered:
            c.dot(px + 2, py - 2, (90, 200, 90))
            c.dot(px + 4, py - 1, (90, 200, 90))

    def draw_coffee_machine(self, c: Canvas, t: int) -> None:
        mx, my = self.coffee
        c.dot(mx + 4, my + 1, (90, 220, 120) if (t // 10) % 2 else (40, 120, 60))
        if (t // 6) % 4 == 0:
            c.dot(mx + 2, my + 4 - (t // 2) % 2, (200, 205, 215))

    def draw_microwave(self, c: Canvas, t: int, cooking: bool) -> None:
        if not cooking:
            return
        ox, top = self.oven_x, self.wall_h - 6
        c.rect(ox + 2, top, 5, 4, OVEN_LIT)
        spin = [(0, 0), (1, 0), (1, 1), (0, 1)][(t // 3) % 4]
        c.rect(ox + 3 + spin[0], top + 1 + spin[1], 2, 2, FOOD)
        c.dot(ox + 8, top + 2, (90, 220, 120))

    def draw_arcade_screen(self, c: Canvas, t: int, playing: bool) -> None:
        ax, ay = self.arcade
        screen = [(60, 220, 255), (255, 80, 160), (120, 255, 120)][(t // 4) % 3] if playing else (30, 30, 50)
        c.rect(ax + 1, ay + 3, 7, 5, screen)
        if playing:
            c.dot(ax + 2 + (t // 2) % 5, ay + 5, (255, 255, 255))

    def paint_desks(self, c: Canvas) -> None:
        for desk in self.desks:
            self.draw_chair(c, desk)
            self.draw_desk(c, desk)

    @staticmethod
    def draw_chair(c: Canvas, desk: tuple[int, int]) -> None:
        ox, oy = desk
        c.rect(ox + 2, oy + 2, 7, 4, CHAIR)

    @staticmethod
    def draw_desk(c: Canvas, desk: tuple[int, int]) -> None:
        ox, oy = desk
        top = oy + 7
        c.rect(ox, top, 15, 2, DESK)
        c.rect(ox, top + 2, 15, 3, DESK_DARK)
        c.rect(ox + 1, top + 5, 1, 2, DESK_LEG)
        c.rect(ox + 13, top + 5, 1, 2, DESK_LEG)
        c.rect(ox + 9, top - 5, 6, 4, MONITOR)
        c.dot(ox + 11, top - 1, MONITOR)
        c.rect(ox + 10, top - 4, 4, 2, SCREEN_OFF)
        c.dot(ox + 3, top, (90, 90, 100))
        c.dot(ox + 5, top, (230, 230, 230))

    def draw_desk_life(self, c: Canvas, desk: tuple[int, int], owner: Person, view: FrameView) -> None:
        ox, oy = desk
        top = oy + 7
        self.draw_screen(c, ox, top, owner.status, view.t)
        if owner.state == "spin" and not owner.moving():
            c.rect(ox + (2 if (view.t // 2) % 2 else 8), oy + 2, 1, 4, CHAIR_EDGE)
        if view.night and owner.status == "working":
            c.rect(ox + 1, top - 4, 1, 4, (70, 70, 76))
            c.rect(ox, top - 5, 3, 1, (255, 214, 120))
        if owner.first_day(view.t):
            self.draw_balloon(c, ox, top, view.t)
        c.label(ox, (oy + 13) // 2, owner.label[: self.SLOT_W - 3], LABEL_INKS.get(owner.status, IDLE_INK))

    def draw_screen(self, c: Canvas, ox: int, top: int, status: str, t: int) -> None:
        if status == "working":
            c.rect(ox + 10, top - 4, 4, 2, (70, 120, 190))
            c.rect(ox + 10, top - 4, 1 + (t // 2) % 4, 1, (150, 220, 255))
            c.rect(ox + 10, top - 3, 1 + (t // 3 + 2) % 4, 1, (120, 230, 160))
        elif status == "blocked":
            c.rect(ox + 10, top - 4, 4, 2, (230, 70, 70) if (t // 4) % 2 else (120, 30, 30))
        elif status in SCREENS:
            c.rect(ox + 10, top - 4, 4, 2, SCREENS[status])

    def draw_balloon(self, c: Canvas, ox: int, top: int, t: int) -> None:
        bob = (t // 8) % 2
        c.rect(ox + 13, top - 10 - bob, 1, 5 + bob, STRING)
        c.rect(ox + 12, top - 14 - bob, 3, 4, BALLOON)
        c.dot(ox + 12, top - 14 - bob, BALLOON_SHINE)
        c.dot(ox + 13, top - 10 - bob, BALLOON)

    def draw_person(self, c: Canvas, p: Person, t: int, confetti: tuple[Colour, ...]) -> None:
        pose = p.pose()
        x, y = int(p.x), int(p.y)
        if pose == "lie":
            self.draw_napper(c, p, x, y, t)
            return
        if pose == "cheer" and (t // 3) % 2:
            y -= 1
        put = facing_pen(c, x, y, p.facing)
        look = p.look
        self.draw_head(put, look, blinking(p, t))
        for dx in range(5):
            put(dx, 3, look.shirt)
            put(dx, 4, look.shirt)
        for dx in (1, 2, 3):
            put(dx, 5, look.shirt)
        if pose == "sit":
            if (t // 2) % 2:
                put(4, 4, look.skin)
            return
        if pose == "hand":
            self.draw_raised_hand(put, look, t)
        if pose == "cheer":
            self.draw_cheer(c, put, p, x, y, t, confetti)
        if p.has_mug(t) and pose in ("stand", "walk"):
            put(5, 4, (240, 240, 235))
            put(5, 3, (120, 72, 40))
        if pose == "play" and p.state == "pingpong":
            put(5, 3, look.skin)
            put(6, 2, PADDLE_RED)
            put(6, 3, PADDLE_RED)
        elif pose == "play":
            put(5, 3, look.skin)
            put(5, 4 - (t // 3) % 2, look.skin)
        if pose == "read":
            put(4, 3, READING_BOOK)
            put(5, 3, READING_COVER)
            put(5, 4, READING_COVER)
        if pose == "water":
            put(5, 3, CAN)
            put(6, 3, CAN)
            put(7, 2, CAN)
            if (t // 2) % 2:
                put(8, 3 + (t // 4) % 3, WATER)
        step = (t // 2) % 2 if pose == "walk" else 0
        put(1 + step, 6, PANTS)
        put(3 - step, 6, PANTS)
        put(1 + step, 7, SHOE)
        put(3 - step, 7, SHOE)

    @staticmethod
    def draw_head(put, look, eyes_shut: bool) -> None:
        for dx in (1, 2, 3):
            put(dx, 0, look.hair)
            put(dx, 1, look.skin)
            put(dx, 2, look.skin)
        put(1, 1, look.hair)
        put(3, 1, look.skin if eyes_shut else EYE)

    @staticmethod
    def draw_raised_hand(put, look, t: int) -> None:
        put(4, 2, look.shirt)
        put(5, 1, look.skin)
        put(5, 0, look.skin)
        if (t // 4) % 2:
            put(2, -5, ALARM_RED)
            put(2, -4, ALARM_RED)
            put(2, -2, ALARM_RED)

    @staticmethod
    def draw_cheer(c: Canvas, put, p: Person, x: int, y: int, t: int, confetti: tuple[Colour, ...]) -> None:
        for side in (-1, 5):
            put(side, 2, p.look.shirt)
            put(side, 1, p.look.skin)
        rng = random.Random(p.seed * 7919 + t)
        for _ in range(4):
            c.dot(x + rng.randint(-3, 7), y - rng.randint(1, 5), rng.choice(confetti))

    @staticmethod
    def draw_napper(c: Canvas, p: Person, x: int, y: int, t: int) -> None:
        c.rect(x, y, 2, 2, p.look.hair)
        c.rect(x + 2, y, 2, 2, p.look.skin)
        c.rect(x + 4, y, 5, 2, p.look.shirt)
        c.rect(x + 9, y, 3, 2, PANTS)
        c.dot(x + 12, y, SHOE)
        rise = (t // 5) % 4
        c.dot(x + 2 + rise, y - 2 - rise, (200, 210, 230))

    @staticmethod
    def everyone_at(game_name: str, view: FrameView) -> bool:
        playing = [p for p in view.people if p.game is not None and p.game[0].name == game_name]
        return bool(playing) and len(playing) == len(playing[0].game[0].spots) and all(p.arrived() for p in playing)

    def draw_foosball_ball(self, c: Canvas, view: FrameView) -> None:
        if not self.everyone_at("foosball", view):
            return
        fx, fy = self.foosball
        rng = random.Random(view.t // 4)
        c.dot(fx + 2 + rng.randint(0, 11), fy + 1 + rng.randint(0, 3), BALL_WHITE)

    def draw_pingpong_ball(self, c: Canvas, view: FrameView) -> None:
        if not self.everyone_at("pingpong", view):
            return
        tx, ty = self.table
        period = 26
        phase = (view.t % (2 * period)) / period
        frac = phase if phase <= 1 else 2 - phase
        bx = tx + 1 + frac * 18
        by = ty - 1 - 5 * math.sin(math.pi * (frac * 2 % 1))
        c.dot(bx, by, (250, 250, 240))
        c.dot(bx, ty + 2, (28, 84, 66))

    @staticmethod
    def draw_pet(c: Canvas, pet, x: int, y: int, facing: int, t: int) -> None:
        for dx, dy, colour in pet.pixels(t):
            c.dot(x + dx if facing == 1 else x + 5 - dx, y + dy, colour)


def facing_pen(c: Canvas, x: int, y: int, facing: int) -> Callable[[int, int, Colour], None]:
    if facing >= 0:
        return lambda dx, dy, colour: c.dot(x + dx, y + dy, colour)
    return lambda dx, dy, colour: c.dot(x + 4 - dx, y + dy, colour)


def blinking(p: Person, t: int) -> bool:
    return (t + p.seed * 13) % 47 == 0


def sprite_box(p: Person) -> Rect:
    if p.pose() == "sit":
        return Rect(int(p.x), int(p.y), 5, 7)
    return Rect(int(p.x) - 2, int(p.y) - 1, 9, 9)


def touches(p: Person, px: int, py: int) -> bool:
    return int(p.x) - 1 <= px <= int(p.x) + 6 and int(p.y) - 2 <= py <= int(p.y) + 8


SCENE = OfficeScene
