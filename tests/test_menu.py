import json
import os
import tempfile
import unittest

from office.app import Office, open_tab
from office.config import Config, apply_choices, save_choices
from office.input import parse
from office.menu import Menu, MenuItem
from office.render.canvas import Canvas

ITEMS = [MenuItem("amenity:coffee", "Coffee machine", "on", switch=True), MenuItem("amenity:arcade", "Arcade", "off", switch=True),
         MenuItem("pet", "Pet", "cat"), MenuItem("night", "Night", "on")]


class MenuTest(unittest.TestCase):
    def setUp(self):
        self.menu = Menu()
        self.menu.toggle()

    def test_keys_move_and_choose(self):
        self.assertIsNone(self.menu.press("down", ITEMS))
        self.assertEqual(self.menu.press("space", ITEMS), "amenity:arcade")
        self.menu.press("down", ITEMS)
        self.assertEqual(self.menu.press("enter", ITEMS), "pet")

    def test_escape_closes(self):
        self.menu.press("esc", ITEMS)
        self.assertFalse(self.menu.open)

    def test_clicking_an_item_chooses_it(self):
        self.menu.draw(Canvas(80, 30, (0, 0, 0)), ITEMS)
        self.assertEqual(self.menu.click(self.menu.left + 3, self.menu.top_row + 3, ITEMS), "amenity:arcade")
        self.assertEqual(self.menu.cursor, 1)

    def test_clicking_outside_closes(self):
        self.menu.draw(Canvas(80, 30, (0, 0, 0)), ITEMS)
        self.assertIsNone(self.menu.click(0, 14, ITEMS))
        self.assertFalse(self.menu.open)

    def test_switches_show_ticks_and_settings_show_values(self):
        canvas = Canvas(80, 30, (0, 0, 0))
        self.menu.draw(canvas, ITEMS)
        text = {row: "".join(ch for (x, r), (ch, _) in sorted(canvas.text.items()) if r == row) for _, row in canvas.text}
        self.assertIn("[x] Coffee machine", text.values())
        self.assertIn("[ ] Arcade", text.values())
        self.assertTrue(any(line.strip().startswith("Pet") and line.endswith("cat") for line in text.values()))
        self.assertTrue(any(line.strip().startswith("Night") and line.endswith("on") for line in text.values()))


class OfficeMenuTest(unittest.TestCase):
    def test_switching_off_rebuilds_the_room_without_it(self):
        with tempfile.TemporaryDirectory() as folder:
            office = Office(Config(state_dir=folder), {}, {"hairs": [[0, 0, 0]], "skins": [[0, 0, 0]], "shirts": [[0, 0, 0]],
                                                          "confetti": [[0, 0, 0]]})
            office.fit(200, 58)
            for key in ["m", "down", "down", "down", "down", "space"]:
                office.press(key)
            office.fit(200, 58)
            self.assertEqual(office.scene.closed, frozenset({"arcade"}))
            with open(os.path.join(folder, "choices.json")) as f:
                self.assertEqual(json.load(f)["closed"], ["arcade"])


class SceneSwitchTest(unittest.TestCase):
    def test_scene_item_cycles_scenes_and_rebuilds_the_room(self):
        with tempfile.TemporaryDirectory() as folder:
            office = Office(Config(state_dir=folder), {}, {"hairs": [[0, 0, 0]], "skins": [[0, 0, 0]], "shirts": [[0, 0, 0]],
                                                          "confetti": [[0, 0, 0]]})
            office.fit(200, 58)
            office.press("m")
            office.press("enter")
            office.fit(200, 58)
            self.assertEqual((office.scene_name, type(office.scene).__name__), ("station", "StationScene"))
            self.assertIn("Sleep pods", [item.label for item in office.menu_items()])
            office.press("enter")
            office.fit(200, 58)
            self.assertEqual(office.scene_name, "office")


class SizeTest(unittest.TestCase):
    def test_tiny_pane_shows_a_notice_instead_of_the_room(self):
        with tempfile.TemporaryDirectory() as folder:
            office = Office(Config(state_dir=folder), {}, {"hairs": [[0, 0, 0]], "skins": [[0, 0, 0]], "shirts": [[0, 0, 0]],
                                                          "confetti": [[0, 0, 0]]})
            office.fit(60, 20)
            text = "".join(ch for _, (ch, _) in sorted(office.canvas().text.items(), key=lambda kv: (kv[0][1], kv[0][0])))
            self.assertIn("At least 60x24, this one is 60x20.", text)


