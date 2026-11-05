"""Renders screenshots/demo.gif from the scripted demo day: python3 tools/demo_gif.py"""
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from office import app  # noqa: E402
from office.config import load_config  # noqa: E402
from office.details import pane_story  # noqa: E402
from office.people.timing import TICK_SECONDS  # noqa: E402
from office.render.png import draw_glyph  # noqa: E402
from office.sources.fake import FakeSource  # noqa: E402

COLS, ROWS, SCALE = 160, 46, 6
WARM_UP_TICKS = 80
SHOTS = 160
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots", "demo.gif")


def main() -> None:
    office, source = demo_office()
    frames = [frame_pixels(office, source, shot) for shot in range(SHOTS)]
    with open(OUT, "wb") as f:
        f.write(gif_bytes(frames, delay_cs=10))
    print("%s: %d frames, %d KB" % (OUT, len(frames), os.path.getsize(OUT) // 1024))


def demo_office():
    os.environ["OFFICE_HOUR"] = "11"
    os.environ["HERDR_PLUGIN_STATE_DIR"] = tempfile.mkdtemp()
    config = load_config()
    config.scene, config.pet, config.closed = "office", "cat", []
    office = app.Office(config, app.load_pets(app.DATA_DIR), app.load_palette(config))
    source = FakeSource(clock=lambda: office.t * TICK_SECONDS)
    office.fit(COLS, ROWS)
    for _ in range(WARM_UP_TICKS):
        tick(office, source)
    return office, source


def tick(office, source) -> None:
    source.advance()
    office.sync(source)
    office.step()


def frame_pixels(office, source, shot: int) -> list[bytearray]:
    direct(office, shot)
    tick(office, source)
    office.fit(COLS, ROWS)
    return scaled(office.canvas())


def direct(office, shot: int) -> None:
    """The story the clip tells: a quiet office, a click on someone working, the menu, then the station."""
    if shot == 45:
        person = office.crowd.people["app-142:p1"]
        with open(os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "claude_working.txt")) as f:
            person.details = pane_story([line for line in f.read().splitlines() if line.strip()])
        office.selected, office.selected_at = person.key, 1e18
    if shot == 80:
        office.selected = None
        office.press("m")
    if 84 <= shot <= 92 and shot % 4 == 0:
        office.press("down")
    if shot == 96:
        for _ in range(3):
            office.press("up")
    if shot == 102:
        office.press("space")
    if shot == 112:
        office.press("m")


def scaled(canvas) -> list[bytearray]:
    rows = [bytearray(b"".join(bytes(c) * SCALE for c in row)) for row in canvas.px for _ in range(SCALE)]
    for (col, cell_row), (ch, fg) in canvas.text.items():
        if 0 <= col < canvas.w and 0 <= cell_row < canvas.h // 2:
            draw_glyph(rows, col * SCALE, cell_row * 2 * SCALE, SCALE, ch, fg, canvas.px[cell_row * 2 + 1][col])
    return rows


def gif_bytes(frames: list[list[bytearray]], delay_cs: int) -> bytes:
    palette, indexed = index_frames(frames)
    height, width = len(indexed[0]), len(indexed[0][0])
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", width, height, 0xF7, 0, 0))
    out += b"".join(bytes(c) for c in palette) + b"\x00\x00\x00" * (256 - len(palette))
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    previous = None
    for image in indexed:
        box = changed_box(previous, image) if previous else (0, 0, width, height)
        previous = image
        if box is None:
            box = (0, 0, 1, 1)
        x, y, w, h = box
        out += b"\x21\xf9\x04\x04" + struct.pack("<H", delay_cs) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHHB", x, y, w, h, 0)
        out += bytes([8]) + sub_blocks(lzw([v for row in image[y:y + h] for v in row[x:x + w]], 8))
    return bytes(out + b"\x3b")


def index_frames(frames: list[list[bytearray]]) -> tuple[list[tuple], list[list[bytes]]]:
    colours: dict[tuple, int] = {}
    indexed = []
    for rows in frames:
        image = []
        for row in rows:
            image.append(bytes(colours.setdefault(tuple(row[i:i + 3]), len(colours)) for i in range(0, len(row), 3)))
        indexed.append(image)
    if len(colours) > 256:
        raise SystemExit("the clip uses %d colours; a GIF holds 256" % len(colours))
    return sorted(colours, key=colours.get), indexed


def changed_box(before: list[bytes], after: list[bytes]):
    rows = [y for y in range(len(after)) if before[y] != after[y]]
    if not rows:
        return None
    cols = [x for y in rows for x in (first_difference(before[y], after[y]), last_difference(before[y], after[y]))]
    return min(cols), rows[0], max(cols) - min(cols) + 1, rows[-1] - rows[0] + 1


def first_difference(a: bytes, b: bytes) -> int:
    return next(i for i in range(len(a)) if a[i] != b[i])


def last_difference(a: bytes, b: bytes) -> int:
    return next(i for i in range(len(a) - 1, -1, -1) if a[i] != b[i])


def lzw(indices: list[int], min_size: int) -> bytes:
    """GIF's variant of LZW: variable-width codes, packed least significant bit first, reset at 4096 codes."""
    clear, end = 1 << min_size, (1 << min_size) + 1
    out, bits, bit_count = bytearray(), 0, 0
    size, table, next_code = min_size + 1, {}, end + 1

    def emit(code: int) -> None:
        nonlocal bits, bit_count
        bits |= code << bit_count
        bit_count += size
        while bit_count >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8

    emit(clear)
    prefix = indices[0]
    for symbol in indices[1:]:
        key = (prefix << 8) | symbol
        if key in table:
            prefix = table[key]
            continue
        emit(prefix)
        if next_code < 4096:
            table[key] = next_code
            next_code += 1
            if next_code > (1 << size) and size < 12:
                size += 1
        else:
            emit(clear)
            size, table, next_code = min_size + 1, {}, end + 1
        prefix = symbol
    emit(prefix)
    emit(end)
    if bit_count:
        out.append(bits & 0xFF)
    return bytes(out)


def sub_blocks(data: bytes) -> bytes:
    return b"".join(bytes([len(data[i:i + 255])]) + data[i:i + 255] for i in range(0, len(data), 255)) + b"\x00"


if __name__ == "__main__":
    main()
