import json
import os
from dataclasses import dataclass

Colour = tuple[int, int, int]
NO_PET = "none"


@dataclass(frozen=True)
class Pet:
    """An office pet loaded from data: its sprite frames facing right, their timing, and what it says."""

    kind: str
    lines: tuple[str, ...]
    frames: tuple[tuple[tuple[int, int, Colour], ...], ...]
    sequence: tuple[int, ...]

    def pixels(self, t: int) -> tuple[tuple[int, int, Colour], ...]:
        """(dx, dy, colour) for tick `t`; dy 0 is the row the pet's feet stand on."""
        return self.frames[self.sequence[t % len(self.sequence)]]


def pet_from_data(kind: str, data: dict) -> Pet:
    colours = {key: tuple(value) for key, value in data["colours"].items()}
    ox, oy = data["origin"]
    frames = tuple(tuple((ox + x, oy + y, colours[ch]) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in colours)
                   for rows in data["frames"])
    sequence = tuple(index for index, hold in data["sequence"] for _ in range(hold))
    return Pet(kind, tuple(data["lines"]), frames, sequence)


def load_pets(*directories: str) -> dict[str, Pet]:
    """Every pet in `pets.json` and `pets/*.json` under each directory; later directories win."""
    pets = {}
    for directory in directories:
        for path in pet_files(directory):
            with open(path) as f:
                pets.update({kind: pet_from_data(kind, data) for kind, data in json.load(f).items()})
    return pets


def pet_files(directory: str) -> list[str]:
    files = [os.path.join(directory, "pets.json")]
    extra = os.path.join(directory, "pets")
    if os.path.isdir(extra):
        files += sorted(os.path.join(extra, name) for name in os.listdir(extra) if name.endswith(".json"))
    return [path for path in files if os.path.isfile(path)]


def next_pet(current: str, kinds: list[str]) -> str:
    cycle = kinds + [NO_PET]
    return cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else cycle[0]
