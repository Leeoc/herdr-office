import argparse
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from typing import Optional

from office import control
from office.config import DATA_DIR, PLUGIN_ID, Config, apply_choices, colour_mode, load_config, load_palette, save_choices
from office.details import Board, load_details, read_pane
from office.input import DoubleClick, Terminal, parse, read_raw
from office.menu import Menu, MenuItem
from office.people.crowd import Crowd
from office.people.person import Person
from office.people.timing import TICK_SECONDS
from office.pets import NO_PET, Pet, load_pets, next_pet
from office.render.bubbles import draw_person_bubble, draw_pet_bubble
from office.render.canvas import Canvas, encode
from office.render.frames import FrameBuilder
from office.render.png import canvas_png
from office.render.screen import Screen
from office.scenes import scene_class, scene_names
from office.scenes.base import DESK_BUILD_TICKS, FrameView, Scene
from office.sources.base import AgentSource, StatusLedger
from office.sources.fake import FakeSource
from office.sources.herdr import HerdrClient, HerdrError, HerdrEventSource, PollingSource, herdr_cli

SELECTION_SECONDS = 20
PET_LINE_SECONDS = 3
FLASH_SECONDS = 5
MAX_CATCH_UP = 30
LIVELY_POSES = ("walk", "cheer", "play")
MIN_COLS, MIN_ROWS = 60, 24
SPARE_DESKS = 2
SHRINK_AFTER_SECONDS = 60
ZOOMS = (3, 2)
ZOOMED_ROOM_MIN = (110, 64)
NOTICE_INK = (230, 230, 235)


