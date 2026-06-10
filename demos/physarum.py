"""Physarum -- a slime mold of 320 blind agents that sniff their own
trail chemical and, out of nothing, build veiny transport networks.

Controls:  hold click = drop food scent (the mold swarms it)
           1 / 2 / 3 = sensor presets (web / maze / dots)
           A = scatter the agents      SPACE = clear canvas

Study: perception-action loops (sense ahead, turn, move, deposit),
bytearray grids, and how rich behavior emerges from dumb rules.
"""
import math
import random

import pyxel

W = H = 128
N_AGENTS = 320
PRESETS = {  # key: (sensor angle, sensor distance, turn speed)
    pyxel.KEY_1: (0.45, 6, 0.30),
    pyxel.KEY_2: (0.90, 9, 0.55),
    pyxel.KEY_3: (0.25, 4, 0.20),
}


class Agent:
    __slots__ = ("x", "y", "a")

    def __init__(self):
        self.scatter()

    def scatter(self):
        self.x = random.uniform(0, W)
        self.y = random.uniform(0, H)
        self.a = random.uniform(0, math.tau)


class Cursor:
    """Software mouse cursor for a persistent canvas: it memorizes the
    pixels it paints over and restores them next frame, so it never
    leaves a trail (the built-in cursor gets stamped into the screen
    buffer and would)."""

    ARMS = ((-2, 0), (-1, 0), (1, 0), (2, 0), (0, -2), (0, -1), (0, 1), (0, 2))

    def __init__(self):
        self.under = []  # [(x, y, color), ...] saved last frame

    def erase(self):
        for x, y, c in self.under:
            pyxel.pset(x, y, c)
        self.under = []

    def draw(self):
        self.under = []
        for dx, dy in self.ARMS:
            x, y = pyxel.mouse_x + dx, pyxel.mouse_y + dy
            if 0 <= x < pyxel.width and 0 <= y < pyxel.height:
                self.under.append((x, y, pyxel.pget(x, y)))
                pyxel.pset(x, y, 7)


class App:
    def __init__(self):
        pyxel.init(W, H, title="physarum")
        pyxel.mouse(False)  # see Cursor: the engine cursor would smear
        self.cursor = Cursor()
        self.trail = bytearray(W * H)
        self.agents = [Agent() for _ in range(N_AGENTS)]
        self.sense_angle, self.sense_dist, self.turn = PRESETS[pyxel.KEY_1]
        self.wipe = True

    def run(self):
        pyxel.run(self.update, self.draw)

    def sniff(self, x, y, a):
        sx = int(x + math.cos(a) * self.sense_dist) % W
        sy = int(y + math.sin(a) * self.sense_dist) % H
        return self.trail[sx + sy * W]

    def update(self):
        for key, preset in PRESETS.items():
            if pyxel.btnp(key):
                self.sense_angle, self.sense_dist, self.turn = preset
        if pyxel.btnp(pyxel.KEY_A):
            for ag in self.agents:
                ag.scatter()
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.wipe = True
        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):  # squirt food scent
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            for _ in range(40):
                x = (mx + random.randint(-5, 5)) % W
                y = (my + random.randint(-5, 5)) % H
                i = x + y * W
                self.trail[i] = min(255, self.trail[i] + 120)

        # the whole trail field evaporates a little each frame
        self.trail = bytearray((v * 15) >> 4 for v in self.trail)

        t = self.trail
        for ag in self.agents:
            # sense ahead-left, ahead, ahead-right
            left = self.sniff(ag.x, ag.y, ag.a - self.sense_angle)
            fwd = self.sniff(ag.x, ag.y, ag.a)
            right = self.sniff(ag.x, ag.y, ag.a + self.sense_angle)
            if fwd >= left and fwd >= right:
                pass  # stay the course
            elif left > right:
                ag.a -= self.turn
            elif right > left:
                ag.a += self.turn
            else:
                ag.a += random.choice((-1, 1)) * self.turn
            ag.a += random.uniform(-0.08, 0.08)
            ag.x = (ag.x + math.cos(ag.a)) % W
            ag.y = (ag.y + math.sin(ag.a)) % H
            i = int(ag.x) + int(ag.y) * W
            t[i] = min(255, t[i] + 45)  # deposit chemical

    def draw(self):
        self.cursor.erase()
        if self.wipe:
            pyxel.cls(0)
            self.wipe = False
        for _ in range(120):  # stochastic fade of the painted canvas
            pyxel.pset(random.randrange(W), random.randrange(H), 0)
        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            pyxel.circ(pyxel.mouse_x, pyxel.mouse_y, 2, 2)  # food stain
        for ag in self.agents:
            v = self.trail[int(ag.x) + int(ag.y) * W]
            col = 7 if v > 200 else 11 if v > 120 else 3 if v > 50 else 1
            pyxel.pset(ag.x, ag.y, col)
        self.cursor.draw()


if __name__ == "__main__":
    App().run()
