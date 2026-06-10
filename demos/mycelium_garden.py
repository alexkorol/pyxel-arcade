"""Mycelium Garden -- hyphae forage for food, fatten up, and fruit
into mushrooms that puff spores and start the cycle again.

Controls:  click = drop a nutrient    R = replant the garden

Study: steering toward a target angle (the wrap-around trick in
Tip.step), a tiny energy economy, dataclasses, emergent lifecycles.
"""
import math
import random
from dataclasses import dataclass

import pyxel

W = H = 128
MAX_TIPS = 220
MAX_FOOD = 18


@dataclass
class Nutrient:
    x: float
    y: float
    amount: float = 10.0


class Tip:
    def __init__(self, x, y, angle, energy=60.0):
        self.x, self.y = x, y
        self.px, self.py = x, y
        self.angle = angle
        self.energy = energy

    def step(self, food):
        self.px, self.py = self.x, self.y

        # chemotaxis: lean toward the juiciest nearby nutrient
        best, pull = None, 0.0
        for n in food:
            d2 = (n.x - self.x) ** 2 + (n.y - self.y) ** 2
            if d2 < 40 ** 2:
                w = n.amount / (d2 + 20)
                if w > pull:
                    best, pull = n, w
        if best:
            target = math.atan2(best.y - self.y, best.x - self.x)
            # shortest signed angle difference, wrapped into [-pi, pi]
            diff = (target - self.angle + math.pi) % math.tau - math.pi
            self.angle += diff * 0.15

        self.angle += random.uniform(-0.25, 0.25)
        self.x += math.cos(self.angle) * 0.8
        self.y += math.sin(self.angle) * 0.8
        self.energy -= 0.35

        if best and (best.x - self.x) ** 2 + (best.y - self.y) ** 2 < 9:
            bite = min(0.5, best.amount)
            best.amount -= bite
            self.energy += bite * 14

    @property
    def alive(self):
        return self.energy > 0 and 0 <= self.x < W and 0 <= self.y < H


class Mushroom:
    def __init__(self, x, y):
        self.x, self.y, self.age = x, y, 0

    def step(self):
        """Grow; return True on the single frame the cap puffs spores."""
        self.age += 1
        return self.age == 90

    def draw(self):
        h = min(self.age // 12, 7)            # stem height
        r = min(self.age // 18, 4)            # cap radius
        pyxel.line(self.x, self.y, self.x, self.y - h, 7)
        if r:
            pyxel.circ(self.x, self.y - h, r, 8)
            pyxel.pset(self.x - 1, self.y - h - 1, 7)
            pyxel.pset(self.x + 1, self.y - h, 7)


class App:
    def __init__(self):
        pyxel.init(W, H, title="mycelium garden")
        pyxel.mouse(True)
        self.reset()

    def run(self):
        pyxel.run(self.update, self.draw)

    def reset(self):
        self.wipe = True
        self.tips = [Tip(64, 64, a * math.tau / 4) for a in range(4)]
        self.food = [Nutrient(random.uniform(8, 120), random.uniform(8, 120))
                     for _ in range(14)]
        self.shrooms = []
        self.spores = []  # each spore is a [x, y, vx, vy, life] list

    def update(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.reset()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and len(self.food) < MAX_FOOD:
            self.food.append(Nutrient(pyxel.mouse_x, pyxel.mouse_y))
        if pyxel.frame_count % 120 == 0 and len(self.food) < MAX_FOOD:
            self.food.append(Nutrient(random.uniform(8, 120), random.uniform(8, 120)))

        # grow tips; well-fed tips branch, splitting their energy
        babies = []
        for t in self.tips:
            t.step(self.food)
            if t.energy > 90 and len(self.tips) + len(babies) < MAX_TIPS \
                    and random.random() < 0.05:
                fork = t.angle + random.choice((-1, 1)) * random.uniform(0.4, 0.8)
                babies.append(Tip(t.x, t.y, fork, t.energy * 0.45))
                t.energy *= 0.55
        self.tips = [t for t in self.tips if t.alive] + babies
        self.food = [n for n in self.food if n.amount > 0.4]

        # very well-fed tips occasionally fruit into a mushroom
        if len(self.shrooms) < 6 and random.random() < 0.03:
            fat = [t for t in self.tips if t.energy > 110]
            if fat:
                t = random.choice(fat)
                self.shrooms.append(Mushroom(int(t.x), int(t.y)))
                t.energy = 40
        for m in self.shrooms:
            if m.step():  # puff! release drifting spores
                self.spores += [[m.x, m.y - 8, random.uniform(-0.6, 0.6),
                                 random.uniform(-0.5, -0.1), random.randint(40, 90)]
                                for _ in range(8)]
        self.shrooms = [m for m in self.shrooms if m.age < 240]

        # spores drift, then land and germinate into new tips
        for s in self.spores:
            s[0] += s[2] + random.uniform(-0.2, 0.2)
            s[1] += s[3]
            s[3] += 0.01  # gentle gravity wins eventually
            s[4] -= 1
            if s[4] <= 0 and 0 < s[0] < W and 0 < s[1] < H \
                    and len(self.tips) < MAX_TIPS:
                self.tips.append(Tip(s[0], s[1], random.uniform(0, math.tau)))
        self.spores = [s for s in self.spores if s[4] > 0]

        if not self.tips and not self.spores:
            self.reset()

    def draw(self):
        if self.wipe:
            pyxel.cls(0)
            self.wipe = False
        # the hyphal web accumulates on a persistent canvas;
        # vein color shows how well-fed each thread was
        for t in self.tips:
            col = 11 if t.energy > 80 else 3 if t.energy > 40 else 1
            pyxel.line(t.px, t.py, t.x, t.y, col)
            pyxel.pset(t.x, t.y, 7)
        for n in self.food:
            r = max(1, int(n.amount / 4))
            pyxel.circb(n.x, n.y, r + 1, 4)
            pyxel.circ(n.x, n.y, r, 9)
        for m in self.shrooms:
            m.draw()
        for x, y, *_ in self.spores:
            pyxel.pset(x, y, 14)


if __name__ == "__main__":
    App().run()
