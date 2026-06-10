"""Koi Pond -- a quiet top-down pond. Four koi drift as flexing chains
of circles, nosing toward whatever disturbs the water.

Controls:  click = tap the water (ripple draws the fish)
           (rain drips fall on their own now and then)

Study: segment-following chains (each link chases the one ahead --
instant fish skeleton), eased steering with the signed-angle trick,
and draw ordering as cheap depth (pads paint over fish).
"""
import math
import random

import pyxel

W = H = 160
TAU = math.tau

# (body color, patch color) pairs -- classic kohaku-ish palettes
SKINS = [(7, 8), (7, 9), (9, 7), (15, 8)]


def shortest_turn(current, target):
    """Signed smallest angle from current to target, in (-pi, pi]."""
    return (target - current + math.pi) % TAU - math.pi


class Ripple:
    def __init__(self, x, y, big=True):
        self.x, self.y = x, y
        self.r = 1.0
        self.max = random.uniform(18, 30) if big else random.uniform(7, 12)
        self.big = big  # big ripples attract koi, drips are decor

    def update(self):
        self.r += 0.55

    @property
    def alive(self):
        return self.r < self.max

    def draw(self):
        fade = self.r / self.max  # 0 fresh -> 1 gone
        col = 7 if fade < 0.4 else 6 if fade < 0.75 else 5
        pyxel.circb(self.x, self.y, int(self.r), col)


class Koi:
    N_SEG = 9
    GAP = 3.2  # distance between spine joints

    def __init__(self):
        x, y = random.uniform(20, W - 20), random.uniform(20, H - 20)
        self.angle = random.uniform(0, TAU)
        self.speed = random.uniform(0.55, 0.8)
        self.spine = [[x, y] for _ in range(self.N_SEG)]
        self.body, self.patch = random.choice(SKINS)
        # each koi gets its own patch pattern: which segments are patched
        self.patched = {i for i in range(1, self.N_SEG - 1) if random.random() < 0.4}
        self.wander = random.uniform(-0.02, 0.02)
        self.turn_timer = random.randint(40, 140)

    def update(self, ripples):
        # -- choose a heading: nearest fresh big ripple, else wander
        target = None
        best = 1e9
        hx, hy = self.spine[0]
        for rp in ripples:
            if not rp.big or rp.r > rp.max * 0.6:
                continue  # only fresh taps are interesting
            d = (rp.x - hx) ** 2 + (rp.y - hy) ** 2
            if d < best:
                best, target = d, rp

        if target:
            want = math.atan2(target.y - hy, target.x - hx)
            self.angle += shortest_turn(self.angle, want) * 0.06
        else:
            self.turn_timer -= 1
            if self.turn_timer <= 0:
                self.wander = random.uniform(-0.025, 0.025)
                self.turn_timer = random.randint(40, 140)
            self.angle += self.wander

        # -- soft wall avoidance: steer toward pond center near edges
        if not 16 < hx < W - 16 or not 16 < hy < H - 16:
            want = math.atan2(H / 2 - hy, W / 2 - hx)
            self.angle += shortest_turn(self.angle, want) * 0.08

        # -- swim: head moves, tail sways, every link chases the one ahead
        sway = math.sin(pyxel.frame_count * 0.18 + id(self) % 7) * 0.12
        a = self.angle + sway
        self.spine[0][0] += math.cos(a) * self.speed
        self.spine[0][1] += math.sin(a) * self.speed
        for i in range(1, self.N_SEG):
            px, py = self.spine[i - 1]
            sx, sy = self.spine[i]
            d = math.hypot(px - sx, py - sy) or 1e-6
            if d > self.GAP:
                pull = (d - self.GAP) / d
                self.spine[i][0] += (px - sx) * pull
                self.spine[i][1] += (py - sy) * pull

    def draw(self):
        # widths along the body: nose, fat shoulders, tapering tail
        widths = (2, 3, 4, 4, 3, 3, 2, 2, 1)
        for i in range(self.N_SEG - 1, -1, -1):  # tail first, head on top
            x, y = self.spine[i]
            col = self.patch if i in self.patched else self.body
            pyxel.circ(x, y, widths[i], col)
        # tail fin: small triangle past the last joint
        tx, ty = self.spine[-1]
        px, py = self.spine[-2]
        ang = math.atan2(ty - py, tx - px)
        f = math.sin(pyxel.frame_count * 0.25 + id(self) % 5) * 0.5
        for spread in (-0.5 + f * 0.3, 0.5 + f * 0.3):
            pyxel.line(tx, ty,
                       tx + math.cos(ang + spread) * 4,
                       ty + math.sin(ang + spread) * 4, self.body)
        # eyes
        hx, hy = self.spine[0]
        ex, ey = math.cos(self.angle + TAU / 4), math.sin(self.angle + TAU / 4)
        pyxel.pset(hx + ex * 2, hy + ey * 2, 0)
        pyxel.pset(hx - ex * 2, hy - ey * 2, 0)


class LilyPad:
    def __init__(self):
        self.x = random.uniform(15, W - 15)
        self.y = random.uniform(15, H - 15)
        self.r = random.randint(5, 9)
        self.notch = random.uniform(0, TAU)  # the classic pac-man cut
        self.drift = random.uniform(-0.05, 0.05)

    def update(self):
        self.notch += 0.002
        self.x = (self.x + self.drift * 0.1) % W

    def draw(self):
        pyxel.circ(self.x, self.y, self.r, 11)
        pyxel.circ(self.x, self.y, self.r - 2, 3)
        # cut the notch with two water-colored lines widening from center
        for da in (-0.18, 0, 0.18):
            a = self.notch + da
            pyxel.line(self.x, self.y,
                       self.x + math.cos(a) * (self.r + 1),
                       self.y + math.sin(a) * (self.r + 1), 1)


class App:
    def __init__(self):
        pyxel.init(W, H, title="Koi Pond")
        pyxel.mouse(True)
        self.koi = [Koi() for _ in range(4)]
        self.pads = [LilyPad() for _ in range(5)]
        self.ripples = []
        self.drip_timer = 90

    def run(self):
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.ripples.append(Ripple(pyxel.mouse_x, pyxel.mouse_y))

        self.drip_timer -= 1
        if self.drip_timer <= 0:  # ambient rain drip
            self.ripples.append(
                Ripple(random.uniform(10, W - 10), random.uniform(10, H - 10), big=False))
            self.drip_timer = random.randint(70, 220)

        for rp in self.ripples:
            rp.update()
        self.ripples = [rp for rp in self.ripples if rp.alive]

        for k in self.koi:
            k.update(self.ripples)
        for p in self.pads:
            p.update()

    def draw(self):
        pyxel.cls(1)  # deep water
        # caustic sparkles: a few twinkling psets keyed off frame noise
        for _ in range(14):
            x, y = random.randrange(W), random.randrange(H)
            if pyxel.noise(x * 0.06, y * 0.06, pyxel.frame_count * 0.02) > 0.42:
                pyxel.pset(x, y, 5)

        for k in self.koi:
            k.draw()
        for rp in self.ripples:
            rp.draw()
        for p in self.pads:  # pads last: fish glide UNDER them
            p.draw()


if __name__ == "__main__":
    App().run()
