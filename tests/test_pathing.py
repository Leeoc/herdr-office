import unittest

from office.pathing import Rect, WalkGrid, corners

FOOTPRINT = Rect(0, 0, 2, 2)


def walked_through(route, start):
    points, (x, y) = [], start
    for tx, ty in route:
        while x != tx:
            x += 1 if tx > x else -1
            points.append((x, y))
        while y != ty:
            y += 1 if ty > y else -1
            points.append((x, y))
    return points


class WalkGridTest(unittest.TestCase):
    def setUp(self):
        self.wall = Rect(20, 0, 4, 30)
        self.grid = WalkGrid(Rect(0, 0, 60, 40), [self.wall], FOOTPRINT)

    def test_route_goes_round_the_obstacle(self):
        route = self.grid.route((4.0, 10.0), (40.0, 10.0))
        self.assertEqual(route[-1], (40.0, 10.0))
        for x, y in walked_through(route, (4.0, 10.0)):
            self.assertFalse(FOOTPRINT.moved(x, y).overlaps(self.wall), (x, y))
        self.assertTrue(any(y >= 30 for _, y in route))

    def test_route_bends_rarely(self):
        route = self.grid.route((4.0, 10.0), (40.0, 10.0))
        self.assertLessEqual(len(route), 6)

    def test_open_floor_is_a_straight_walk(self):
        self.assertEqual(self.grid.route((0.0, 36.0), (50.0, 36.0)), [(0.0, 36.0), (50.0, 36.0), (50.0, 36.0)])

    def test_goal_inside_furniture_ends_beside_it(self):
        route = self.grid.route((4.0, 10.0), (21.0, 10.0))
        before_last = route[-2]
        self.assertFalse(FOOTPRINT.moved(*before_last).overlaps(self.wall))

    def test_corners_keep_ends_and_turns(self):
        cells = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        self.assertEqual(corners(cells), [(0, 0), (2, 0), (2, 2)])


if __name__ == "__main__":
    unittest.main()
