Colour = tuple[int, int, int]
Point = tuple[float, float]


class LightMap:
    """Evening light: the room dimmed, with a soft warm pool round each lamp."""

    def __init__(self, w: int, h: int, lamps: list[Point], radius: int = 13):
        self.levels = [[0.0] * w for _ in range(h)]
        for lx, ly in lamps:
            self.add_pool(int(lx), int(ly), radius, w, h)
        self.cache: dict[tuple[Colour, float], Colour] = {}

    def add_pool(self, lx: int, ly: int, radius: int, w: int, h: int) -> None:
        for y in range(max(0, ly - radius), min(h, ly + radius)):
            row = self.levels[y]
            for x in range(max(0, lx - radius * 2), min(w, lx + radius * 2)):
                distance = (((x - lx) / 2.0) ** 2 + (y - ly) ** 2) ** 0.5
                row[x] = max(row[x], round(max(0.0, 1.0 - distance / radius), 2))

    def apply(self, colour: Colour, x: int, y: int) -> Colour:
        level = self.levels[y][x]
        key = (colour, level)
        lit = self.cache.get(key)
        if lit is None:
            lit = self.cache[key] = lamp_lit(colour, level)
        return lit


def lamp_lit(colour: Colour, level: float) -> Colour:
    r, g, b = colour
    return (min(255, int(r * (0.4 + 0.65 * level) + 14 * level)),
            min(255, int(g * (0.4 + 0.6 * level) + 6 * level)),
            int(b * (0.48 + 0.4 * level)))
