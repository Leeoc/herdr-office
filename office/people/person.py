import random
from dataclasses import dataclass
from typing import Callable, Optional

from office.people.timing import ticks
from office.people.venue import Activity, Game, Point, Venue

Colour = tuple[int, int, int]

WORKING, DONE, BLOCKED = "working", "done", "blocked"
AT_DESK_STATUSES = (WORKING, DONE, BLOCKED)
RESTING_STATUSES = ("idle", "unknown")

WANDER = Activity("wander", "Wandering", (), (3.0, 9.6), 0.45)
SPIN_TICKS = ticks(1.6)
MUG_TICKS = ticks(48)
FIRST_DAY_TICKS = ticks(600)
WALK_X, WALK_Y = 1.25, 0.9

POSES = {"typing": "sit", "spin": "sit", "cheer": "cheer", "hand": "hand", "nap": "lie"}

FreeSpot = Callable[[Activity], Optional[Point]]


@dataclass(frozen=True)
class Look:
    hair: Colour
    skin: Colour
    shirt: Colour

    @classmethod
    def for_key(cls, key: str, palette: dict) -> "Look":
        """Same key, same look, so an agent keeps their appearance across restarts."""
        rng = random.Random(key)
        hair, skin, shirt = rng.choice(palette["hairs"]), rng.choice(palette["skins"]), rng.choice(palette["shirts"])
        return cls(tuple(hair), tuple(skin), tuple(shirt))


class Person:
    """One agent in the office: who they are, what herdr says they are doing, and how they behave."""

    def __init__(self, key: str, look: Look, at: Point, t: int, first_day: bool):
        self.key, self.look = key, look
        self.rng = random.Random(key + "walk")
        self.seed = sum(map(ord, key))
        self.label, self.status, self.since = key, "idle", 0.0
        self.pane_id, self.space, self.title, self.ticket = key, None, "", None
        self.x, self.y = at
        self.facing = 1
        self.first_day_until = t + FIRST_DAY_TICKS if first_day else -1
        self.leaving = False
        self.desk: Optional[int] = None
        self.meeting: Optional[int] = None
        self.game: Optional[tuple[Game, int]] = None
        self.nap_index = 0
        self.state = "arrive"
        self.goal: Optional[Point] = None
        self.route: list[Point] = []
        self.activity: Optional[Activity] = None
        self.leisure_spot: Optional[Point] = None
        self.linger = 0
        self.mug_until = -1
        self.spin_until = -1
        self.details: Optional[dict] = None

    def update(self, agent, ticket: Optional[str], t: int) -> None:
        if self.status == WORKING and agent.status == DONE and self.desk is not None:
            self.spin_until = t + SPIN_TICKS
        self.label, self.status, self.since = agent.label, agent.status, agent.since
        self.pane_id, self.space, self.title, self.ticket = agent.pane_id, agent.space, agent.title, ticket
        self.leaving = False

    def tick(self, venue: Venue, t: int, now: float, nap_after: float, free_spot: FreeSpot) -> None:
        state, spot = self.intent(venue, t, now, nap_after, free_spot)
        if self.activity is not None and state != self.activity.name:
            self.activity = None
        self.state = state
        self.head_for(venue, spot)
        if self.route:
            self.walk()
        elif self.linger > 0:
            self.linger -= 1
        self.facing = self.facing_at_rest(t)

    def intent(self, venue: Venue, t: int, now: float, nap_after: float, free_spot: FreeSpot) -> tuple[str, Point]:
        if self.leaving:
            return "leave", venue.entrance()
        if self.meeting is not None:
            return "meeting", venue.meeting_spot(self.meeting)
        if self.game is not None:
            game, place = self.game
            return game.name, game.spots[place]
        if self.desk is not None and self.status in AT_DESK_STATUSES:
            return self.desk_intent(venue, t)
        if self.napping(now, nap_after):
            return "nap", venue.nap_spot(self.nap_index)
        return self.leisure_intent(venue, t, free_spot)

    def desk_intent(self, venue: Venue, t: int) -> tuple[str, Point]:
        if self.status == WORKING:
            return "typing", venue.seat(self.desk)
        if t < self.spin_until:
            return "spin", venue.seat(self.desk)
        return ("cheer" if self.status == DONE else "hand"), venue.desk_stand(self.desk)

    def leisure_intent(self, venue: Venue, t: int, free_spot: FreeSpot) -> tuple[str, Point]:
        if self.activity is not None and self.activity is not WANDER and free_spot(self.activity) is None:
            self.activity = None
        if self.activity is not None and self.lingered():
            if self.activity.gives_mug:
                self.mug_until = t + MUG_TICKS
            self.activity = None
        if self.activity is None:
            self.activity, self.leisure_spot = self.pick_activity(venue, t, free_spot)
            low, high = self.activity.linger_seconds
            self.linger = ticks(self.rng.uniform(low, high))
        return self.activity.name, self.leisure_spot

    def pick_activity(self, venue: Venue, t: int, free_spot: FreeSpot) -> tuple[Activity, Point]:
        open_now = [(a, free_spot(a)) for a in venue.activities() if not (a.gives_mug and self.has_mug(t))]
        options = [(a, spot) for a, spot in open_now if spot is not None]
        options.append((WANDER, None))
        activity, spot = self.rng.choices(options, [a.weight for a, _ in options])[0]
        return activity, spot if spot is not None else venue.wander_spot(self.rng)

    def head_for(self, venue: Venue, spot: Point) -> None:
        if spot != self.goal:
            self.goal = spot
            self.route = venue.route((self.x, self.y), spot)

    def walk(self) -> None:
        tx, ty = self.route[0]
        dx, dy = tx - self.x, ty - self.y
        if abs(dx) > 0.5:
            step = max(-WALK_X, min(WALK_X, dx))
            self.x += step
            self.facing = 1 if step > 0 else -1
        elif abs(dy) > 0.5:
            self.y += max(-WALK_Y, min(WALK_Y, dy))
        else:
            self.x, self.y = tx, ty
            self.route.pop(0)

    def facing_at_rest(self, t: int) -> int:
        if self.route:
            return self.facing
        if self.state == "spin":
            return 1 if (t // 2) % 2 else -1
        if self.state == "typing":
            return 1
        if self.game is not None and self.state == self.game[0].name:
            game, place = self.game
            return game.facings[place]
        return self.facing

    def lingered(self) -> bool:
        return self.arrived() and self.linger <= 0

    def arrived(self) -> bool:
        return not self.route and self.goal is not None and abs(self.goal[0] - self.x) <= 0.5 and abs(self.goal[1] - self.y) <= 0.5

    def moving(self) -> bool:
        return bool(self.route)

    def pose(self) -> str:
        if self.route:
            return "walk"
        if self.game is not None and self.state == self.game[0].name:
            return "play"
        if self.activity is not None and self.state == self.activity.name:
            return self.activity.pose
        return POSES.get(self.state, "stand")

    def napping(self, now: float, nap_after: float) -> bool:
        return self.status in RESTING_STATUSES and now - self.since >= nap_after

    def has_mug(self, t: int) -> bool:
        return t < self.mug_until

    def first_day(self, t: int) -> bool:
        return t < self.first_day_until

    def busy_with(self, name: str) -> bool:
        """Whether they are at `name` (an activity or a game) and doing it, not still walking there."""
        return self.state == name and self.arrived()

    def forget_places(self) -> None:
        """Drop every remembered coordinate, for when the scene is laid out again at a new size."""
        self.goal, self.route, self.activity, self.leisure_spot = None, [], None, None
