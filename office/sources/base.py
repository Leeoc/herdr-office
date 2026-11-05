import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AgentSnapshot:
    """One agent as the office sees it. `since` is when it entered its current status (epoch seconds)."""

    key: str
    label: str
    status: str
    pane_id: str
    space: Optional[str]
    title: str
    since: float


class AgentSource(ABC):
    """Where the office learns which agents exist and what they are doing.

    Sources run in the background; `version` goes up and `changed` is set whenever the agents
    or the office's visibility change, so the app can sleep until something happens.
    """

    def __init__(self):
        self.changed = threading.Event()
        self.version = 0
        self._agents: dict[str, AgentSnapshot] = {}
        self._visible = True
        self._lock = threading.Lock()

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def agents(self) -> dict[str, AgentSnapshot]:
        with self._lock:
            return dict(self._agents)

    def visible(self) -> bool:
        return self._visible

    def publish(self, agents: dict[str, AgentSnapshot], visible: Optional[bool] = None) -> None:
        with self._lock:
            moved = agents != self._agents or (visible is not None and visible != self._visible)
            self._agents = agents
            if visible is not None:
                self._visible = visible
            if moved:
                self.version += 1
        if moved:
            self.changed.set()


class StatusLedger:
    """Remembers when each agent entered its current status, which herdr does not report.

    With a `path`, the ledger survives restarts, so a long-idle agent is still asleep when the office reopens.
    """

    def __init__(self, clock=time.time, path: Optional[str] = None):
        self.clock, self.path = clock, path
        self.entered: dict[str, tuple[str, float]] = self.load()

    def since(self, key: str, status: str) -> float:
        known = self.entered.get(key)
        if known is None or known[0] != status:
            known = self.entered[key] = (status, self.clock())
            self.save()
        return known[1]

    def forget_all_but(self, keys) -> None:
        kept = {k: v for k, v in self.entered.items() if k in keys}
        if kept != self.entered:
            self.entered = kept
            self.save()

    def load(self) -> dict[str, tuple[str, float]]:
        try:
            with open(self.path) as f:
                return {key: (status, float(since)) for key, (status, since) in json.load(f).items()}
        except (OSError, TypeError, ValueError):
            return {}

    def save(self) -> None:
        if self.path:
            with open(self.path, "w") as f:
                json.dump(self.entered, f)


def snapshots_from(raw_agents: list[dict], space_labels: dict[str, str], ledger: StatusLedger) -> dict[str, AgentSnapshot]:
    """Office snapshots from herdr's agent list. Unnamed agents take their space's name, with `:pN` when it holds several."""
    per_space: dict[str, int] = {}
    for agent in raw_agents:
        per_space[agent.get("workspace_id")] = per_space.get(agent.get("workspace_id"), 0) + 1
    snapshots = {}
    for agent in raw_agents:
        key = agent.get("name") or agent.get("pane_id")
        space = space_labels.get(agent.get("workspace_id"))
        status = agent.get("agent_status") or "idle"
        snapshots[key] = AgentSnapshot(
            key=key,
            label=agent.get("name") or labelled_space(space, agent, per_space) or agent.get("pane_id"),
            status=status,
            pane_id=agent.get("pane_id") or key,
            space=space,
            title=(agent.get("terminal_title_stripped") or "").strip(),
            since=ledger.since(key, status),
        )
    ledger.forget_all_but(snapshots)
    return snapshots


def labelled_space(space: Optional[str], agent: dict, per_space: dict) -> Optional[str]:
    if space and per_space[agent.get("workspace_id")] > 1:
        return "%s:%s" % (space, (agent.get("pane_id") or "").split(":")[-1])
    return space
