"""Powder Box -- a tiny falling-sand sandbox.

Controls:  left-drag = paint     right-drag = erase
           1 sand  2 water  3 wall  4 plant  5 fire  0 erase
           Z / X = brush smaller / bigger     C = clear

Study: cellular automata on a flat bytearray, two scan passes
(fallers scan bottom-up, risers top-down, so nothing moves twice
per frame), and dirty-cell rendering for speed.
"""
import random

import pyxel

W, SIM_H, BAR_H = 128, 116, 12
EMPTY, WALL, SAND, WATER, PLANT, FIRE, SMOKE = range(7)
COLORS = {
    EMPTY: (0,), WALL: (13,), SAND: (15, 9), WATER: (12, 6),
    PLANT: (11, 3), FIRE: (8, 9, 10), SMOKE: (13, 5),
}
PALETTE_KEYS = [  # (key, element, label)
    (pyxel.KEY_1, SAND, "sand"), (pyxel.KEY_2, WATER, "watr"),
    (pyxel.KEY_3, WALL, "wall"), (pyxel.KEY_4, PLANT, "plnt"),
    (pyxel.KEY_5, FIRE, "fire"), (pyxel.KEY_0, EMPTY, "del"),
]


class App:
    def __init__(self):
        pyxel.init(W, SIM_H + BAR_H, title="powder box")
        # keep the engine cursor hidden: it gets stamped into the screen
        # buffer, and on a no-cls canvas every stamp would stay behind.
        # the brush ring drawn in draw() is the cursor instead.
        pyxel.mouse(False)
        self.element = SAND
        self.brush = 3
        self.repair = None  # (x, y, r) cursor-ring area to restore next frame
        self.clear()

    def run(self):
        pyxel.run(self.update, self.draw)

    def clear(self):
        self.grid = bytearray(W * SIM_H)
        self.dirty = []
        for x in range(W):  # jar walls on every border
            self.set(x, 0, WALL)
            self.set(x, SIM_H - 1, WALL)
        for y in range(SIM_H):
            self.set(0, y, WALL)
            self.set(W - 1, y, WALL)
        self.wipe = True

    # -- grid helpers -------------------------------------------------
    def get(self, x, y):
        return self.grid[x + y * W]

    def set(self, x, y, e):
        self.grid[x + y * W] = e
        self.dirty.append((x, y))

    def swap(self, x, y, nx, ny):
        a, b = self.get(x, y), self.get(nx, ny)
        self.set(x, y, b)
        self.set(nx, ny, a)

    # -- per-element rules --------------------------------------------
    def fall(self, x, y, through):
        """Sand-style: straight down, else diagonally, sinking through
        anything listed in `through`."""
        if self.get(x, y + 1) in through:
            self.swap(x, y, x, y + 1)
            return
        dx = random.choice((-1, 1))
        if self.get(x + dx, y + 1) in through:
            self.swap(x, y, x + dx, y + 1)

    def flow(self, x, y):
        below = self.get(x, y + 1)
        if below == EMPTY:
            self.swap(x, y, x, y + 1)
            return
        dx = random.choice((-1, 1))
        if self.get(x + dx, y + 1) == EMPTY:
            self.swap(x, y, x + dx, y + 1)
        elif self.get(x + dx, y) == EMPTY:
            self.swap(x, y, x + dx, y)

    def sprout(self, x, y):
        if random.random() < 0.02:
            dx, dy = random.choice(((0, -1), (-1, 0), (1, 0), (0, -1)))
            if self.get(x + dx, y + dy) == WATER:  # drink water, grow
                self.set(x + dx, y + dy, PLANT)

    def burn(self, x, y):
        self.dirty.append((x, y))  # always redraw fire so it flickers
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            n = self.get(x + dx, y + dy)
            if n == PLANT and random.random() < 0.25:
                self.set(x + dx, y + dy, FIRE)
            elif n == WATER:  # doused
                self.set(x, y, SMOKE)
                return
        r = random.random()
        if r < 0.04:
            self.set(x, y, SMOKE)
        elif r < 0.06:
            self.set(x, y, EMPTY)
        elif r < 0.4 and self.get(x, y - 1) == EMPTY:  # flames lick upward
            self.swap(x, y, x, y - 1)

    def rise(self, x, y):
        if random.random() < 0.05:
            self.set(x, y, EMPTY)
            return
        dx = random.choice((-1, 0, 0, 1))
        if y > 0 and self.get(x + dx, y - 1) == EMPTY:
            self.swap(x, y, x + dx, y - 1)

    # -- main loop ----------------------------------------------------
    def update(self):
        if pyxel.btnp(pyxel.KEY_C):
            self.clear()
        if pyxel.btnp(pyxel.KEY_Z):
            self.brush = max(1, self.brush - 1)
        if pyxel.btnp(pyxel.KEY_X):
            self.brush = min(8, self.brush + 1)
        for key, elem, _ in PALETTE_KEYS:
            if pyxel.btnp(key):
                self.element = elem
        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            self.paint(self.element)
        if pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT):
            self.paint(EMPTY)

        # pass 1: things that fall -- scan bottom-up so each grain
        # only moves once per frame
        rows = range(SIM_H - 2, 0, -1)
        for y in rows:
            xs = range(1, W - 1) if (y + pyxel.frame_count) % 2 else \
                 range(W - 2, 0, -1)
            for x in xs:
                e = self.get(x, y)
                if e == SAND:
                    self.fall(x, y, (EMPTY, WATER))
                elif e == WATER:
                    self.flow(x, y)
                elif e == PLANT:
                    self.sprout(x, y)
        # pass 2: things that rise -- scan top-down for the same reason
        for y in range(1, SIM_H - 1):
            for x in range(1, W - 1):
                e = self.get(x, y)
                if e == FIRE:
                    self.burn(x, y)
                elif e == SMOKE:
                    self.rise(x, y)

    def paint(self, elem):
        mx, my, r = pyxel.mouse_x, pyxel.mouse_y, self.brush
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > r * r:
                    continue
                x, y = mx + dx, my + dy
                if 1 <= x < W - 1 and 1 <= y < SIM_H - 1:
                    if elem == EMPTY or self.get(x, y) in (EMPTY, WATER, SMOKE):
                        self.set(x, y, elem)

    # -- rendering ----------------------------------------------------
    def draw(self):
        if self.wipe:
            pyxel.cls(0)
            self.wipe = False
        if self.repair:  # restore cells under last frame's cursor ring
            mx, my, r = self.repair
            for y in range(max(1, my - r - 1), min(SIM_H - 1, my + r + 2)):
                for x in range(max(1, mx - r - 1), min(W - 1, mx + r + 2)):
                    pyxel.pset(x, y, random.choice(COLORS[self.get(x, y)]))
        for x, y in self.dirty:  # only repaint cells that changed
            pyxel.pset(x, y, random.choice(COLORS[self.get(x, y)]))
        self.dirty = []

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if my < SIM_H:
            pyxel.circb(mx, my, self.brush, 7)
            self.repair = (mx, my, self.brush)
        else:
            self.repair = None

        # toolbar
        pyxel.rect(0, SIM_H, W, BAR_H, 1)
        for i, (_, elem, label) in enumerate(PALETTE_KEYS):
            x = 2 + i * 21
            pyxel.rect(x, SIM_H + 2, 8, 8, COLORS[elem][0])
            pyxel.text(x + 10, SIM_H + 4, label[0], 7)
            if elem == self.element:
                pyxel.rectb(x - 1, SIM_H + 1, 10, 10, 7)


if __name__ == "__main__":
    App().run()
