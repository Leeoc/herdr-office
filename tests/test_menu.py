import json
import os
import tempfile
import unittest

from office.app import Office
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


class KeysTest(unittest.TestCase):
    def test_arrows_space_enter_and_escape_have_names(self):
        self.assertEqual(parse("m\x1b[A\x1b[B \r\x1b")[1], ["m", "up", "down", "space", "enter", "esc"])

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
