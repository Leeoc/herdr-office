TICK_SECONDS = 0.1


def ticks(seconds: float) -> int:
    """Simulation ticks in `seconds` of wall time."""
    return max(1, round(seconds / TICK_SECONDS))
