"""Turn assets/photo.jpg into the ASCII portrait used by the profile card.

Run it once, or again whenever the photo changes:

    python scripts/ascii_art.py

The result lands in assets/ascii.txt, which scripts/today.py embeds in both
SVGs. Needs Pillow (pip install pillow).
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "assets/photo.jpg"
OUT = ROOT / "assets/ascii.txt"

COLS, ROWS = 64, 41
# Has to match the portrait's font in today.py (11px font, 13px lines): a
# monospace cell is ~0.6em wide, so cells are about half as wide as tall.
CELL_RATIO = 0.6 * 11 / 13
# Horizontal slice of the photo to keep; the face sits left of centre.
CROP_X = (40, 360)

# Sparse to dense. Darkness in the photo picks the glyph: the card is dark,
# so hair, beard and eyes get the heavy glyphs and lit skin stays airy, which
# is what makes the features read.
RAMP = " .,:;i1tfLCG08@"
GAMMA = 1.2


def background_mask(im):
    """255 where the flat studio background is, 0 on the subject."""
    flood = im.filter(ImageFilter.GaussianBlur(1.5)).convert("RGB")
    w, h = im.size
    for seed in [(2, 2), (w - 3, 2), (2, h * 3 // 4), (w - 3, h * 3 // 8)]:
        ImageDraw.floodfill(flood, seed, (255, 0, 0), thresh=7)
    r, g, _ = flood.split()
    mask = ImageChops.difference(r, g).point(lambda v: 255 if v > 200 else 0)
    # Grow it a little so the dark halo around the cut-out doesn't become a
    # line of heavy glyphs along the silhouette.
    return mask.filter(ImageFilter.MaxFilter(5))


def drop_strays(lines):
    """Blank out glyphs with no neighbours; they're mask noise, not features."""
    at = lambda x, y: 0 <= y < len(lines) and 0 <= x < len(lines[y]) and lines[y][x] != " "
    return ["".join(
        ch if ch == " " or any(at(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                               if dx or dy) else " "
        for x, ch in enumerate(row)) for y, row in enumerate(lines)]


def main():
    photo = Image.open(PHOTO).convert("L")
    mask = background_mask(photo)

    x0, x1 = CROP_X
    height = round((x1 - x0) * ROWS / (COLS * CELL_RATIO))
    box = (x0, 0, x1, min(height, photo.height))
    im, mask = photo.crop(box), mask.crop(box)

    subject = ImageOps.invert(mask)
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im = im.filter(ImageFilter.UnsharpMask(radius=10, percent=180, threshold=0))
    im = ImageOps.equalize(im, mask=subject)

    small = im.resize((COLS, ROWS), Image.BOX)
    small_mask = mask.resize((COLS, ROWS), Image.BOX)

    lines = []
    for y in range(ROWS):
        row = ""
        for x in range(COLS):
            if small_mask.getpixel((x, y)) > 140:
                row += " "
                continue
            darkness = (1 - small.getpixel((x, y)) / 255) ** GAMMA
            row += RAMP[min(len(RAMP) - 1, int(darkness * len(RAMP)))]
        lines.append(row)

    lines = [row.rstrip() for row in drop_strays(lines)]
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
