import random
import unittest

from office.people.crowd import MEETING_EVERY, Crowd
from office.people.person import SPIN_TICKS
from office.people.timing import ticks
from office.people.venue import Activity, Game, Venue
from office.sources.base import AgentSnapshot

PALETTE = {"hairs": [[1, 1, 1]], "skins": [[2, 2, 2]], "shirts": [[3, 3, 3]]}
NOW = 100_000.0


class OpenRoom(Venue):
    def __init__(self, desks=4):
        self.desks = desks
        self.places = (Activity("arcade", "Arcade", ((90.0, 10.0),), (5, 5), 1000.0),
                       Activity("cooler", "Cooler", ((80.0, 10.0), (80.0, 20.0)), (5, 5), 1000.0))
        self.game_list = (Game("pingpong", "Ping-pong", ((60.0, 30.0), (70.0, 30.0)), (1, -1), 100, 50),
                          Game("foosball", "Foosball", ((60.0, 50.0), (60.0, 56.0), (70.0, 50.0), (70.0, 56.0)),
                               (1, 1, -1, -1), 100, 50))

    def desk_count(self): return self.desks
    def seat(self, desk): return float(desk * 10), 40.0
    def desk_stand(self, desk): return float(desk * 10), 38.0
    def entrance(self): return 0.0, 0.0
    def nap_spot(self, index): return 50.0 + index, 60.0
    def meeting_spot(self, index): return 30.0 + index, 5.0
    def wander_spot(self, rng: random.Random): return 75.0, 25.0
    def activities(self): return self.places
    def games(self): return self.game_list
    def route(self, start, goal): return [goal]


def agent(key, status, since=NOW, label=None):
    return AgentSnapshot(key, label or key, status, "w:" + key, None, "", since)


def run(crowd, venue, ticks, start=1):
    for t in range(start, start + ticks):
        crowd.tick(venue, t, NOW)
    return start + ticks


class PersonBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.venue = OpenRoom()
        self.crowd = Crowd(PALETTE, r"(?i)\b([a-z]{2,}-\d+)", nap_after=1800)

    def person(self, key):
        return self.crowd.people[key]

    def test_working_agent_walks_to_their_desk_and_types(self):
        self.crowd.sync([agent("a", "working")], self.venue, 1, newcomers=False)
        run(self.crowd, self.venue, 200)
        a = self.person("a")
        self.assertEqual((a.state, a.pose()), ("typing", "sit"))
        self.assertEqual((a.x, a.y), self.venue.seat(a.desk))

    def test_finishing_spins_the_chair_then_cheers(self):
        self.crowd.sync([agent("a", "working")], self.venue, 1, newcomers=False)
        t = run(self.crowd, self.venue, 200)
        self.crowd.sync([agent("a", "done")], self.venue, t, newcomers=True)
        t = run(self.crowd, self.venue, 2, start=t)
        self.assertEqual(self.person("a").state, "spin")
        run(self.crowd, self.venue, SPIN_TICKS + 40, start=t)
        self.assertEqual((self.person("a").state, self.person("a").pose()), ("cheer", "cheer"))

    def test_blocked_agent_stands_at_their_desk_with_a_hand_up(self):
        self.crowd.sync([agent("a", "blocked")], self.venue, 1, newcomers=False)
        run(self.crowd, self.venue, 200)
        self.assertEqual(self.person("a").pose(), "hand")
        self.assertTrue(self.crowd.alarm())

    def test_long_idle_agent_naps(self):
        self.crowd.sync([agent("a", "idle", since=NOW - 3600)], self.venue, 1, newcomers=False)
        run(self.crowd, self.venue, 300)
        self.assertEqual(self.person("a").pose(), "lie")

    def test_recently_idle_agent_takes_up_a_pastime(self):
        self.crowd.sync([agent("a", "idle")], self.venue, 1, newcomers=False)
        run(self.crowd, self.venue, 5)
        self.assertIn(self.person("a").state, {"arcade", "cooler", "wander", "coffee"})

    def test_departed_agent_walks_out_and_is_removed(self):
        self.crowd.sync([agent("a", "working")], self.venue, 1, newcomers=False)
        t = run(self.crowd, self.venue, 200)
        self.crowd.sync([], self.venue, t, newcomers=True)
        t = run(self.crowd, self.venue, 1, start=t)
        self.assertEqual(self.person("a").state, "leave")
        run(self.crowd, self.venue, 300, start=t)
        self.assertNotIn("a", self.crowd.people)

    def test_newcomers_after_the_first_sync_get_a_first_day(self):
        self.crowd.sync([agent("old", "idle")], self.venue, 1, newcomers=False)
        self.crowd.sync([agent("old", "idle"), agent("new", "working")], self.venue, 2, newcomers=True)
        self.assertFalse(self.person("old").first_day(3))
        self.assertTrue(self.person("new").first_day(3))

    def test_same_ticket_agents_meet_at_the_whiteboard(self):
        agents = [agent("x", "working", label="app-12:p1"), agent("y", "working", label="app-12:p2"),
                  agent("z", "working", label="app-99")]
        self.crowd.sync(agents, self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, MEETING_EVERY * 3, NOW)
        self.assertEqual((self.person("x").meeting, self.person("y").meeting, self.person("z").meeting), (0, 1, None))


