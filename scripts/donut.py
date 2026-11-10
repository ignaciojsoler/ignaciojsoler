"""Generate the spinning ASCII donut used as the profile card's animation.

    python scripts/donut.py

Writes assets/ascii.txt as a sequence of frames separated by a line holding
just `---`. scripts/today.py plays them as a loop inside both SVGs. The loop
is seamless: both rotation angles complete exactly one turn over FRAMES.

Standard library only. To go back to the photo portrait, run
scripts/ascii_art.py instead (it overwrites assets/ascii.txt with one frame).
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets/ascii.txt"

COLS, ROWS = 64, 41
# Same cell geometry as the card (11px font, 13px lines, ~0.6em glyph width).
CELL_W, CELL_H = 6.6, 13.0
FRAMES = 24
R1, R2, K2 = 1.0, 2.0, 8.0   # tube radius, ring radius, camera distance
K1 = 410.0                   # px per unit at distance 1 (sets the size)
RAMP = ".,-~:;=!*#$@"


def frame(a, b):
    cos_a, sin_a, cos_b, sin_b = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    grid = [[" "] * COLS for _ in range(ROWS)]
    zbuf = [[0.0] * COLS for _ in range(ROWS)]
    cx, cy = COLS * CELL_W / 2, ROWS * CELL_H / 2

    theta = 0.0
    while theta < 2 * math.pi:
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        phi = 0.0
        while phi < 2 * math.pi:
            cos_p, sin_p = math.cos(phi), math.sin(phi)
            circle_x, circle_y = R2 + R1 * cos_t, R1 * sin_t
            x = circle_x * (cos_b * cos_p + sin_a * sin_b * sin_p) - circle_y * cos_a * sin_b
            y = circle_x * (sin_b * cos_p - sin_a * cos_b * sin_p) + circle_y * cos_a * cos_b
            z = K2 + cos_a * circle_x * sin_p + circle_y * sin_a
            ooz = 1 / z
            col = int((cx + K1 * ooz * x) / CELL_W)
            row = int((cy - K1 * ooz * y) / CELL_H)
            lum = (cos_p * cos_t * sin_b - cos_a * cos_t * sin_p - sin_a * sin_t
                   + cos_b * (cos_a * sin_t - cos_t * sin_a * sin_p))
            if 0 <= col < COLS and 0 <= row < ROWS and lum > 0 and ooz > zbuf[row][col]:
                zbuf[row][col] = ooz
                grid[row][col] = RAMP[min(len(RAMP) - 1, int(lum * 8))]
            phi += 0.02
        theta += 0.07
    return "\n".join("".join(r).rstrip() for r in grid)


def main():
    frames = []
    for i in range(FRAMES):
        t = 2 * math.pi * i / FRAMES
        frames.append(frame(t, t))
    OUT.write_text("\n---\n".join(frames) + "\n")
    print(f"{FRAMES} frames -> {OUT}")


if __name__ == "__main__":
    main()
