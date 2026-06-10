"""Color Mycelium -- branching hyphae paint slow rainbow threads.

Controls:  click = plant a spore    SPACE = clear canvas
           C = next palette         F = toggle slow fade

Study: persistent-canvas rendering (we never call cls per frame),
list-comprehension lifecycles, polar-coordinate motion.
"""
import math
import random

import pyxel

PALETTES = [
    [1, 5, 3, 11, 10, 7],   # aurora
    [2, 8, 9, 10, 7],       # ember
    [1, 2, 14, 15, 7],      # orchid
    [5, 12, 6, 7],          # frost
]
MAX_TIPS = 350


class Tip:
    """One growing hyphal tip. It remembers where it just was (px, py)
    so draw() can connect the dots with a line."""

    def __init__(self, x, y, angle, shade=0):
        self.x, self.y = x, y
        self.px, self.py = x, y
        self.angle = angle
        self.curve = random.uniform(-0.08, 0.08)
        self.life = random.randint(120, 480)
        self.shade = shade  # index into the active palette ramp

    def step(self):
        self.px, self.py = self.x, self.y
        self.angle += self.curve + random.uniform(-0.03, 0.03)
        if random.random() < 0.01:  # occasionally pick a new curl direction
            self.curve = random.uniform(-0.08, 0.08)
        self.x = (self.x + math.cos(self.angle) * 0.7) % pyxel.width
        self.y = (self.y + math.sin(self.angle) * 0.7) % pyxel.height
        self.life -= 1


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
        pyxel.init(128, 128, title="color mycelium")
        pyxel.mouse(False)  # see Cursor: the engine cursor would smear
        self.cursor = Cursor()
        self.palette = 0
        self.fade = False
        self.wipe = True  # ask draw() to clear the canvas once
        self.tips = []
        self.seed(64, 64)

    def run(self):
        pyxel.run(self.update, self.draw)

    def seed(self, x, y):
        self.tips += [Tip(x, y, random.uniform(0, math.tau)) for _ in range(3)]

    def update(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.wipe = True
        if pyxel.btnp(pyxel.KEY_F):
            self.fade = not self.fade
        if pyxel.btnp(pyxel.KEY_C):
            self.palette = (self.palette + 1) % len(PALETTES)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.seed(pyxel.mouse_x, pyxel.mouse_y)

        babies = []
        for t in self.tips:
            t.step()
            crowded = len(self.tips) + len(babies) >= MAX_TIPS
            if t.life > 30 and not crowded and random.random() < 0.012:
                side = random.choice((-1, 1))
                fork = t.angle + side * random.uniform(0.5, 0.9)
                babies.append(Tip(t.x, t.y, fork, t.shade + 1))
                t.angle -= side * 0.25  # parent leans the other way

        self.tips = [t for t in self.tips if t.life > 0] + babies
        if not self.tips:  # the colony died out -- replant the middle
            self.seed(64, 64)

    def draw(self):
        self.cursor.erase()
        if self.wipe:
            pyxel.cls(0)
            self.wipe = False
        if self.fade:  # stochastic fade: sprinkle black pixels
            for _ in range(30):
                pyxel.pset(random.randrange(128), random.randrange(128), 0)

        ramp = PALETTES[self.palette]
        for t in self.tips:
            # skip the connecting line when the tip wrapped around an edge
            if abs(t.x - t.px) < 2 and abs(t.y - t.py) < 2:
                pyxel.line(t.px, t.py, t.x, t.y, ramp[t.shade % len(ramp)])
            pyxel.pset(t.x, t.y, 7)  # glowing growth tip
        self.cursor.draw()


if __name__ == "__main__":
    App().run()
