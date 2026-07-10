"""Generate the arcade favicon set (SVG + 32px/180px PNG) from a pixel sprite."""
import os

from PIL import Image

SPRITE = [
    "..#..#..",
    "..####..",
    ".######.",
    "##.##.##",
    "########",
    "#.####.#",
    "#..##..#",
    ".#....#.",
]
BG = (11, 11, 18)
FG = (67, 255, 173)

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "assets")


def make_png(px_per_cell, pad_cells, path):
    n = len(SPRITE)
    size = (n + 2 * pad_cells) * px_per_cell
    img = Image.new("RGB", (size, size), BG)
    for y, row in enumerate(SPRITE):
        for x, cell in enumerate(row):
            if cell != "#":
                continue
            x0 = (x + pad_cells) * px_per_cell
            y0 = (y + pad_cells) * px_per_cell
            for dy in range(px_per_cell):
                for dx in range(px_per_cell):
                    img.putpixel((x0 + dx, y0 + dy), FG)
    img.save(path)
    print("wrote", path, img.size)


def make_svg(path):
    n = len(SPRITE)
    cells = []
    for y, row in enumerate(SPRITE):
        for x, cell in enumerate(row):
            if cell == "#":
                cells.append(f'<rect x="{x + 1}" y="{y + 1}" width="1" height="1"/>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n + 2} {n + 2}">'
        f'<rect width="{n + 2}" height="{n + 2}" rx="1.5" fill="rgb{BG}"/>'
        f'<g fill="rgb{FG}">{"".join(cells)}</g></svg>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", path)


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    make_svg(os.path.join(ASSETS, "favicon.svg"))
    for size in (32, 180, 192, 512):
        path = os.path.join(ASSETS, f"icon-{size}.png")
        make_png(max(1, size // 10), 1, path)
        img = Image.open(path)
        img.resize((size, size), Image.NEAREST).save(path)
    print("done")
