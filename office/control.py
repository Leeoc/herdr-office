import glob
import os
import time

COMMANDS = ("cycle-pet", "toggle-night", "snapshot")


class Inbox:
    """Commands from plugin actions to every running office, through a file both sides can find.

    Actions append a line; each office reads what arrived since it last looked, so a command
    reaches all open offices without anyone tracking their process ids.
    """

    def __init__(self, state_dir: str):
        self.path = os.path.join(state_dir, "commands")
        self.offset = self.size()

    def size(self) -> int:
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def take(self) -> list[str]:
        size = self.size()
        if size == self.offset:
            return []
        if size < self.offset:
            self.offset = 0
        with open(self.path) as f:
            f.seek(self.offset)
            text = f.read()
        self.offset = size
        return [line for line in text.split() if line in COMMANDS]


def send(state_dir: str, command: str) -> None:
    with open(os.path.join(state_dir, "commands"), "a") as f:
        f.write(command + "\n")


def snapshots_after(state_dir: str, moment: float) -> list[str]:
    return sorted(p for p in glob.glob(os.path.join(state_dir, "snapshot-*.png")) if os.path.getmtime(p) >= moment)


def request_snapshot(state_dir: str, wait: float = 3.0) -> list[str]:
    """Ask every running office for a snapshot and return the PNG paths written within `wait` seconds."""
    asked = time.time()
    send(state_dir, "snapshot")
    deadline = asked + wait
    while time.time() < deadline:
        time.sleep(0.2)
        written = snapshots_after(state_dir, asked)
        if written:
            time.sleep(0.3)
            return snapshots_after(state_dir, asked)
    return []
