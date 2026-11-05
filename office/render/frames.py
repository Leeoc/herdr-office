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

    def build(self, scene: Scene, view: FrameView) -> Canvas:
        """The scene's frame for `view`, with lighting applied and switched off again for overlays."""
        light = self.lighting(scene, view)
        canvas = Canvas.over(self.cached_background(scene, view, light), light)
        scene.paint_foreground(canvas, view)
        canvas.light = None
        return canvas

    def lighting(self, scene: Scene, view: FrameView):
        if not view.night:
            return None
        key = (scene, tuple(scene.lamps(view)))
        if key != self.light_for:
            self.light_for, self.light = key, LightMap(scene.w, scene.h, list(key[1]))
        return self.light

    def cached_background(self, scene: Scene, view: FrameView, light) -> Canvas:
        key = (scene, scene.background_key(view), light)
        if key != self.background_for:
            canvas = Canvas(scene.w, scene.h, scene.fill)
            canvas.light = light
            scene.paint_background(canvas, view)
            self.background_for, self.background = key, canvas
        return self.background
