"""Oculus Garden -- a moonlit bed of eye-stalks that watch your cursor.

They sway, they track, they blink. Stare at one too long and it gets
shy. Click the soil to sprout a new stalk; click the sky and every
eye in the garden blinks at once.

Controls:  move mouse = be watched     click soil = grow a stalk
           click sky = synchronized blink

Study: kinematic chains (stacked segment angles), vector clamping
for the iris, tiny state machines for blinking and shyness.
"""
import math
import random

import pyxel

W = H = 128
SOIL = 112
MAX_STALKS = 12
IRIS_COLS = (8, 9, 10, 12, 14, 2)


class Stalk:
    def __init__(self, x):
        self.base = x
        self.segs = random.randint(3, 5)
        self.seglen = random.uniform(7, 10)
        self.eye_r = random.randint(3, 5)
        self.iris = random.choice(IRIS_COLS)
        self.phase = random.uniform(0, math.tau)
        self.grow = 0.0          # 0 -> 1 sprouting animation
        self.blink_t = 0         # >0 while a blink is playing out
        self.next_blink = random.randint(90, 300)
        self.stare = 0           # frames the cursor has hovered on the eye

    def points(self):
        """Walk up the chain of segments, accumulating sway and lean."""
        t = pyxel.frame_count / 30
        lean = max(-0.3, min(0.3, (pyxel.mouse_x - self.base) / 200))
        x, y = float(self.base), float(SOIL)
        pts = [(x, y)]
        angle = -math.pi / 2
        for i in range(self.segs):
            angle += math.sin(t * 0.9 + self.phase + i) * 0.1 + lean / self.segs
            x += math.cos(angle) * self.seglen * self.grow
            y += math.sin(angle) * self.seglen * self.grow
            pts.append((x, y))
        return pts

    def update(self):
        self.grow = min(1.0, self.grow + 0.02)
        self.next_blink -= 1
        if self.next_blink <= 0:
            self.start_blink()
        if self.blink_t > 0:
            self.blink_t -= 1

        ex, ey = self.points()[-1]
        d = math.hypot(pyxel.mouse_x - ex, pyxel.mouse_y - ey)
        self.stare = self.stare + 1 if d < self.eye_r + 4 else max(0, self.stare - 3)

    def start_blink(self):
        self.blink_t = 10
        self.next_blink = random.randint(90, 300)

    def draw(self):
        pts = self.points()
        for i, ((x1, y1), (x2, y2)) in enumerate(zip(pts, pts[1:])):
            pyxel.line(x1, y1, x2, y2, 3)
            if i % 2:  # a little leaf at every other joint
                pyxel.pset(x2 + (1 if i % 4 else -1), y2, 11)
        ex, ey = pts[-1]
        r = self.eye_r

        pyxel.circ(ex, ey, r, 7)                       # sclera
        dx, dy = pyxel.mouse_x - ex, pyxel.mouse_y - ey
        d = math.hypot(dx, dy) or 1
        reach = min(d, r - 2)                          # clamp iris in eye
        ix, iy = ex + dx / d * reach, ey + dy / d * reach
        pyxel.circ(ix, iy, 2, self.iris)
        pyxel.circ(ix, iy, 1 + (d < 25), 0)            # pupil dilates up close

        # eyelid: blink animation, or held shut while feeling shy
        lid = 1.0 if self.stare > 60 else \
            (10 - abs(self.blink_t - 5)) / 5 if self.blink_t > 0 else 0.0
        if lid > 0:
            h = int((2 * r + 1) * min(1.0, lid))
            pyxel.rect(ex - r, ey - r, 2 * r + 1, h, 15)
        pyxel.circb(ex, ey, r, 2)                      # rim


class App:
    def __init__(self):
        pyxel.init(W, H, title="oculus garden")
        pyxel.mouse(True)
        self.stalks = [Stalk(x) for x in (18, 40, 64, 88, 110)]
        for s in self.stalks:
            s.grow = 1.0
        self.spores = [[random.uniform(0, W), random.uniform(0, H),
                        random.uniform(0.1, 0.4)] for _ in range(20)]

    def run(self):
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if pyxel.mouse_y > SOIL - 6 and len(self.stalks) < MAX_STALKS:
                self.stalks.append(Stalk(pyxel.mouse_x))
            else:
                for s in self.stalks:  # the garden blinks back
                    s.start_blink()
        for s in self.stalks:
            s.update()
        for sp in self.spores:  # dust motes drift upward forever
            sp[1] -= sp[2]
            sp[0] += math.sin(pyxel.frame_count / 40 + sp[1]) * 0.2
            if sp[1] < -2:
                sp[0], sp[1] = random.uniform(0, W), H + 2

    def draw(self):
        pyxel.cls(1)
        pyxel.circ(102, 20, 8, 7)        # moon
        pyxel.circ(99, 18, 2, 6)
        pyxel.pset(105, 23, 6)
        for x, y, _ in self.spores:
            pyxel.pset(x, y, 13)
        pyxel.rect(0, SOIL, W, H - SOIL, 2)      # soil mound
        for i in range(0, W, 7):
            pyxel.pset(i + (i // 7) % 3, SOIL + 3 + (i % 9), 0)
        for s in self.stalks:
            s.draw()


if __name__ == "__main__":
    App().run()
