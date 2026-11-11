from typing import Optional

from office.render.canvas import Canvas
from office.render.light import LightMap
from office.scenes.base import FrameView, Scene


class FrameBuilder:
    """Builds frames from a cached background, so each frame only draws what moves."""

    def __init__(self):
        self.background_for = None
        self.background = None
        self.light_for = None
        self.light = None
        self.zoomed_for = None
        self.zoomed = None

    def build(self, scene: Scene, view: FrameView, scale: int = 1, size: Optional[tuple[int, int]] = None) -> Canvas:
        """The scene's frame for `view`, with lighting applied and switched off again for overlays.

        With `scale` above 1, each scene pixel becomes a scale-by-scale block on a canvas of `size`.
        """
        light = self.lighting(scene, view)
        background = self.cached_background(scene, view, light)
        canvas = Canvas.over(background, light)
        scene.paint_foreground(canvas, view)
        canvas.light = None
        if scale == 1:
            return canvas
        size = size or (scene.w * scale, scene.h * scale)
        if self.zoomed_for != (background, scale, size):
            self.zoomed_for, self.zoomed = (background, scale, size), zoom(background, scale, *size)
        return zoom_changes(canvas, self.zoomed, scale)

    def lighting(self, scene: Scene, view: FrameView):
        if not view.night:
            return None
        key = (scene, tuple(scene.lamps(view)))
        if key != self.light_for:
            self.light_for, self.light = key, LightMap(scene.w, scene.h, list(key[1]))
        return self.light

    def cached_background(self, scene: Scene, view: FrameView, light) -> Canvas:
        key = (scene, scene.background_key(view), frozenset(view.building), light)
        if key != self.background_for:
            canvas = Canvas(scene.w, scene.h, scene.fill)
            canvas.light = light
            scene.paint_background(canvas, view)
            self.background_for, self.background = key, canvas
        return self.background


def zoom(source: Canvas, scale: int, w: int, h: int) -> Canvas:
    canvas = Canvas(w, h, (0, 0, 0))
    columns = [x // scale for x in range(w)]
    for y in range(min(h, source.h * scale)):
        row = source.px[y // scale]
        canvas.px[y] = [row[x] for x in columns]
    return canvas


def zoom_changes(canvas: Canvas, zoomed_background: Canvas, scale: int) -> Canvas:
    """The zoomed background with only the pixels and labels drawn over `canvas`'s background copied in."""
    out = Canvas.over(zoomed_background)
    for cell_row, (first, last) in canvas.dirty.items():
        for y in range(2 * cell_row, min(2 * cell_row + 2, canvas.h)):
            row = canvas.px[y]
            for x in range(first, last + 1):
                out.rect(x * scale, y * scale, scale, scale, row[x])
    out.text = zoom_labels(canvas.text, scale)
    return out


def zoom_labels(text: dict[tuple[int, int], tuple], scale: int) -> dict[tuple[int, int], tuple]:
    """Labels moved to their zoomed spot, each run of letters kept together rather than spread out."""
    zoomed, run_start, last = {}, 0, None
    for x, row in sorted(text, key=lambda spot: (spot[1], spot[0])):
        if last != (x - 1, row):
            run_start = x
        zoomed[(run_start * scale + x - run_start, row * scale)] = text[(x, row)]
        last = (x, row)
    return zoomed