class OpenTabTest(unittest.TestCase):
    def herdr(self, panes):
        calls = []

        def cli(*args):
            calls.append(args)
            if args[:2] == ("pane", "list"):
                return {"panes": panes}
            if args[:3] == ("plugin", "pane", "open"):
                return {"plugin_pane": {"pane": {"tab_id": "w1:t9"}}}
            return {}
        return calls, cli

    def test_existing_office_tab_is_focused_not_duplicated(self):
        calls, cli = self.herdr([{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": None},
                                 {"pane_id": "w1:p4", "tab_id": "w1:t3", "label": "office"}])
        open_tab("w1", cli)
        self.assertEqual(calls[-1], ("tab", "focus", "w1:t3"))
        self.assertFalse(any(c[:3] == ("plugin", "pane", "open") for c in calls))

    def test_new_office_tab_is_named_office(self):
        calls, cli = self.herdr([{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": None}])
        open_tab("w1", cli)
        self.assertIn("--workspace", calls[1])
        self.assertEqual(calls[-1], ("tab", "rename", "w1:t9", "office"))


class KeyboardSelectionTest(unittest.TestCase):
    def test_tab_walks_through_people_and_escape_clears(self):
        from office.sources.fake import FakeSource
        with tempfile.TemporaryDirectory() as folder:
            office = Office(Config(state_dir=folder), {}, {"hairs": [[0, 0, 0]], "skins": [[0, 0, 0]], "shirts": [[0, 0, 0]],
                                                          "confetti": [[0, 0, 0]]})
            source = FakeSource(clock=lambda: 0.0)
            office.pane_reader = source.pane_text
            source.advance()
            office.fit(200, 58)
            office.sync(source)
            office.step()
            office.press("tab")
            first = office.selected
            office.press("tab")
            self.assertNotEqual(office.selected, first)
            office.press("backtab")
            self.assertEqual(office.selected, first)
            office.press("esc")
            self.assertIsNone(office.selected)

    def test_demo_panes_read_like_claude(self):
        from office.details import pane_story
        from office.sources.fake import demo_pane
        story = pane_story(demo_pane("migrations"))
        self.assertEqual((story["asked"], story["question"]), ("tidy up the old database migrations", "Do you want to proceed?"))


class KeysTest(unittest.TestCase):
    def test_arrows_space_enter_and_escape_have_names(self):
        self.assertEqual(parse("m\x1b[A\x1b[B \r\x1b\t\x1b[Z")[1], ["m", "up", "down", "space", "enter", "esc", "tab", "backtab"])

    def test_mouse_reports_are_clicks_not_keys(self):
        self.assertEqual(parse("\x1b[<0;5;6M\x1b[<0;5;6m"), ([(4, 5)], []))


class ChoicesTest(unittest.TestCase):
    def test_menu_choices_survive_a_restart_over_the_config(self):
        with tempfile.TemporaryDirectory() as folder:
            save_choices(folder, {"closed": ["arcade"], "pet": "dog", "night": "on"})
            config = Config(pet="cat", state_dir=folder)
            apply_choices(config)
            self.assertEqual((config.closed, config.pet, config.night), (["arcade"], "dog", "on"))

    def test_no_choices_keeps_the_config(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Config(pet="duck", closed=["naps"], state_dir=os.path.join(folder, "missing"))
            apply_choices(config)
            self.assertEqual((config.pet, config.closed), ("duck", ["naps"]))


if __name__ == "__main__":
    unittest.main()


class HeaderTest(unittest.TestCase):
    def test_narrow_pane_drops_extras_but_keeps_who_needs_you(self):
        import re
        with tempfile.TemporaryDirectory() as folder:
            office = Office(Config(state_dir=folder), {}, {"hairs": [[0, 0, 0]], "skins": [[0, 0, 0]], "shirts": [[0, 0, 0]],
                                                          "confetti": [[0, 0, 0]]})
            office.fit(200, 58)
            self.assertIn("m menu", office.header())
            office.fit(60, 24)
            visible = re.sub(r"\033\[[0-9;]*m", "", office.header())
            self.assertLessEqual(len(visible) + 1, 60)
            self.assertIn("need you", visible)
            self.assertNotIn("m menu", visible)


class RoomSizeTest(unittest.TestCase):
    def office(self, folder):
        return Office(Config(state_dir=folder), {}, {"hairs": [[0, 0, 0]], "skins": [[0, 0, 0]], "shirts": [[0, 0, 0]],
                                                    "confetti": [[0, 0, 0]]})

    def test_room_has_two_spare_desks_and_builds_more_as_agents_arrive(self):
        with tempfile.TemporaryDirectory() as folder:
            office = self.office(folder)
            office.fit(185, 55)
            office.arrange(3)
            self.assertEqual(office.scene.desk_count(), 5)
            self.assertEqual(office.building, {})
            office.welcoming = True
            office.arrange(5)
            self.assertEqual(office.scene.desk_count(), 7)
            self.assertEqual(sorted(office.building), [5, 6])

    def test_spare_desks_linger_before_the_room_shrinks(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            office = self.office(folder)
            office.fit(185, 55)
            office.arrange(6)
            with mock.patch("office.app.time.time", return_value=1000.0):
                office.arrange(1)
            self.assertEqual(office.scene.desk_count(), 8)
            with mock.patch("office.app.time.time", return_value=1061.0):
                office.arrange(1)
            self.assertEqual(office.scene.desk_count(), 3)

    def test_big_screens_zoom_in_until_the_desks_no_longer_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            office = self.office(folder)
            office.fit(360, 100)
            office.arrange(3)
            self.assertEqual(office.scale, 2)
            office.arrange(40)
            self.assertEqual(office.scale, 1)
            office.fit(72, 53)
            self.assertEqual(office.scale, 1)
