import random
import unittest

from office.scenes import scene_class, scene_names
from office.scenes.base import Scene

ROOMY = [(200, 112), (160, 76)]
CRAMPED = [(100, 56), (80, 24)]


class EveryScene(unittest.TestCase):
    def test_scenes_are_listed_office_first(self):
        self.assertEqual(scene_names()[0], "office")
        self.assertIn("station", scene_names())

    def test_every_scene_draws_at_every_size(self):
        from office.render.frames import FrameBuilder
        from office.scenes.base import FrameView
        for name in scene_names():
            for w, h in ROOMY + CRAMPED:
                scene = scene_class(name)(w, h)
                for night in (False, True):
                    FrameBuilder().build(scene, FrameView([], 5, 12, night, True, None, ((255, 0, 0),)))


class OfficeSceneTest(unittest.TestCase):
    def test_office_is_a_scene(self):
        self.assertTrue(issubclass(scene_class("office"), Scene))

    def test_every_place_can_be_reached_from_the_door(self):
        for w, h in ROOMY:
            scene = scene_class("office")(w, h)
            places = [scene.seat(d) for d in range(scene.desk_count())] + [scene.nap_spot(0), scene.meeting_spot(0)]
            places += [spot for activity in scene.activities() for spot in activity.spots]
            places += [spot for game in scene.games() for spot in game.spots]
            for place in places:
                route = scene.route(scene.entrance(), place)
                self.assertEqual(route[-1], place, (w, h))
                self.assertLess(abs(route[-2][0] - place[0]) + abs(route[-2][1] - place[1]), 12, (w, h, place))

    def test_cramped_rooms_still_route_everywhere(self):
        for w, h in CRAMPED:
            scene = scene_class("office")(w, h)
            for desk in range(scene.desk_count()):
                self.assertEqual(scene.route(scene.entrance(), scene.seat(desk))[-1], scene.seat(desk))

    def test_everything_switchable_is_listed(self):
        names = [name for name, _ in scene_class("office")(200, 112).amenities()]
        self.assertEqual(names, ["coffee", "arcade", "cooler", "lunch", "books", "plant", "pingpong", "foosball", "naps"])

    def test_switched_off_furniture_leaves_the_room(self):
        office = scene_class("office")
        full, emptied = office(200, 112), office(200, 112, frozenset({"pingpong", "foosball"}))
        self.assertEqual(len(full.obstacles()) - len(emptied.obstacles()), 2)
        tx, ty = full.table
        self.assertTrue(emptied.grid.is_open(emptied.grid.cell_of((tx + 8.0, ty - 4.0))))
        self.assertFalse(full.grid.is_open(full.grid.cell_of((tx + 8.0, ty - 4.0))))

    def test_wander_spots_are_on_open_floor(self):
        scene = scene_class("office")(200, 112)
        rng = random.Random(1)
        for _ in range(20):
            spot = scene.wander_spot(rng)
            self.assertTrue(scene.grid.is_open(scene.grid.cell_of(spot)), spot)


if __name__ == "__main__":
    unittest.main()
