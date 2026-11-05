import importlib
import os

from office.scenes.base import Scene


def scene_class(name: str) -> type[Scene]:
    """The scene in office/scenes/<name>.py, which names its class as SCENE."""
    return importlib.import_module("office.scenes.%s" % name).SCENE


def scene_names() -> list[str]:
    """Every scene module installed, office first."""
    folder = os.path.dirname(__file__)
    names = sorted(f[:-3] for f in os.listdir(folder) if f.endswith(".py") and f not in ("__init__.py", "base.py"))
    return sorted(names, key=lambda name: name != "office")
