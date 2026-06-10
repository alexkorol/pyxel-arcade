"""Terrarium -- a glass jar of tiny leaf-headed creatures ("pips").

Red pips trot, gold pips hop, blue pips float. Click to drop a berry;
fed pips lay eggs. At night the walkers curl up and sleep while the
blue pips glow like fireflies.

Controls:  click = drop a berry

Study: per-creature state machines, a day/night clock driven by
frame_count, simple particle effects, layered scene drawing.
"""
import math
import random

import pyxel

W = H = 128
GROUND = 104
DAY_LEN = 1800          # frames per full day (60 s at 30 fps)
POP_CAP = 24
KINDS = {  # kind: (body color, accent color)
    "red": (8, 2), "gold": (10, 9), "blue": (12, 5),
}


class Berry:
    def __init__(self, x):
        self.x, self.y, self.vy, self.size = x, 6, 0.0, 3.0

    def update(self):
        if self.y < GROUND - 2:
            self.vy += 0.15
            self.y = min(GROUND - 2, self.y + self.vy)

    @property
    def landed(self):
        return self.y >= GROUND - 2

    def draw(self):
        r = max(1, int(self.size))
        pyxel.circ(self.x, self.y, r, 8)
        pyxel.pset(self.x - 1, self.y - 1, 14)
        pyxel.pset(self.x, self.y - r - 1, 3)  # little stem


