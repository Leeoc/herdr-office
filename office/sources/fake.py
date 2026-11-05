import threading
import time
from dataclasses import dataclass

from office.sources.base import AgentSnapshot, AgentSource

GONE = "gone"


@dataclass(frozen=True)
class Cue:
    """At `at` seconds into the script, agent `key` becomes `status` (or GONE), having been so for `ago` seconds."""

    at: float
    key: str
    status: str
    ago: float = 0.0


DEMO_DAY = (
    Cue(0, "app-142:p1", "working"),
    Cue(0, "app-142:p2", "working"),
    Cue(0, "app-150", "working"),
    Cue(0, "migrations", "blocked"),
    Cue(0, "reviewer", "idle", ago=3600),
    Cue(0, "docs", "idle"),
    Cue(0, "scout", "idle"),
    Cue(0, "app-139", "done"),
    Cue(0, "qa", "idle"),
    Cue(0, "infra", "idle"),
    Cue(0, "design", "idle"),
    Cue(0, "release", "idle"),
    Cue(12, "app-150", "done"),
    Cue(20, "app-161", "working"),
    Cue(35, "migrations", "working"),
    Cue(50, "app-139", GONE),
    Cue(70, "docs", "working"),
    Cue(90, "app-150", "idle"),
    Cue(110, "migrations", "blocked"),
)


DEMO_PANES = {
    "app-142:p1": ("add a retry to the upload client and run the tests", "Bash(uv run pytest -q tests/upload)",
                   "Percolating… (47s · esc to interrupt)"),
    "app-142:p2": ("write the upload client's docs", "Edit(docs/upload.md)", "Composing… (12s · esc to interrupt)"),
    "app-150": ("make the settings page load faster", "Read(src/settings/page.tsx)", "Pondering… (1m 3s · esc to interrupt)"),
    "migrations": ("tidy up the old database migrations", "Bash(rm -rf migrations/old)", None),
    "app-139": ("fix the flaky login test", "Bash(npm test -- login)", "Done in 4m 10s"),
    "app-161": ("add a dark mode toggle", "Read(src/theme.ts)", "Thinking… (5s · esc to interrupt)"),
}


def demo_pane(key: str) -> list[str]:
    """A made-up Claude pane for a demo agent, shaped like the real thing so the bubble reads it the same way."""
    asked, step, status = DEMO_PANES.get(key, ("look around the codebase", "Glob(**/*.md)", None))
    lines = ["❯ " + asked, "⏺ " + step]
    if status:
        lines.append("✻ " + status)
    if key == "migrations":
        lines += ["╭────────────────────────────╮", "│ Do you want to proceed?    │", "╰────────────────────────────╯"]
    return lines


class FakeSource(AgentSource):
    """Plays a script of status changes, for tests and `--demo`. The script loops after `length` seconds."""

    def __init__(self, script=DEMO_DAY, length: float = 130.0, clock=time.time):
        super().__init__()
        self.script, self.length, self.clock = sorted(script, key=lambda c: c.at), length, clock
        self.started = clock()
        self.stopping = threading.Event()

    @staticmethod
    def pane_text(pane_id: str) -> list[str]:
        return demo_pane(pane_id.removeprefix("demo:"))

    def start(self) -> None:
        self.advance()
        threading.Thread(target=self.run, name="fake-day", daemon=True).start()

    def close(self) -> None:
        self.stopping.set()

    def run(self) -> None:
        while not self.stopping.wait(0.25):
            self.advance()

    def advance(self) -> None:
        now = self.clock()
        elapsed = (now - self.started) % self.length
        loop_start = now - elapsed
        self.publish(self.agents_at(elapsed, loop_start))

    def agents_at(self, elapsed: float, loop_start: float) -> dict[str, AgentSnapshot]:
        agents: dict[str, AgentSnapshot] = {}
        for cue in self.script:
            if cue.at > elapsed:
                break
            if cue.status == GONE:
                agents.pop(cue.key, None)
            else:
                agents[cue.key] = self.snapshot(cue, loop_start)
        return agents

    @staticmethod
    def snapshot(cue: Cue, loop_start: float) -> AgentSnapshot:
        return AgentSnapshot(cue.key, cue.key, cue.status, "demo:" + cue.key, cue.key.split(":")[0],
                             "demo agent", loop_start + cue.at - cue.ago)
