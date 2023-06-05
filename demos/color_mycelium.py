import pyxel
import math
import random

class GrowingPoint:
    speed = 0.07

    def __init__(self, x, y, angle=0):
        self.x = x
        self.y = y
        self.angle = angle
        self.curve = random.uniform(-0.1, 0.1)
        self.prob_turn = 0.0005
        self.lifetime = random.randint(100, 600)
        self.colour = random.randint(0, 15)
        self.trail = [(x, y)]  # record trail

    def move(self):
        self.angle += self.curve

        if random.random() < self.prob_turn:
            self.curve = random.uniform(-0.1, 0.1)

        self.x = (self.x + math.sin(self.angle) * self.speed) % pyxel.width
        self.y = (self.y - math.cos(self.angle) * self.speed) % pyxel.height
        self.trail.append((self.x, self.y))

        self.lifetime -= 0.5  # slow down lifetime reduction

class App:
    def __init__(self):
        pyxel.init(128, 128)
        self.growing_points = [GrowingPoint(pyxel.width / 2, pyxel.height / 2, math.pi / 4)]
        self.prob_split = 0.01  # increased branching probability
        pyxel.run(self.update, self.draw)

    def update(self):
        for g in self.growing_points[:]:
            if random.random() < self.prob_split and g.lifetime > 10:
                new_growth = GrowingPoint(g.x, g.y, g.angle + math.pi / 4)
                new_growth.curve = - g.curve
                new_growth.colour = (new_growth.colour + 1) % 16
                self.growing_points.append(new_growth)
                g.angle -= math.pi / 4

            g.move()
            if g.lifetime <= 0:
                self.growing_points.remove(g)

    def draw(self):
        pyxel.cls(0)
        for g in self.growing_points:
            for x, y in g.trail:
                if 0 <= x < pyxel.width and 0 <= y < pyxel.height:
                    pyxel.pset(x, y, g.colour)


App()