import io
import struct
import unittest
import zlib

from office.render.canvas import Canvas, encode
from office.render.png import canvas_png
from office.render.screen import Screen, changed_span

RED, BLUE = (255, 0, 0), (0, 0, 255)


R, B = (RED, RED, "x"), (BLUE, BLUE, "y")


def fresh_screen(header, rows):
    out = io.StringIO()
    screen = Screen(out)
    screen.show(header, rows)
    out.truncate(0)
    out.seek(0)
    return screen, out


class ScreenTest(unittest.TestCase):
    def test_first_frame_clears_and_draws_everything(self):
        out = io.StringIO()
        Screen(out).show("head", [[R]])
        self.assertEqual(out.getvalue(), "\033[H\033[2Jhead\033[K\n" + encode([R]))

    def test_later_frames_send_only_the_changed_span(self):
        screen, out = fresh_screen("head", [[R, R, R, R], [R, R, R, R]])
        sent = screen.show("head", [[R, R, R, R], [R, B, B, R]])
        self.assertEqual(out.getvalue(), "\033[3;2H" + encode([B, B]))
        self.assertEqual(sent, len(out.getvalue().encode()))

    def test_header_redrawn_only_when_it_changes(self):
        screen, out = fresh_screen("12:00", [[R]])
        screen.show("12:01", [[R]])
        self.assertEqual(out.getvalue(), "\033[1;1H12:01\033[K")

    def test_unchanged_frame_sends_nothing(self):
        screen, _ = fresh_screen("head", [[R]])
        self.assertEqual(screen.show("head", [[R]]), 0)

    def test_forgetting_or_resizing_forces_a_full_redraw(self):
        screen, out = fresh_screen("head", [[R]])
        screen.forget()
        screen.show("head", [[R]])
        self.assertTrue(out.getvalue().startswith("\033[H\033[2J"))
        out.truncate(0)
        out.seek(0)
        screen.show("head", [[R, R]])
        self.assertTrue(out.getvalue().startswith("\033[H\033[2J"))


class ChangedSpanTest(unittest.TestCase):
    def test_finds_first_and_last_difference(self):
        old = list(range(200))
        for first, last in ((0, 0), (0, 199), (5, 5), (17, 140), (199, 199)):
            row = old[:]
            row[first] = row[last] = -1
            self.assertEqual(changed_span(row, old), (first, last))


class CanvasTest(unittest.TestCase):
    def test_two_pixels_per_cell(self):
        canvas = Canvas(2, 2, RED)
        canvas.dot(1, 1, BLUE)
        self.assertEqual(canvas.cells(), [[(RED, RED, "▀"), (RED, BLUE, "▀")]])

    def test_labels_sit_on_the_lower_pixel_colour(self):
        canvas = Canvas(1, 2, RED)
        canvas.label(0, 0, "x", BLUE)
        self.assertEqual(canvas.cells(), [[(BLUE, RED, "x")]])

    def test_encoding_sets_colours_once_per_run(self):
        self.assertEqual(encode([R, R, B]), "\033[38;2;255;0;0m\033[48;2;255;0;0mxx\033[38;2;0;0;255m\033[48;2;0;0;255my\033[0m")


class DirtySpanTest(unittest.TestCase):
    def test_drawn_span_is_rebuilt_and_the_rest_reused(self):
        base = Canvas(6, 4, RED)
        canvas = Canvas.over(base)
        canvas.dot(2, 3, BLUE)
        canvas.dot(4, 2, BLUE)
        rows = canvas.cells()
        self.assertIs(rows[0], base.cells()[0])
        self.assertEqual(rows[1], [(RED, RED, "▀")] * 2 + [(RED, BLUE, "▀"), (RED, RED, "▀"), (BLUE, RED, "▀"), (RED, RED, "▀")])

    def test_labelled_rows_do_not_touch_the_base(self):
        base = Canvas(2, 2, RED)
        canvas = Canvas.over(base)
        canvas.label(0, 0, "x", BLUE)
        canvas.cells()
        self.assertEqual(base.cells(), [[(RED, RED, "▀"), (RED, RED, "▀")]])


class PngTest(unittest.TestCase):
    def test_png_is_well_formed_at_scale(self):
        canvas = Canvas(3, 2, RED)
        canvas.label(0, 0, "A", BLUE)
        data = canvas_png(canvas, scale=4)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (12, 8))
        idat_length = struct.unpack(">I", data[33:37])[0]
        raw = zlib.decompress(data[41:41 + idat_length])
        self.assertEqual(len(raw), height * (1 + width * 3))


if __name__ == "__main__":
    unittest.main()
