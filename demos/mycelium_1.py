"""Mycelium (prototype 1) -- the first sketch that grew into
color_mycelium.py and mycelium_garden.py. Kept for the study value:
compare its raw random-walk hyphae with the steered, budgeted tips
of its descendants.

Controls:  click = plant a new tip    SPACE = clear canvas
"""
import math
import random

import pyxel

W = H = 128
MAX_TIPS = 200


class Nutrient:
    def __init__(self, x, y, amount):
        self.x = x
        self.y = y
        self.amount = amount


class HyphalTip:
    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.px = x
        self.py = y
        self.dx = dx
        self.dy = dy

    def grow(self, speed):
        self.px, self.py = self.x, self.y
        self.x += self.dx * speed
        self.y += self.dy * speed

    def branch(self):
        angle = random.uniform(-math.pi, math.pi)
        return HyphalTip(self.x, self.y,
                         self.dx + math.cos(angle), self.dy + math.sin(angle))

    def change_direction(self, persistence):
        angle = random.uniform(-math.pi, math.pi)
        self.dx = self.dx * persistence + math.cos(angle) * (1 - persistence)
        self.dy = self.dy * persistence + math.sin(angle) * (1 - persistence)

    @property
    def alive(self):
        return 0 <= self.x < W and 0 <= self.y < H


class Mycelium:
    def __init__(self):
        self.tips = [HyphalTip(64, 64, 1, 0)]
        self.branching_probability = 0.05
        self.growth_speed = 0.5
        self.persistence = 0.75
        self.death_probability = 0.002

    def grow(self):
        babies = []
        survivors = []
        for tip in self.tips:
            tip.grow(self.growth_speed)
            if random.random() < self.branching_probability and \
                    len(self.tips) + len(babies) < MAX_TIPS:
                babies.append(tip.branch())
            tip.change_direction(self.persistence)
            if tip.alive and random.random() >= self.death_probability:
                survivors.append(tip)
        self.tips = survivors + babies
        if not self.tips:  # the colony died out -- replant the middle
            self.tips = [HyphalTip(64, 64, 1, 0)]


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
        pyxel.init(128, 128, title="mycelium 1")
        pyxel.mouse(False)  # see Cursor: the engine cursor would smear
        self.cursor = Cursor()
        self.mycelium = Mycelium()
        self.nutrients = [Nutrient(random.randint(0, 127), random.randint(0, 127), 10)
                          for _ in range(100)]
        self.wipe = True
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.wipe = True
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and len(self.mycelium.tips) < MAX_TIPS:
            self.mycelium.tips.append(
                HyphalTip(pyxel.mouse_x, pyxel.mouse_y, 1, 0))
        self.mycelium.grow()

    def draw(self):
        # persistent canvas: trails accumulate on screen instead of being
        # replayed from ever-growing point lists (the original sketch
        # slowed to a crawl within minutes)
        self.cursor.erase()
        if self.wipe:
            pyxel.cls(0)
            self.wipe = False
            for nutrient in self.nutrients:
                pyxel.pset(nutrient.x, nutrient.y, 4)
        for tip in self.mycelium.tips:
            pyxel.line(tip.px, tip.py, tip.x, tip.y, 6)
            pyxel.pset(tip.x, tip.y, 7)
        self.cursor.draw()


App()