class Office:
    """The running office: the crowd, the scene they are in, and what the viewer has clicked."""

    def __init__(self, config: Config, pets: dict[str, Pet], palette: dict):
        self.config, self.pets = config, pets
        self.crowd = Crowd(palette, config.ticket_pattern, config.nap_after_minutes * 60, config.closed)
        self.scene_name = config.scene if config.scene in scene_names() else "office"
        self.scene: Optional[Scene] = None
        self.scale = 1
        self.size = (MIN_COLS, MIN_ROWS)
        self.building: dict[int, int] = {}
        self.surplus_since: Optional[float] = None
        self.frames = FrameBuilder()
        self.confetti = tuple(tuple(c) for c in palette["confetti"])
        self.pet_kind = config.pet if config.pet in pets or config.pet == NO_PET else next(iter(pets), NO_PET)
        self.night_mode = config.night
        self.menu = Menu()
        self.board = Board(**config.board) if config.board else None
        self.pane_reader = read_pane
        self.chatter = random.Random()
        self.clicks = DoubleClick()
        self.t = 0
        self.seen_version = -1
        self.welcoming = False
        self.selected: Optional[str] = None
        self.selected_at = 0.0
        self.pet_line: Optional[str] = None
        self.pet_line_at = 0.0
        self.flash: Optional[str] = None
        self.flash_at = 0.0

    def fit(self, cols: int, rows: int) -> None:
        self.size = (cols, rows)
        self.arrange(len(self.crowd.people))

    def arrange(self, agents: int) -> None:
        """Lay the room out for this many agents: as zoomed in as their desks allow, with a couple of spare desks."""
        cols, rows = self.size
        w, h = cols, max(24, (rows - 2) * 2)
        kind = scene_class(self.scene_name)
        desks = self.desks_needed(agents)
        self.scale = zoom_for(kind, w, h, desks)
        w, h = -(-w // self.scale), -(-h // self.scale)
        desks = min(desks, kind.desk_capacity(w, h))
        closed = frozenset(self.crowd.closed)
        old = self.scene
        same_floor = old is not None and (type(old), old.w, old.h, old.closed) == (kind, w, h, closed)
        if same_floor and old.desk_count() == desks:
            return
        self.scene = kind(w, h, closed, desks)
        if not same_floor:
            self.building.clear()
            self.crowd.relocate()
        elif self.welcoming:
            self.building.update({index: self.t for index in range(old.desk_count(), desks)})

    def desks_needed(self, agents: int) -> int:
        wanted = agents + SPARE_DESKS
        current = self.scene.desk_count() if self.scene else 0
        if wanted >= current:
            self.surplus_since = None
            return wanted
        self.surplus_since = self.surplus_since or time.time()
        return wanted if time.time() - self.surplus_since > SHRINK_AFTER_SECONDS else current

    def sync(self, source: AgentSource) -> None:
        if source.version == self.seen_version:
            return
        self.seen_version = source.version
        agents = source.agents().values()
        self.arrange(len(agents))
        self.crowd.sync(agents, self.scene, self.t, newcomers=self.welcoming)
        self.welcoming = True

    def step(self) -> None:
        self.crowd.tick(self.scene, self.t, time.time())
        self.t += 1
        self.building = {index: born for index, born in self.building.items() if self.t - born < DESK_BUILD_TICKS}
        self.expire(time.time())
        if self.pet is not None and not self.pet_line and self.t % 330 == 0 and self.chatter.random() < 0.5:
            self.say_pet_line()

    def expire(self, now: float) -> None:
        if self.selected and (self.selected not in self.crowd.people or now - self.selected_at > SELECTION_SECONDS):
            self.selected = None
        if self.pet_line and now - self.pet_line_at > PET_LINE_SECONDS:
            self.pet_line = None
        if self.flash and now - self.flash_at > FLASH_SECONDS:
            self.flash = None

    @property
    def pet(self) -> Optional[Pet]:
        return self.pets.get(self.pet_kind)

    def hour(self) -> int:
        return int(os.environ.get("OFFICE_HOUR", time.localtime().tm_hour))

    def night(self) -> bool:
        if self.night_mode in ("on", "off"):
            return self.night_mode == "on"
        return self.hour() >= 18 or self.hour() < 7

    def lively(self) -> bool:
        return self.selected is not None or any(p.pose() in LIVELY_POSES for p in self.crowd.people.values())

    def view(self) -> FrameView:
        people = list(self.crowd.people.values())
        building = {index: self.t - born for index, born in self.building.items()}
        return FrameView(people, self.t, self.hour(), self.night(), self.crowd.alarm(), self.pet, self.confetti, building)

    def too_small(self) -> bool:
        return self.size[0] < MIN_COLS or self.size[1] < MIN_ROWS

    def size_notice(self) -> Canvas:
        cols, rows = self.size
        canvas = Canvas(cols, max(2, (rows - 1) * 2), self.scene.fill)
        lines = ["The office needs a bigger pane.", "At least %dx%d, this one is %dx%d." % (MIN_COLS, MIN_ROWS, cols, rows)]
        for i, line in enumerate(lines):
            canvas.label(max(0, (cols - len(line)) // 2), max(0, (rows - 1) // 2 - 1 + i), line[:cols], NOTICE_INK)
        return canvas

    def canvas(self) -> Canvas:
        if self.too_small():
            return self.size_notice()
        cols, rows = self.size
        canvas = self.frames.build(self.scene, self.view(), self.scale, (cols, max(24, (rows - 2) * 2)))
        person = self.crowd.people.get(self.selected) if self.selected else None
        if person is not None:
            draw_person_bubble(canvas, person, time.time() - person.since, self.scale)
        if self.pet_line and self.pet is not None:
            x, y, _ = self.scene.pet_spot(self.t)
            draw_pet_bubble(canvas, x * self.scale, y * self.scale, self.pet_line)
        if self.menu.open:
            self.menu.draw(canvas, self.menu_items())
        return canvas

    def menu_items(self) -> list[MenuItem]:
        amenities = [MenuItem(AMENITY + name, title, "off" if name in self.crowd.closed else "on", switch=True)
                     for name, title in self.scene.amenities()]
        settings = [MenuItem("scene", "Scene", self.scene_name), MenuItem("pet", "Pet", self.pet_kind),
                    MenuItem("night", "Night", self.night_mode)]
        return settings + amenities

    def choose(self, key: str) -> None:
        if key.startswith(AMENITY):
            self.crowd.closed ^= {key[len(AMENITY):]}
        elif key == "scene":
            self.scene_name = next_in(scene_names(), self.scene_name)
        elif key == "pet":
            self.pet_kind, self.pet_line = next_pet(self.pet_kind, list(self.pets)), None
        elif key == "night":
            self.night_mode = next_in(NIGHT_MODES, self.night_mode)
        self.remember()

    def remember(self) -> None:
        save_choices(self.config.state_dir, {"closed": sorted(self.crowd.closed), "pet": self.pet_kind,
                                             "night": self.night_mode, "scene": self.scene_name})

    def press(self, key: str) -> None:
        if self.menu.open:
            choice = self.menu.press(key, self.menu_items())
            if choice:
                self.choose(choice)
        elif key == "m":
            self.menu.toggle()
        elif key in ("tab", "backtab"):
            self.select_next(1 if key == "tab" else -1)
        elif key == "enter" and self.selected in self.crowd.people:
            jump_to(self.crowd.people[self.selected])
        elif key == "esc":
            self.selected = None
        elif key in KEYS:
            self.command(KEYS[key])

    def select_next(self, step: int) -> None:
        """Move the selection through everyone, desk by desk, so the office works without a mouse."""
        order = sorted(self.crowd.people.values(), key=lambda p: (p.desk is None, p.desk or 0, p.key))
        if not order:
            return
        keys = [p.key for p in order]
        here = keys.index(self.selected) if self.selected in keys else (-1 if step > 0 else 0)
        self.select(order[(here + step) % len(order)])

    def select(self, person: Person) -> None:
        self.selected, self.selected_at = person.key, time.time()
        person.details = None
        threading.Thread(target=load_details, args=(person, self.board, self.pane_reader), daemon=True).start()

    def frame(self) -> tuple[str, list]:
        return self.header(), self.canvas().cells()

    def text(self) -> str:
        header, rows = self.frame()
        return "\n".join([header] + [encode(row, colour_mode(self.config)) for row in rows])

    def header(self) -> str:
        n = self.crowd.counts()
        red = "\033[1;31m" if n["blocked"] else "\033[2m"
        parts = {
            "title": ("\033[1m", self.scene.title),
            "clock": ("\033[2m", time.strftime("%H:%M")),
            "blocked": (red, "%d need you" % n["blocked"]),
            "working": ("\033[33m", "%d working" % n["working"]),
            "done": ("\033[32m", "%d done" % n["done"]),
            "idle": ("\033[2m", "%d idle" % n["idle"]),
            "hint": ("\033[2m", self.flash or "m menu"),
        }
        for least_needed in ("hint", "clock", "idle", "done"):
            if header_width(parts) <= self.size[0]:
                break
            del parts[least_needed]
        return "  ".join("%s%s\033[0m" % style_text for style_text in parts.values())

    def click(self, col: int, row: int) -> None:
        if self.menu.open:
            choice = self.menu.click(col, row - 1, self.menu_items())
            if choice:
                self.choose(choice)
            return
        px, py = col // self.scale, (row - 1) * 2 // self.scale
        if self.pet_hit(px, py):
            self.say_pet_line()
            return
        hit = self.scene.person_at(px, py, list(self.crowd.people.values()))
        if self.clicks.press(hit.key if hit else None, time.time()):
            jump_to(hit)
            self.selected = None
            return
        if hit is None or hit.key == self.selected:
            self.selected = None
        else:
            self.select(hit)

    def pet_hit(self, px: int, py: int) -> bool:
        if self.pet is None:
            return False
        x, y, _ = self.scene.pet_spot(self.t)
        return abs(px - (x + 3)) <= 5 and y - 8 <= py <= y + 2

    def say_pet_line(self) -> None:
        self.pet_line, self.pet_line_at = self.chatter.choice(self.pet.lines), time.time()

    def command(self, name: str) -> None:
        if name == "cycle-pet":
            self.choose("pet")
        elif name == "toggle-night":
            self.night_mode = "off" if self.night() else "on"
            self.remember()
        elif name == "snapshot":
            self.flash, self.flash_at = "snapshot: " + self.snapshot(), time.time()

    def snapshot(self, path: Optional[str] = None) -> str:
        path = path or os.path.join(self.config.state_dir, "snapshot-%s-%d.png" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid()))
        with open(path, "wb") as f:
            f.write(canvas_png(self.canvas()))
        return path


KEYS = {"p": "cycle-pet", "n": "toggle-night", "s": "snapshot"}
AMENITY = "amenity:"
NIGHT_MODES = ["auto", "on", "off"]


def next_in(options: list[str], current: str) -> str:
    return options[(options.index(current) + 1) % len(options)] if current in options else options[0]


def jump_to(person: Person) -> None:
    subprocess.Popen(["herdr", "agent", "focus", person.pane_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_source(config: Config, demo: bool) -> AgentSource:
    if demo:
        source = FakeSource()
        source.start()
        return source
    workspace, tab = os.environ.get("HERDR_WORKSPACE_ID"), os.environ.get("HERDR_TAB_ID")
    ledger = StatusLedger(path=os.path.join(config.state_dir, "since.json"))
    if config.source == "events":
        source = HerdrEventSource(HerdrClient(), workspace, tab, ledger)
        try:
            source.start()
            return source
        except (OSError, HerdrError, ValueError):
            source.close()
    source = PollingSource(workspace, tab, ledger)
    source.start()
    return source


def animate(office: Office, source: AgentSource, inbox: control.Inbox) -> None:
    screen = Screen(sys.stdout, colour_mode(office.config))
    screen.enter()
    started = time.monotonic()
    try:
        with Terminal() as terminal:
            while True:
                office.fit(*shutil.get_terminal_size((100, 30)))
                office.sync(source)
                for name in inbox.take():
                    office.command(name)
                if not source.visible():
                    screen.forget()
                    source.changed.wait(1.0)
                    source.changed.clear()
                    started = time.monotonic() - office.t * TICK_SECONDS
                    continue
                due = int((time.monotonic() - started) / TICK_SECONDS) - office.t
                if due > MAX_CATCH_UP:
                    started += (due - MAX_CATCH_UP) * TICK_SECONDS
                    due = MAX_CATCH_UP
                for _ in range(due):
                    office.step()
                screen.show(*office.frame())
                interval = 1 / (office.config.active_fps if office.lively() else office.config.still_fps)
                if terminal.interactive():
                    handle_input(office, read_raw(interval))
                else:
                    time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        screen.leave()
        source.close()


def handle_input(office: Office, raw: str) -> None:
    clicks, keys = parse(raw)
    for key in keys:
        office.press(key)
    for col, row in clicks:
        office.click(col, row)


def settle(office: Office, source: AgentSource, ticks: int) -> None:
    office.fit(*shutil.get_terminal_size((100, 30)))
    office.sync(source)
    for _ in range(ticks):
        office.step()


def open_tab(workspace: Optional[str], cli=herdr_cli) -> None:
    """Focus this workspace's office tab, or open one named after the office."""
    existing = office_tab(workspace, cli)
    if existing:
        cli("tab", "focus", existing)
        return
    args = ["plugin", "pane", "open", "--plugin", PLUGIN_ID, "--entrypoint", "office", "--placement", "tab", "--focus"]
    opened = cli(*args, *(["--workspace", workspace] if workspace else []))
    tab = opened.get("plugin_pane", {}).get("pane", {}).get("tab_id")
    if tab:
        cli("tab", "rename", tab, "office")


def header_width(parts: dict[str, tuple[str, str]]) -> int:
    text = "  ".join(text for _, text in parts.values())
    return len(text) + sum(1 for ch in text if ord(ch) >= 0x1F000)


def zoom_for(kind: type[Scene], w: int, h: int, desks: int) -> int:
    for scale in ZOOMS:
        room_w, room_h = -(-w // scale), -(-h // scale)
        roomy = room_w >= ZOOMED_ROOM_MIN[0] and room_h >= ZOOMED_ROOM_MIN[1]
        if roomy and kind.desk_capacity(room_w, room_h) >= desks:
            return scale
    return 1


def office_tab(workspace: Optional[str], cli) -> Optional[str]:
    panes = cli("pane", "list", *(["--workspace", workspace] if workspace else [])).get("panes", [])
    return next((p["tab_id"] for p in panes if p.get("label") == "office" and p.get("tab_id")), None)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="office", description="A pixel-art office for your herdr agents.")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "open", *control.COMMANDS])
    parser.add_argument("--once", action="store_true", help="draw one frame and exit")
    parser.add_argument("--demo", action="store_true", help="play a scripted day instead of reading herdr")
    parser.add_argument("--pet", help="cat, dog, chicken, duck, none, or one you added")
    parser.add_argument("--png", help="with --once, also write the frame to this PNG")
    parser.add_argument("--settle", type=int, default=150, help="with --once, ticks to run before drawing")
    args = parser.parse_args(argv)
    config = load_config()
    if args.command == "open":
        open_tab(os.environ.get("HERDR_WORKSPACE_ID"))
        return
    if args.command == "snapshot":
        print("\n".join(control.request_snapshot(config.state_dir)) or "no office is running")
        return
    if args.command in control.COMMANDS:
        control.send(config.state_dir, args.command)
        return
    apply_choices(config)
    config.pet = args.pet or os.environ.get("OFFICE_PET") or config.pet
    office = Office(config, load_pets(DATA_DIR, config.config_dir), load_palette(config))
    source = make_source(config, args.demo)
    if isinstance(source, FakeSource):
        office.pane_reader = source.pane_text
    if args.once:
        settle(office, source, args.settle)
        print(office.text())
        if args.png:
            print(office.snapshot(args.png))
        source.close()
        return
    animate(office, source, control.Inbox(config.state_dir))
