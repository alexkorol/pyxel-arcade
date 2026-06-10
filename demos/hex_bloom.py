"""Hex Bloom -- crystals blooming on a hexagonal grid.

Each pulse, an empty hex comes alive if it touches exactly one living
hex (the Ulam-Warburton rule). On hexagons this grows snowflakes;
seed several and watch the flakes collide into interference lace.

Controls:  click = plant a seed crystal
           U = toggle rule (flake / coral)     SPACE = clear

Study: axial hex coordinates and cube rounding (see Red Blob Games),
dict-based sparse grids, generation-banded color ramps.
"""
import math
import random

import pyxel

W = H = 128
S = 3                      # hex size in pixels
SQ3 = math.sqrt(3)
CX, CY = 64, 64
NEIGHBORS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
RULES = [({1}, "flake"), ({1, 2}, "coral")]
RAMP = [7, 12, 6, 11, 3, 10, 9, 8, 14, 2]
STEP_EVERY = 4             # frames between growth pulses


def hex_to_px(q, r):
    return CX + S * SQ3 * (q + r / 2), CY + S * 1.5 * r


def px_to_hex(x, y):
    """Pixel -> nearest hex, via fractional axial coords + cube rounding."""
    qf = ((x - CX) * SQ3 / 3 - (y - CY) / 3) / S
    rf = (y - CY) * 2 / 3 / S
    xf, zf, yf = qf, rf, -qf - rf
    rx, ry, rz = round(xf), round(yf), round(zf)
    dx, dy, dz = abs(rx - xf), abs(ry - yf), abs(rz - zf)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, rz


class App:
    def __init__(self):
        pyxel.init(W, H, title="hex bloom")
        pyxel.mouse(True)
        self.rule_i = 0
        self.clear()

    def run(self):
        pyxel.run(self.update, self.draw)

    def clear(self):
        self.born = {}      # (q, r) -> generation
        self.queue = []     # cells waiting to be painted
        self.gen = 0
        self.wipe = True
        self.plant(0, 0)

    def plant(self, q, r):
        if (q, r) not in self.born:
            self.born[(q, r)] = self.gen
            self.queue.append((q, r))

    def grow(self):
        rule = RULES[self.rule_i][0]
        counts = {}
        for (q, r) in self.born:
            for dq, dr in NEIGHBORS:
                c = (q + dq, r + dr)
                if c not in self.born:
                    counts[c] = counts.get(c, 0) + 1
        self.gen += 1
        for cell, k in counts.items():
            if k in rule:
                x, y = hex_to_px(*cell)
                self.born[cell] = self.gen
                if -4 < x < W + 4 and -4 < y < H + 4:
                    self.queue.append(cell)

    def update(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.clear()
        if pyxel.btnp(pyxel.KEY_U):
            self.rule_i = (self.rule_i + 1) % len(RULES)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.plant(*px_to_hex(pyxel.mouse_x, pyxel.mouse_y))
        if pyxel.frame_count % STEP_EVERY == 0:
            self.grow()

    def draw(self):
        if self.wipe:
            pyxel.cls(0)
            self.wipe = False
        # paint only newborn cells; old ones persist on the canvas
        for q, r in self.queue:
            x, y = hex_to_px(q, r)
            pyxel.circ(x, y, 1, RAMP[self.born[(q, r)] % len(RAMP)])
        self.queue = []
        pyxel.rect(0, 0, 60, 7, 0)
        pyxel.text(2, 1, f"rule: {RULES[self.rule_i][1]}", 5)


if __name__ == "__main__":
    App().run()
