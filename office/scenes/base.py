import random
from abc import abstractmethod
from dataclasses import dataclass
from typing import Hashable, Optional

from office.pathing import Rect, WalkGrid
from office.people.person import Person
from office.people.venue import Point, Venue
from office.pets import Pet
from office.render.canvas import Canvas, Colour


@dataclass
class FrameView:
    """Everything a scene needs to draw one frame."""

    people: list[Person]
    t: int
    hour: int
    night: bool
    alarm: bool
    pet: Optional[Pet]
    confetti: tuple[Colour, ...]


class Scene(Venue):
    """A place the people live in, laid out for one canvas size.

    A scene is a Venue (the places people ask for) plus everything about how it looks. Amenities
    named in `closed` are left out of the room. To add a scene, subclass this in a new module under
    office/scenes and name it in the config.
    """

    footprint = Rect(1, 6, 3, 2)
    fill: Colour = (0, 0, 0)
    title = "the office"

    def __init__(self, w: int, h: int, closed: frozenset[str] = frozenset()):
        self.w, self.h, self.closed = w, h, closed
        self.grid = WalkGrid(self.floor(), self.obstacles(), self.footprint, cell=3)

    def route(self, start: Point, goal: Point) -> list[Point]:
        return self.grid.route(start, goal)

    def open_spot_in(self, area: Rect, rng: random.Random, tries: int = 20) -> Point:
        """A random spot in `area` where a person can stand."""
        spot = (float(area.x), float(area.y))
        for _ in range(tries):
            spot = (float(rng.randint(area.x, area.x + area.w)), float(rng.randint(area.y, area.y + area.h)))
            if self.grid.is_open(self.grid.cell_of(spot)):
                return spot
        return spot

    @abstractmethod
    def floor(self) -> Rect:
        """Where a person's anchor (top-left of their head) may be."""

    @abstractmethod
    def obstacles(self) -> list[Rect]:
        """Furniture people walk round, as the floor area it covers."""

    @abstractmethod
    def background_key(self, view: FrameView) -> Hashable:
        """Whatever the static background depends on; it is redrawn only when this changes."""

    @abstractmethod
    def paint_background(self, canvas: Canvas, view: FrameView) -> None: ...

    @abstractmethod
    def paint_foreground(self, canvas: Canvas, view: FrameView) -> None:
        """Animated props and people, over a copy of the cached background."""

    @abstractmethod
    def draw_person(self, canvas: Canvas, person: Person, t: int, confetti: tuple[Colour, ...]) -> None: ...

    @abstractmethod
    def lamps(self, view: FrameView) -> list[Point]:
        """Where light falls at night."""

    @abstractmethod
    def person_at(self, px: int, py: int, people: list[Person]) -> Optional[Person]:
        """Who a click at pixel (px, py) means: the person there, or whoever owns the furniture there."""

    @abstractmethod
    def pet_spot(self, t: int) -> tuple[int, int, int]:
        """Where the pet is at tick `t`, as (x, y, facing)."""
