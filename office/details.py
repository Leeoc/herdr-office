import json
import os
import re
import subprocess
from typing import Optional

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
SPINNER = "✻✢✳✶✽*·"
BORDER = "────"
TOOL_VERBS = {"Bash": "running", "Read": "reading", "Edit": "editing", "Update": "editing", "Write": "writing",
              "MultiEdit": "editing", "Grep": "searching", "Glob": "finding files", "Search": "searching",
              "WebFetch": "fetching", "WebSearch": "searching the web", "Agent": "delegating", "Task": "delegating"}


def short_step(text: str) -> str:
    match = re.match(r"([A-Za-z_]+)\((.*?)\)?$", text)
    if not match or match.group(1) not in TOOL_VERBS and not match.group(1)[:1].isupper():
        return text
    tool, arg = match.group(1), match.group(2)
    if tool == "Bash":
        arg = arg.split(";")[-1].split("&&")[-1].strip()
    elif "/" in arg:
        arg = arg.split(",")[0].rstrip("/").split("/")[-1]
    return ("%s %s" % (TOOL_VERBS.get(tool, tool.lower()), arg)).strip()


def split_prompt_box(lines: list[str]) -> tuple[list[str], list[str]]:
    # The prompt box can hold an unsent suggestion, which must never be read as the task.
    borders = [i for i, line in enumerate(lines) if line.lstrip().startswith(BORDER)]
    if not borders:
        return lines, []
    start = borders[-2] if len(borders) > 1 and borders[-1] - borders[-2] <= 8 else borders[-1]
    return lines[:start], lines[start:]


def pane_story(lines: list[str]) -> dict:
    """What a Claude pane says it was asked, is doing or last did, its status line, and any question for you."""
    conversation, box = split_prompt_box(lines)
    story = {}
    for line in reversed(conversation):
        text = line.strip()
        if "asked" not in story and text.startswith("❯ "):
            story["asked"] = text[2:]
        elif "step" not in story and text.startswith("⏺ ") and not text[2:].startswith("Compacted"):
            story["step"] = short_step(text[2:])
        elif "status" not in story and text[:1] in SPINNER and len(text) > 2:
            story["status"] = text[1:].strip()
        if len(story) == 3:
            break
    question = next((line.strip() for line in conversation[-25:] + box if is_question(line)), None)
    if question:
        story["question"] = question.strip("│ ").strip()
    return story


def is_question(line: str) -> bool:
    text = line.strip()
    return "Do you want" in line or "?" in line and text.startswith(("│", "Do"))


def read_pane(pane_id: str, herdr: str = "herdr") -> list[str]:
    out = ""
    # A working agent's history can't be scrolled, so fall back to what's on screen.
    for source in (["--source", "recent", "--lines", "80"], ["--source", "visible"]):
        try:
            out = subprocess.run([herdr, "agent", "read", pane_id, *source], capture_output=True, text=True, timeout=8).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        if out and not out.lstrip().startswith('{"error"'):
            break
    return [ANSI.sub("", line) for line in out.splitlines() if line.strip()]


class Board:
    """The optional board line: the card for a space on a `board` CLI board, and its next step."""

    def __init__(self, command: str, board: str, project: str):
        self.command, self.board, self.project = os.path.expanduser(command), board, os.path.expanduser(project)
        self.columns: dict = {}

    def line(self, space: str) -> Optional[str]:
        try:
            if not self.columns:
                self.columns = {c["id"]: c["name"] for c in self.run("column")}
            cards = self.run("card")
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        card = next((c for c in cards if c.get("space_ref") == space and not c.get("archived_at")), None)
        if not card:
            return None
        description = card.get("description") or ""
        next_step = description.split("Next: ", 1)[1] if "Next: " in description else description
        return "%s: %s" % (self.columns.get(card.get("column_id"), "board"), next_step)

    def run(self, kind: str) -> list:
        args = [self.command, kind, "list", "--board", self.board, "--project", self.project, "--json"]
        return json.loads(subprocess.run(args, capture_output=True, text=True, timeout=5).stdout or "[]")


def load_details(person, board: Optional[Board]) -> None:
    """Fills `person.details` from their pane; run it on a background thread so the animation never waits on herdr."""
    story = pane_story(read_pane(person.pane_id))
    story["board"] = board.line(person.space) if board and person.space else None
    person.details = story
