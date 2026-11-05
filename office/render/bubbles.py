from typing import Optional

from office.render.canvas import Canvas

PAPER = (246, 244, 236)
INKS = {"name": (20, 24, 30), "ink": (34, 38, 46), "dim": (100, 104, 115), "warn": (180, 40, 40)}
STATE_INKS = {"working": (150, 105, 0), "done": (30, 120, 55), "blocked": (180, 40, 40)}
STATE_WORDS = {"working": "working", "done": "finished, come look", "blocked": "needs you", "idle": "idle"}


def since_text(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % max(0, seconds)
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    return "%dh%02dm" % (seconds // 3600, seconds % 3600 // 60)


def wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1] + "…"
    return lines


def person_lines(person, inner: int, in_state_for: float) -> list[tuple[str, str]]:
    details: Optional[dict] = person.details
    body = [(person.label, "name")]
    if details is None:
        body.append(("reading…", "dim"))
    else:
        body += story_lines(person, details, inner)
    status = details.get("status") if details else None
    words = STATE_WORDS.get(person.status, person.status)
    body.append(("%s · %s" % (words, status or since_text(in_state_for)), "state"))
    return body


def story_lines(person, details: dict, inner: int) -> list[tuple[str, str]]:
    lines = []
    if person.status == "blocked" and details.get("question"):
        lines += [(line, "warn") for line in wrap("Needs you: " + details["question"], inner, 2)]
    if details.get("asked"):
        lines += [(line, "ink") for line in wrap("Asked: " + details["asked"], inner, 2)]
    if details.get("step"):
        lead = "Doing: " if person.status == "working" else "Last: "
        lines += [(line, "ink") for line in wrap(lead + details["step"], inner, 2)]
    if details.get("board"):
        lines += [(line, "dim") for line in wrap("Board: " + details["board"], inner, 2)]
    return lines or [(line, "ink") for line in wrap(person.title or "nothing to show yet", inner, 2)]


def draw_person_bubble(canvas: Canvas, person, in_state_for: float) -> None:
    """A speech bubble above the clicked person: what they were asked, what they're doing, what's next."""
    width = max(22, min(52, canvas.w - 4))
    body = person_lines(person, width - 4, in_state_for)
    inks = dict(INKS, state=STATE_INKS.get(person.status, INKS["dim"]))
    draw_bubble(canvas, int(person.x) + 2, int(person.y), [(text, inks[ink]) for text, ink in body], width)


def draw_pet_bubble(canvas: Canvas, x: int, y: int, text: str) -> None:
    """A small speech bubble above the pet."""
    draw_bubble(canvas, x + 3, y - 8, [(text, INKS["ink"])], len(text) + 4)


def draw_bubble(canvas: Canvas, x: int, y: int, lines: list, max_width: int) -> None:
    bw = min(max_width, max(len(text) for text, _ in lines) + 4)
    rows = len(lines)
    left = max(0, min(x - bw // 2, canvas.w - bw))
    top_row = max(0, y // 2 - rows - 2)
    canvas.rect(left, top_row * 2, bw, rows * 2 + 2, PAPER)
    canvas.rect(max(left + 1, min(x, left + bw - 2)), (top_row + rows) * 2 + 2, 1, 2, PAPER)
    for i, (text, ink) in enumerate(lines):
        canvas.label(left + 2, top_row + i, text[: bw - 4], ink)