class Egg:
    def __init__(self, x, kind):
        self.x, self.kind, self.timer = x, kind, 360

    def update(self):
        self.timer -= 1

    def draw(self):
        wob = self.timer < 60 and (self.timer // 4) % 2  # wobble pre-hatch
        pyxel.circ(self.x + (1 if wob else 0), GROUND - 1, 1, 7)
        pyxel.pset(self.x, GROUND - 2, 7)


class Pip:
    def __init__(self, x, kind):
        self.x, self.y = x, float(GROUND - 1)
        self.kind = kind
        self.col, self.dark = KINDS[kind]
        self.vx = random.choice((-0.5, 0.5))
        self.vy = 0.0
        self.fed = 0.0
        self.hop_t = random.randint(10, 40)
        self.blink = random.randint(60, 240)
        self.phase = random.uniform(0, math.tau)
        self.state = "wander"

    # -- brains ---------------------------------------------------------
    def update(self, app):
        self.blink -= 1
        if self.blink < -4:
            self.blink = random.randint(60, 240)

        target = self.nearest_berry(app.berries)
        if app.night and self.kind != "blue":
            self.state = "sleep"
        elif target:
            self.state = "seek"
        else:
            self.state = "wander"

        if self.state == "sleep":
            self.settle()
            if random.random() < 0.01:
                app.particles.append(["z", self.x + 2, self.y - 5, 30])
            return

        getattr(self, "move_" + self.kind)(target)

        if target and abs(target.x - self.x) < 4 and abs(target.y - self.y) < 5:
            target.size -= 0.03
            self.fed += 0.03
            if random.random() < 0.04:
                app.particles.append(["heart", self.x, self.y - 5, 24])
        if self.fed >= 2.5 and len(app.pips) + len(app.eggs) < POP_CAP:
            self.fed = 0.0
            app.eggs.append(Egg(int(self.x), self.kind))

    def nearest_berry(self, berries):
        landed = [b for b in berries if b.landed]
        return min(landed, key=lambda b: abs(b.x - self.x), default=None)

    def settle(self):
        self.y = min(GROUND - 1, self.y + 0.5)

    # -- three little gaits ----------------------------------------------
    def move_red(self, target):  # trotting ground walker
        if target:
            self.vx = math.copysign(0.6, target.x - self.x)
        elif random.random() < 0.02:
            self.vx = random.choice((-0.4, 0.4, 0.0))
        self.x += self.vx
        self.y = GROUND - 1

    def move_gold(self, target):  # springy hopper
        on_ground = self.y >= GROUND - 1
        if on_ground:
            self.vy = 0
            self.hop_t -= 1
            if self.hop_t <= 0:
                self.hop_t = random.randint(20, 50)
                self.vy = -2.2
                dx = (target.x - self.x) if target else random.uniform(-30, 30)
                self.vx = max(-1.2, min(1.2, dx * 0.06))
        else:
            self.vy += 0.18
        self.x += self.vx if not on_ground else 0
        self.y = min(GROUND - 1, self.y + self.vy)

    def move_blue(self, target):  # drifting floater
        tx = target.x if target else 64 + math.sin(self.phase + pyxel.frame_count / 90) * 40
        ty = (target.y - 2) if target else GROUND - 30
        self.vx += (tx - self.x) * 0.002
        self.vy += (ty - self.y) * 0.002
        self.vx *= 0.95
        self.vy *= 0.95
        self.x += self.vx
        self.y += self.vy + math.sin(pyxel.frame_count / 10 + self.phase) * 0.2

    # -- looks -----------------------------------------------------------
    def draw(self, night):
        x, y = int(self.x), int(self.y)
        if self.state == "sleep":
            pyxel.rect(x - 1, y - 1, 4, 2, self.col)  # curled up flat
            return
        if night and self.kind == "blue" and (pyxel.frame_count // 6 + x) % 3:
            pyxel.circb(x, y - 1, 3, 10)  # firefly glow
        pyxel.rect(x - 1, y - 2, 3, 3, self.col)              # body
        sway = round(math.sin(pyxel.frame_count / 8 + self.phase))
        pyxel.pset(x, y - 3, 3)                                # leaf stem
        pyxel.pset(x + sway, y - 4, 11)                        # the leaf!
        if self.blink > 0:                                     # eye (blinks)
            ex = x + (1 if self.vx >= 0 else -1)
            pyxel.pset(ex, y - 2, 7)


class App:
    def __init__(self):
        pyxel.init(W, H, title="terrarium")
        pyxel.mouse(True)
        self.pips = [Pip(random.uniform(20, 108), k)
                     for k in ("red", "red", "gold", "gold", "blue", "blue")]
        self.berries = []
        self.eggs = []
        self.particles = []  # [kind, x, y, life]
        self.stars = [(random.randint(6, 121), random.randint(6, 60))
                      for _ in range(24)]
        self.soil = [(random.randint(4, 123), random.randint(GROUND + 2, 122))
                     for _ in range(60)]
        self.grass = [random.randint(8, 119) for _ in range(14)]

    def run(self):
        pyxel.run(self.update, self.draw)

    @property
    def phase(self):
        return (pyxel.frame_count % DAY_LEN) / DAY_LEN

    @property
    def night(self):
        return self.phase >= 0.6

    def update(self):
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and len(self.berries) < 6:
            self.berries.append(Berry(max(8, min(119, pyxel.mouse_x))))
        for b in self.berries:
            b.update()
        self.berries = [b for b in self.berries if b.size > 0.5]

        for p in self.pips:
            p.update(self)
            p.x = max(6, min(121, p.x))
            p.y = max(8, p.y)
        for e in self.eggs:
            e.update()
            if e.timer <= 0:
                self.pips.append(Pip(e.x, e.kind))
        self.eggs = [e for e in self.eggs if e.timer > 0]

        for q in self.particles:
            q[2] -= 0.3
            q[3] -= 1
        self.particles = [q for q in self.particles if q[3] > 0]

    def draw(self):
        night = self.night
        pyxel.cls(1 if night else 6)
        if night:
            for i, (x, y) in enumerate(self.stars):
                if (pyxel.frame_count // 7 + i) % 5:
                    pyxel.pset(x, y, 7)
            pyxel.circ(int(20 + self.phase * 100), 18, 5, 7)  # moon
        else:
            pyxel.circ(int(10 + self.phase * 180), 16, 6, 10)  # sun
        # soil bed and grass
        pyxel.rect(2, GROUND, 124, H - GROUND - 2, 4)
        for x, y in self.soil:
            pyxel.pset(x, y, 2)
        for i, x in enumerate(self.grass):
            sway = round(math.sin(pyxel.frame_count / 14 + i))
            pyxel.line(x, GROUND, x + sway, GROUND - 3, 3)
            pyxel.pset(x + sway, GROUND - 4, 11)

        for b in self.berries:
            b.draw()
        for e in self.eggs:
            e.draw()
        for p in self.pips:
            p.draw(night)
        for kind, x, y, life in self.particles:
            if kind == "heart":
                pyxel.pset(x, y, 14)
                pyxel.pset(x + 1, y, 14)
                pyxel.pset(x, y + 1, 14)
            else:
                pyxel.text(x, y, "z", 6)

        # the glass itself
        pyxel.rectb(0, 0, W, H, 5)
        pyxel.rectb(1, 1, W - 2, H - 2, 6)
        pyxel.line(4, 5, 4, 26, 7)   # shine
        pyxel.pset(5, 28, 7)
        pyxel.text(5, H - 8, f"{len(self.pips)} pips", 7 if night else 1)


if __name__ == "__main__":
    App().run()
