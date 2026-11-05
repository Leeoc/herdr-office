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


class FakeSource(AgentSource):
    """Plays a script of status changes, for tests and `--demo`. The script loops after `length` seconds."""

    def __init__(self, script=DEMO_DAY, length: float = 130.0, clock=time.time):
        super().__init__()
        self.script, self.length, self.clock = sorted(script, key=lambda c: c.at), length, clock
        self.started = clock()
        self.stopping = threading.Event()

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
