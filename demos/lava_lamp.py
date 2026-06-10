"""Lava Lamp -- six blobs of goo melt into each other as metaballs.

Each blob radiates an invisible field; wherever the combined field is
strong enough, goo appears. Heat at the bottom makes blobs buoyant,
cold at the top sinks them: a perpetual lamp.

Controls:  click = poke the goo     SPACE = reheat
           Z / X = fewer / more blobs

Study: scalar fields and isothreshold rendering (the heart of
metaballs), buoyancy as a feedback loop, chunky block rendering.
"""
import random

import pyxel

W = H = 128
CELL = 4                       # field is sampled every 4 px
BANDS = ((2.2, 10), (1.4, 9), (1.0, 8), (0.75, 2))  # (threshold, color)


class Blob:
    def __init__(self):
        self.x = random.uniform(20, 108)
        self.y = random.uniform(20, 108)
        self.r = random.uniform(9, 15)
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = 0.0
        self.heat = random.random()

    def update(self):
        if self.y > 96:
            self.heat = min(1.0, self.heat + 0.004)   # warmed by the bulb
        if self.y < 40:
            self.heat = max(0.0, self.heat - 0.004)   # cooled at the cap
        self.vy += 0.016 - self.heat * 0.032          # hot goo rises
        self.vx += random.uniform(-0.01, 0.01)
        self.vx *= 0.99
        self.vy *= 0.99
        self.x += self.vx
        self.y += self.vy
        if not self.r < self.x < W - self.r:
            self.vx *= -0.6
            self.x = max(self.r, min(W - self.r, self.x))
        if not self.r < self.y < H - self.r:
            self.vy *= -0.4
            self.y = max(self.r, min(H - self.r, self.y))


class App:
    def __init__(self):
        pyxel.init(W, H, title="lava lamp")
        pyxel.mouse(True)
        self.blobs = [Blob() for _ in range(6)]

    def run(self):
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            for b in self.blobs:
                b.heat = random.random()
        if pyxel.btnp(pyxel.KEY_Z) and len(self.blobs) > 2:
            self.blobs.pop()
        if pyxel.btnp(pyxel.KEY_X) and len(self.blobs) < 9:
            self.blobs.append(Blob())
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):  # shove blobs away from click
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            for b in self.blobs:
                dx, dy = b.x - mx, b.y - my
                d2 = dx * dx + dy * dy + 30
                b.vx += dx * 60 / d2
                b.vy += dy * 60 / d2
        for b in self.blobs:
            b.update()

    def draw(self):
        blobs = [(b.x, b.y, b.r * b.r) for b in self.blobs]
        for gy in range(0, H, CELL):
            fy = gy + CELL / 2
            for gx in range(0, W, CELL):
                fx = gx + CELL / 2
                field = sum(r2 / ((fx - bx) ** 2 + (fy - by) ** 2 + 1)
                            for bx, by, r2 in blobs)
                col = 0 if gx in (0, W - CELL) else 1  # faint glass edge
                for threshold, band_col in BANDS:
                    if field > threshold:
                        col = band_col
                        break
                pyxel.rect(gx, gy, CELL, CELL, col)


if __name__ == "__main__":
    App().run()
