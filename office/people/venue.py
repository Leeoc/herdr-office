import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

Point = tuple[float, float]


NAPS = "naps"


@dataclass(frozen=True)
class Activity:
    """Something one person does while idle: where it happens, how many fit at once, how long they stay."""

    name: str
    title: str
    spots: tuple[Point, ...]
    linger_seconds: tuple[float, float]
    weight: float
    gives_mug: bool = False
    pose: str = "stand"


@dataclass(frozen=True)
class Game:
    """Something idle people play together now and then, with one spot per player."""

    name: str
    title: str
    spots: tuple[Point, ...]
    facings: tuple[int, ...]
    every_seconds: float
    length_seconds: float


class Venue(ABC):
    """The places a scene offers people. People ask for places here and never compute coordinates."""

    nap_title = "Naps"

    @abstractmethod
    def desk_count(self) -> int: ...

    @abstractmethod
    def seat(self, desk: int) -> Point: ...

    @abstractmethod
    def desk_stand(self, desk: int) -> Point: ...

    @abstractmethod
    def entrance(self) -> Point: ...

    @abstractmethod
    def nap_spot(self, index: int) -> Point: ...

    @abstractmethod
    def meeting_spot(self, index: int) -> Point: ...


    @abstractmethod
    def wander_spot(self, rng: random.Random) -> Point: ...

    @abstractmethod
    def activities(self) -> tuple[Activity, ...]: ...

    @abstractmethod
    def games(self) -> tuple[Game, ...]: ...

    @abstractmethod
    def route(self, start: Point, goal: Point) -> list[Point]: ...

    def amenities(self) -> list[tuple[str, str]]:
        """(name, title) of everything here that can be switched off."""
        return ([(a.name, a.title) for a in self.activities()] + [(g.name, g.title) for g in self.games()]
                + [(NAPS, self.nap_title)])
