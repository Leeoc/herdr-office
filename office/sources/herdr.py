import json
import os
import socket
import subprocess
import threading
import time
from typing import Iterator, Optional

from office.sources.base import AgentSource, StatusLedger, snapshots_from

DEFAULT_SOCKET = os.path.expanduser("~/.config/herdr/herdr.sock")
PANE_LIFECYCLE = ("pane.created", "pane.closed", "pane.exited", "pane.agent_detected")
SPACE_CHANGES = ("workspace.created", "workspace.closed", "workspace.renamed", "workspace.updated")
FOCUS_CHANGES = ("workspace.focused", "tab.focused")


class HerdrError(Exception):
    pass


class HerdrClient:
    """herdr's socket API: one request per connection, newline-delimited JSON."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("HERDR_SOCKET_PATH") or DEFAULT_SOCKET

    def request(self, method: str, params: Optional[dict] = None, timeout: float = 5.0) -> dict:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(timeout)
            sock.connect(self.path)
            sock.sendall(encode_request(method, params))
            return result_of(read_line(sock))

    def subscribe(self, subscriptions: list[dict], idle_timeout: float = 1.0) -> "Subscription":
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(5.0)
        sock.connect(self.path)
        sock.sendall(encode_request("events.subscribe", {"subscriptions": subscriptions}))
        subscription = Subscription(sock)
        result_of(subscription.first_line())
        sock.settimeout(idle_timeout)
        return subscription


class Subscription:
    """A live event stream. `events()` yields None whenever the stream is quiet for a while."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buffer = b""

    def first_line(self) -> bytes:
        while b"\n" not in self.buffer:
            self.fill()
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line

    def fill(self) -> None:
        data = self.sock.recv(65536)
        if not data:
            raise HerdrError("herdr closed the event stream")
        self.buffer += data

    def events(self) -> Iterator[Optional[tuple[str, dict]]]:
        while True:
            try:
                self.fill()
            except socket.timeout:
                yield None
                continue
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if line.strip():
                    yield parse_event(line)

    def close(self) -> None:
        self.sock.close()


def encode_request(method: str, params: Optional[dict]) -> bytes:
    return (json.dumps({"id": method, "method": method, "params": params or {}}) + "\n").encode()


