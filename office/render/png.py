import struct
import zlib

from office.render.canvas import Canvas, Colour

# 3x5 glyphs, rows top to bottom, '1' for ink. Lower case is drawn as upper case.
GLYPHS = {
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "101111111101101", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
    "Q": "010101101110011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111",
    "0": "111101101101111", "1": "010110010010111", "2": "110001010100111", "3": "110001010001110",
    "4": "101101111001001", "5": "111100110001110", "6": "011100111101111", "7": "111001010010010",
    "8": "111101111101111", "9": "111101111001110",
    ":": "000010000010000", ".": "000000000000010", ",": "000000000010100", "-": "000000111000000",
    "_": "000000000000111", "/": "001001010100100", "?": "110001010000010", "!": "010010010000010",
    "'": "010010000000000", "(": "010100100100010", ")": "010001001001010", "·": "000000010000000",
    "…": "000000000000101", "*": "000101010101000", "+": "000010111010000", "=": "000111000111000",
    ">": "100010001010100", "<": "001010100010001", "#": "101111101111101", "&": "010101010101011",
    '"': "101101000000000", " ": "000000000000000", "[": "110100100100110", "]": "011001001001011",
    "↑": "010111010010010", "↓": "010010010111010",
}
UNKNOWN = "000010111010000"


def canvas_png(canvas: Canvas, scale: int = 8) -> bytes:
    """A PNG of the canvas as the terminal shows it: each pixel a `scale` square, labels in a small bitmap font."""
    rows = [bytearray(b"".join(bytes(colour) * scale for colour in row)) for row in canvas.px for _ in range(scale)]
    for (col, cell_row), (ch, fg) in canvas.text.items():
        if 0 <= col < canvas.w and 0 <= cell_row < canvas.h // 2:
            draw_glyph(rows, col * scale, cell_row * 2 * scale, scale, ch, fg, canvas.px[cell_row * 2 + 1][col])
    return encode_png(rows, canvas.w * scale)


def draw_glyph(rows: list[bytearray], left: int, top: int, scale: int, ch: str, fg: Colour, bg: Colour) -> None:
    cell_w, cell_h = scale, scale * 2
    paint(rows, left, top, cell_w, cell_h, bg)
    dot = max(1, scale // 4)
    x0, y0 = left + (cell_w - 3 * dot) // 2, top + (cell_h - 5 * dot) // 2
    for i, bit in enumerate(GLYPHS.get(ch.upper(), UNKNOWN)):
        if bit == "1":
            paint(rows, x0 + (i % 3) * dot, y0 + (i // 3) * dot, dot, dot, fg)


def paint(rows: list[bytearray], x: int, y: int, w: int, h: int, colour: Colour) -> None:
    run = bytes(colour) * w
    for yy in range(y, min(y + h, len(rows))):
        rows[yy][x * 3:(x + w) * 3] = run


def encode_png(rows: list[bytes], width: int) -> bytes:
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(rows), 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
