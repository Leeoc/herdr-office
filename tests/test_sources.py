import json
import os
import tempfile
import unittest

from office.sources.base import StatusLedger, snapshots_from
from office.sources.fake import GONE, Cue, FakeSource
from office.sources.herdr import HerdrEventSource, office_visible, parse_event

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)["result"]


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class RecordedClient:
    """Answers list requests from recorded replies and counts them."""

    def __init__(self):
        self.requests = []

    def request(self, method, params=None):
        self.requests.append(method)
        return fixture({"agent.list": "agent_list.json", "workspace.list": "workspace_list.json"}[method])


def recorded_events():
    with open(os.path.join(FIXTURES, "events.jsonl"), "rb") as f:
        return [parse_event(line) for line in f.read().splitlines()[1:]]


class ParseEventTest(unittest.TestCase):
    def test_kinds_come_out_dotted_in_either_form(self):
        kinds = [kind for kind, _ in recorded_events()]
        self.assertEqual(kinds, ["pane.agent_status_changed", "pane.agent_status_changed", "tab.focused", "pane.agent_detected"])

    def test_data_is_passed_through(self):
        _, data = recorded_events()[0]
        self.assertEqual((data["pane_id"], data["agent_status"]), ("wQ:p2", "working"))


class EventSourceTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.client = RecordedClient()
        self.source = HerdrEventSource(self.client, "wQ", "wQ:t1", StatusLedger(self.clock), clock=self.clock)
        self.source.relist()

    def test_relist_labels_unnamed_agents_by_space_and_pane(self):
        labels = sorted(a.label for a in self.source.agents().values())
        self.assertEqual(labels, ["reviewer", "space-0:p1", "space-0:p2"])

    def test_status_event_updates_the_agent_and_restarts_its_clock(self):
        before = self.source.version
        self.clock.now += 60
        kind, data = recorded_events()[0]
        self.assertTrue(self.source.apply(kind, data))
        agent = self.source.agents()["wQ:p2"]
        self.assertEqual((agent.status, agent.since), ("working", 1060.0))
        self.assertGreater(self.source.version, before)

    def test_unchanged_status_keeps_its_clock(self):
        self.clock.now += 60
        self.source.apply(*recorded_events()[0])
        self.clock.now += 60
        self.source.apply(*recorded_events()[0])
        self.assertEqual(self.source.agents()["wQ:p2"].since, 1060.0)

    def test_focus_change_rechecks_visibility(self):
        self.client.requests.clear()
        self.source.apply(*recorded_events()[2])
        self.assertEqual(self.client.requests, ["workspace.list"])
        self.assertFalse(self.source.visible())

    def test_new_agent_asks_for_a_new_subscription(self):
        self.assertFalse(self.source.apply(*recorded_events()[3]))

    def test_subscriptions_cover_every_known_pane(self):
        panes = {s.get("pane_id") for s in self.source.subscriptions() if s["type"] == "pane.agent_status_changed"}
        self.assertEqual(panes, {"wQ:p1", "wQ:p2", "w2H:p1"})


class VisibilityTest(unittest.TestCase):
    def test_visible_only_on_own_focused_tab(self):
        spaces = [{"workspace_id": "w1", "focused": True, "active_tab_id": "w1:t2"}]
        self.assertTrue(office_visible(spaces, "w1", "w1:t2"))
        self.assertFalse(office_visible(spaces, "w1", "w1:t1"))
        self.assertTrue(office_visible(spaces, None, None))


class LedgerTest(unittest.TestCase):
    def test_since_moves_only_on_change(self):
        clock = Clock()
        ledger = StatusLedger(clock)
        self.assertEqual(ledger.since("a", "idle"), 1000.0)
        clock.now = 1500.0
        self.assertEqual(ledger.since("a", "idle"), 1000.0)
        self.assertEqual(ledger.since("a", "working"), 1500.0)

    def test_ledger_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "since.json")
            StatusLedger(Clock(1000.0), path).since("a", "idle")
            self.assertEqual(StatusLedger(Clock(9000.0), path).since("a", "idle"), 1000.0)

    def test_named_agents_keep_their_name(self):
        raw = [{"name": "reviewer", "pane_id": "w1:p1", "workspace_id": "w1", "agent_status": "idle"}]
        self.assertEqual(snapshots_from(raw, {"w1": "space"}, StatusLedger())["reviewer"].label, "reviewer")


class FakeSourceTest(unittest.TestCase):
    def test_script_plays_and_loops(self):
        clock = Clock(0.0)
        source = FakeSource([Cue(0, "a", "working"), Cue(5, "a", "done"), Cue(8, "a", GONE)], length=10, clock=clock)
        clock.now = 6
        source.advance()
        self.assertEqual(source.agents()["a"].status, "done")
        clock.now = 9
        source.advance()
        self.assertEqual(source.agents(), {})
        clock.now = 11
        source.advance()
        self.assertEqual(source.agents()["a"].status, "working")


if __name__ == "__main__":
    unittest.main()