class CapacityTest(unittest.TestCase):
    def setUp(self):
        self.venue = OpenRoom()
        self.crowd = Crowd(PALETTE, r"(?!)", nap_after=1800)

    def test_arcade_takes_one_player_and_cooler_two(self):
        keys = ["p%d" % i for i in range(6)]
        self.crowd.sync([agent(k, "idle") for k in keys], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, ticks(100) - 1, NOW)
        states = [p.state for p in self.crowd.people.values()]
        self.assertEqual(states.count("arcade"), 1)
        self.assertEqual(states.count("cooler"), 2)

    def players(self, game_name):
        return {k for k, p in self.crowd.people.items() if p.game is not None and p.game[0].name == game_name}

    def test_pingpong_takes_a_pair_and_rotates_it(self):
        self.crowd.closed = {"foosball"}
        self.crowd.sync([agent(k, "idle") for k in "abc"], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, 0, NOW)
        first = self.players("pingpong")
        self.assertEqual(sorted(p.game[1] for p in self.crowd.people.values() if p.game), [0, 1])
        self.crowd.tick(self.venue, ticks(100), NOW)
        second = self.players("pingpong")
        self.assertEqual(len(second), 2)
        self.assertNotEqual(first, second)

    def test_foosball_needs_four_and_does_not_poach_pingpong_players(self):
        self.crowd.sync([agent(k, "idle") for k in "abcdef"], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, 0, NOW)
        self.assertEqual((len(self.players("pingpong")), len(self.players("foosball"))), (2, 4))
        self.assertFalse(self.players("pingpong") & self.players("foosball"))

    def test_too_few_for_foosball(self):
        self.crowd.sync([agent(k, "idle") for k in "abc"], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, 0, NOW)
        self.assertEqual(self.players("foosball"), set())

    def test_players_face_the_table_and_play(self):
        self.crowd.closed = {"foosball"}
        self.crowd.sync([agent(k, "idle") for k in "ab"], self.venue, 1, newcomers=False)
        run(self.crowd, self.venue, 150, start=0)
        poses = {p.pose() for p in self.crowd.people.values()}
        facings = sorted(p.facing for p in self.crowd.people.values())
        self.assertEqual((poses, facings), ({"play"}, [-1, 1]))

    def test_closed_games_are_not_played(self):
        self.crowd.closed = {"pingpong", "foosball"}
        self.crowd.sync([agent(k, "idle") for k in "abcdef"], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, 0, NOW)
        self.assertTrue(all(p.game is None for p in self.crowd.people.values()))

    def test_nappers_and_a_lone_idler_do_not_play(self):
        self.crowd.sync([agent("a", "idle"), agent("b", "idle", since=NOW - 7200)], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, 0, NOW)
        self.assertTrue(all(p.game is None for p in self.crowd.people.values()))

    def test_closed_activity_is_never_picked_and_its_user_moves_on(self):
        keys = ["p%d" % i for i in range(6)]
        self.crowd.sync([agent(k, "idle") for k in keys], self.venue, 1, newcomers=False)
        self.crowd.tick(self.venue, ticks(100) - 1, NOW)
        self.crowd.closed = {"arcade"}
        self.crowd.tick(self.venue, ticks(100), NOW)
        self.assertNotIn("arcade", {p.state for p in self.crowd.people.values()})

    def test_closed_couch_keeps_everyone_awake(self):
        self.crowd.closed = {"naps"}
        self.crowd.sync([agent("a", "idle", since=NOW - 7200)], self.venue, 1, newcomers=False)
        run(self.crowd, self.venue, 50, start=ticks(100) - 60)
        self.assertNotEqual(self.crowd.people["a"].state, "nap")

    def test_desks_go_to_the_blocked_first_when_short(self):
        venue = OpenRoom(desks=1)
        self.crowd.sync([agent("a", "working"), agent("b", "blocked")], venue, 1, newcomers=False)
        self.crowd.tick(venue, 1, NOW)
        self.assertEqual((self.crowd.people["b"].desk, self.crowd.people["a"].desk), (0, None))


if __name__ == "__main__":
    unittest.main()