def read_line(sock: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
    return data


def result_of(line: bytes) -> dict:
    reply = json.loads(line or b"{}")
    if "error" in reply:
        raise HerdrError(reply["error"].get("message", "herdr error"))
    return reply.get("result", {})


def parse_event(line: bytes) -> tuple[str, dict]:
    """(kind, data) from one event line, with the kind in dotted form whichever form herdr sends."""
    envelope = json.loads(line)
    data = envelope.get("data") or {}
    kind = envelope.get("event") or data.get("type") or ""
    return (kind if "." in kind else kind.replace("_", ".", 1)), data


def office_visible(workspaces: list[dict], workspace_id: Optional[str], tab_id: Optional[str]) -> bool:
    """Whether the office's own tab is the one on screen; always true outside herdr."""
    if not (workspace_id and tab_id):
        return True
    mine = next((w for w in workspaces if w.get("workspace_id") == workspace_id), None)
    return bool(mine and mine.get("focused") and mine.get("active_tab_id") == tab_id)


class HerdrEventSource(AgentSource):
    """Follows herdr's event stream, re-listing every agent now and then in case an event was missed."""

    RELIST_EVERY = 30.0

    def __init__(self, client: HerdrClient, workspace_id: Optional[str], tab_id: Optional[str],
                 ledger: StatusLedger, clock=time.time):
        super().__init__()
        self.client, self.workspace_id, self.tab_id, self.clock = client, workspace_id, tab_id, clock
        self.ledger = ledger
        self.raw: dict[str, dict] = {}
        self.space_labels: dict[str, str] = {}
        self.stopping = threading.Event()
        self.subscription: Optional[Subscription] = None

    def start(self) -> None:
        self.relist()
        threading.Thread(target=self.run, name="herdr-events", daemon=True).start()

    def close(self) -> None:
        self.stopping.set()
        if self.subscription:
            self.subscription.close()

    def run(self) -> None:
        backoff = 1.0
        while not self.stopping.is_set():
            try:
                self.relist()
                self.listen()
                backoff = 1.0
            except (OSError, HerdrError, ValueError):
                self.stopping.wait(backoff)
                backoff = min(backoff * 2, 30.0)

    def listen(self) -> None:
        self.subscription = self.client.subscribe(self.subscriptions())
        relisted = self.clock()
        try:
            for event in self.subscription.events():
                if self.stopping.is_set():
                    return
                if event is not None and not self.apply(*event):
                    return
                if self.clock() - relisted > self.RELIST_EVERY:
                    panes = set(self.raw)
                    self.relist()
                    relisted = self.clock()
                    if set(self.raw) != panes:
                        return
        finally:
            self.subscription.close()

    def subscriptions(self) -> list[dict]:
        kinds = [{"type": kind} for kind in PANE_LIFECYCLE + SPACE_CHANGES + FOCUS_CHANGES]
        return kinds + [{"type": "pane.agent_status_changed", "pane_id": pane} for pane in sorted(self.raw)]

    def apply(self, kind: str, data: dict) -> bool:
        """Take in one event; False means the pane set changed and the subscription must be renewed."""
        if kind == "pane.agent_status_changed" and data.get("pane_id") in self.raw:
            self.raw[data["pane_id"]] = dict(self.raw[data["pane_id"]], agent_status=data.get("agent_status") or "idle")
            self.publish_raw()
            return True
        if kind in FOCUS_CHANGES:
            self.publish_raw(self.fetch_visibility())
            return True
        if kind in SPACE_CHANGES:
            self.relist()
            return True
        return kind not in PANE_LIFECYCLE and kind != "pane.agent_status_changed"

    def relist(self) -> None:
        agents = self.client.request("agent.list").get("agents", [])
        workspaces = self.client.request("workspace.list").get("workspaces", [])
        self.raw = {a["pane_id"]: a for a in agents if a.get("pane_id")}
        self.space_labels = {w["workspace_id"]: w.get("label") for w in workspaces}
        self.publish_raw(office_visible(workspaces, self.workspace_id, self.tab_id))

    def fetch_visibility(self) -> bool:
        workspaces = self.client.request("workspace.list").get("workspaces", [])
        return office_visible(workspaces, self.workspace_id, self.tab_id)

    def publish_raw(self, visible: Optional[bool] = None) -> None:
        self.publish(snapshots_from(list(self.raw.values()), self.space_labels, self.ledger), visible)


class PollingSource(AgentSource):
    """Asks the herdr CLI for every agent every couple of seconds; the fallback when the socket can't be used."""

    def __init__(self, workspace_id: Optional[str], tab_id: Optional[str], ledger: StatusLedger,
                 every: float = 2.0, herdr: str = "herdr"):
        super().__init__()
        self.workspace_id, self.tab_id, self.every, self.herdr = workspace_id, tab_id, every, herdr
        self.ledger = ledger
        self.stopping = threading.Event()

    def start(self) -> None:
        self.poll()
        threading.Thread(target=self.run, name="herdr-poll", daemon=True).start()

    def close(self) -> None:
        self.stopping.set()

    def run(self) -> None:
        while not self.stopping.wait(self.every):
            self.poll()

    def poll(self) -> None:
        workspaces = self.cli("workspace", "list").get("workspaces", [])
        agents = self.cli("agent", "list").get("agents", [])
        labels = {w["workspace_id"]: w.get("label") for w in workspaces}
        self.publish(snapshots_from(agents, labels, self.ledger), office_visible(workspaces, self.workspace_id, self.tab_id))

    def cli(self, *args: str) -> dict:
        try:
            out = subprocess.run([self.herdr, *args], capture_output=True, text=True, timeout=5).stdout
            return json.loads(out or "{}").get("result", {})
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}
