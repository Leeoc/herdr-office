import json
import os
import subprocess
from dataclasses import dataclass, field, fields
from typing import Optional

import tomllib

PLUGIN_ID = "lee.herdr-office"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")


@dataclass
class Config:
    pet: str = "cat"
    scene: str = "office"
    night: str = "auto"
    source: str = "events"
    nap_after_minutes: float = 30
    ticket_pattern: str = r"(?i)\b([a-z]{2,}-\d+)"
    active_fps: float = 10
    still_fps: float = 3
    board: Optional[dict] = None
    closed: list = field(default_factory=list)
    config_dir: str = field(default="", compare=False)
    state_dir: str = field(default="", compare=False)


def load_config() -> Config:
    """Settings from config.toml in the plugin's config dir, with defaults for anything missing."""
    config_dir = plugin_config_dir()
    settings = read_toml(os.path.join(config_dir, "config.toml"))
    known = {f.name for f in fields(Config)} - {"config_dir", "state_dir"}
    config = Config(**{k: v for k, v in settings.items() if k in known})
    config.config_dir, config.state_dir = config_dir, plugin_state_dir()
    return config


def read_toml(path: str) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def plugin_config_dir() -> str:
    if os.environ.get("HERDR_PLUGIN_CONFIG_DIR"):
        return os.environ["HERDR_PLUGIN_CONFIG_DIR"]
    try:
        out = subprocess.run(["herdr", "plugin", "config-dir", PLUGIN_ID], capture_output=True, text=True, timeout=3)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.expanduser("~/.config/herdr/plugins/config/" + PLUGIN_ID)


def plugin_state_dir() -> str:
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "herdr-office")
    os.makedirs(state, exist_ok=True)
    return state


def choices_path(state_dir: str) -> str:
    return os.path.join(state_dir, "choices.json")


def apply_choices(config: Config) -> None:
    """Lay what was last picked in the menu over the config file, so choices survive a restart."""
    choices = read_json(choices_path(config.state_dir))
    config.closed = list(choices.get("closed", config.closed))
    config.pet = choices.get("pet", config.pet)
    config.night = choices.get("night", config.night)
    config.scene = choices.get("scene", config.scene)


def save_choices(state_dir: str, choices: dict) -> None:
    with open(choices_path(state_dir), "w") as f:
        json.dump(choices, f)


def load_palette(config: Config) -> dict:
    """People's colours: the bundled palette, with any lists from the user's palette.json taking over."""
    palette = read_json(os.path.join(DATA_DIR, "palette.json"))
    palette.update(read_json(os.path.join(config.config_dir, "palette.json")))
    return palette


def read_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
