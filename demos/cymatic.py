"""Cymatic -- a playable Chladni plate. Sand drains onto the nodal lines
of a vibrating square plate, drawing the standing-wave figure of the
current (m, n) resonance mode. Tune the mode and the sand redraws itself.

Controls:  drag = tune mode    (-> tunes m, down tunes n)
           right-drag = pour fresh sand under the cursor
           arrows = fine tune   SPACE = shuffle a random mode
           P = step through presets   S = toggle sound

Study: the (m,n)/(n,m) eigenmodes of a square plate are degenerate, so the
plate rings in a superposition with a slowly drifting mixing sign s:

    a(x,y) = cos(n pi x)cos(m pi y) + s * cos(m pi x)cos(n pi y)

Grains random-walk hardest where |a| is large and descend the analytic
gradient of a^2, so they pool on the nodes (a = 0) -- exactly like sand on
a bowed plate. To stay pure-Python-fast (the web launcher has no NumPy) the
four cos/sin terms are read from per-frame lookup tables instead of calling
trig 8x per grain: a(x,y) only depends on x and y, quantized to R levels.
"""
import math
import random

import pyxel

W = H = 128
PLATE = 98
OX = (W - PLATE) // 2
OY = 11                       # header band above the plate
FPS = 30
N = 1600                      # sand grains (pure-Python budget)
R = 256                       # cos/sin lookup-table resolution

# settled sand (on the nodes) glows warm amber; shaken sand cools to violet
COLS = [10, 9, 4, 5, 1]

PRESETS = [(1, 2), (2, 3), (1, 4), (3, 5), (2, 5),
           (4, 5), (3, 7), (5, 6), (6, 7), (5, 8)]
NAMES = "c c# d d# e f f# g g# a a# b".split()


def clamp(v, a, b):
    return a if v < a else b if v > b else v


class App:
    def __init__(self):
        pyxel.init(W, H, title="Cymatic", fps=FPS)
        pyxel.mouse(True)
        self.px = [random.random() for _ in range(N)]
        self.py = [random.random() for _ in range(N)]
        self.vb = [0.0] * N                       # local amplitude per grain
        # per-frame lookup tables for cos/sin(n pi x), cos/sin(m pi x)
        self.cos_n = [0.0] * R
        self.cos_m = [0.0] * R
        self.sin_n = [0.0] * R
        self.sin_m = [0.0] * R

        self.m = self.tm = 3.0
        self.n = self.tn = 5.0
        self.s_ph = random.random() * math.tau
        self.s = -1.0
        self.agitation = 0.0
        self.preset_i = 0
        self.interacted = False
        self.recycle_acc = 0.0

        self.sound = True
        self.dragging = False
        self.lx = self.ly = 0
        self.flash = 0                            # frames of border flash
        self.pm_i, self.pn_i = round(self.m), round(self.n)
        pyxel.sounds[0].set("c2", "s", "5", "n", 12)   # mode blip
        pyxel.sounds[1].set("g3", "p", "3", "f", 4)    # detent tick

    def run(self):
        pyxel.run(self.update, self.draw)

    def plate_freq(self):
        return 60.0 * (self.m * self.m + self.n * self.n) ** 0.62

    def blip(self):
        if not self.sound:
            return
        # map plate frequency onto a 4-octave chiptune scale
        semi = clamp(int(12 * math.log2(self.plate_freq() / 70.0)), 0, 47)
        note = NAMES[semi % 12] + str(1 + semi // 12)
        pyxel.sounds[0].set(note, "s", "5", "n", 12)
        pyxel.play(0, 0)

    def shuffle(self):
        a = b = 1
        while a == b:                     # m == n is silent (pattern vanishes)
            a, b = 1 + random.randrange(8), 1 + random.randrange(8)
        self.tm, self.tn = a, b
        self.s_ph = random.random() * math.tau
        self.agitation = min(self.agitation + 1.0, 1.4)
        self.interacted = True
        self.flash = 8
        self.blip()

    def preset(self, i):
        self.preset_i = i % len(PRESETS)
        self.tm, self.tn = PRESETS[self.preset_i]
        self.agitation = min(self.agitation + 0.8, 1.4)
        self.interacted = True
        self.flash = 8
        self.blip()

    # ---------------- input ----------------
    def handle_input(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.shuffle()
        if pyxel.btnp(pyxel.KEY_P):
            self.preset(self.preset_i + 1)
        if pyxel.btnp(pyxel.KEY_S):
            self.sound = not self.sound
            if self.sound:
                self.blip()

        step = 0.24
        keyed = False
        if pyxel.btn(pyxel.KEY_RIGHT):
            self.tm = clamp(self.tm + step, 1, 8); keyed = True
        if pyxel.btn(pyxel.KEY_LEFT):
            self.tm = clamp(self.tm - step, 1, 8); keyed = True
        if pyxel.btn(pyxel.KEY_DOWN):
            self.tn = clamp(self.tn + step, 1, 8); keyed = True
        if pyxel.btn(pyxel.KEY_UP):
            self.tn = clamp(self.tn - step, 1, 8); keyed = True
        if keyed:
            self.interacted = True
            self.agitation = min(self.agitation + 0.05, 1.4)

        # drag anywhere: right tunes m, down tunes n
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.dragging = True
            self.lx, self.ly = pyxel.mouse_x, pyxel.mouse_y
            self.interacted = True
        if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            self.dragging = False
        if self.dragging:
            dx = (pyxel.mouse_x - self.lx) / PLATE
            dy = (pyxel.mouse_y - self.ly) / PLATE
            self.lx, self.ly = pyxel.mouse_x, pyxel.mouse_y
            self.tm = clamp(self.tm + dx * 6.0, 1, 8)
            self.tn = clamp(self.tn + dy * 6.0, 1, 8)
            self.agitation = min(self.agitation + (abs(dx) + abs(dy)) * 8, 1.4)

        # right-drag: pour a stream of fresh sand under the cursor
        if pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT):
            ux = (pyxel.mouse_x - OX) / PLATE
            uy = (pyxel.mouse_y - OY) / PLATE
            if 0.0 <= ux <= 1.0 and 0.0 <= uy <= 1.0:
                self.interacted = True
                px, py = self.px, self.py
                for _ in range(30):
                    k = random.randrange(N)
                    px[k] = clamp(ux + random.gauss(0, 0.03), 0.0, 1.0)
                    py[k] = clamp(uy + random.gauss(0, 0.03), 0.0, 1.0)

    def idle_drift(self):
        if self.interacted:
            return
        t = pyxel.frame_count / FPS
        self.tm = 3.5 + 2.4 * math.sin(t * 0.11)
        self.tn = 4.5 + 2.4 * math.sin(t * 0.073 + 2.1)

    # ---------------- simulation ----------------
    def update(self):
        self.handle_input()
        self.idle_drift()

        # glide toward the target mode; drift the degeneracy-mixing sign
        self.m += (self.tm - self.m) * 0.09
        self.n += (self.tn - self.n) * 0.09
        self.s_ph += 0.005
        self.s = math.sin(self.s_ph)

        # detent ticks: the dial clicks as the mode crosses each integer
        mi, ni = round(self.m), round(self.n)
        if (mi, ni) != (self.pm_i, self.pn_i):
            self.pm_i, self.pn_i = mi, ni
            if self.sound and self.interacted:
                pyxel.play(1, 1)

        # rebuild the cos/sin lookup tables for this frame's mode
        nPI, mPI, s = self.n * math.pi, self.m * math.pi, self.s
        cos_n, cos_m = self.cos_n, self.cos_m
        sin_n, sin_m = self.sin_n, self.sin_m
        inv = 1.0 / R
        for i in range(R):
            xc = i * inv
            cos_n[i] = math.cos(nPI * xc)
            sin_n[i] = math.sin(nPI * xc)
            cos_m[i] = math.cos(mPI * xc)
            sin_m[i] = math.sin(mPI * xc)

        shake = 0.0058 + self.agitation * 0.02
        lr, cap, floor = 0.00028, 0.0042, 0.05
        px, py, vb = self.px, self.py, self.vb
        rnd = random.random
        Rm1 = R - 1

        # fresh sand trickle so no node line hoards grains across mode changes
        self.recycle_acc += N * 0.00004
        while self.recycle_acc >= 1.0:
            k = random.randrange(N)
            px[k] = rnd(); py[k] = rnd()
            self.recycle_acc -= 1.0

        for i in range(N):
            x = px[i]; y = py[i]
            ix = int(x * R); ix = ix if ix < R else Rm1
            iy = int(y * R); iy = iy if iy < R else Rm1
            cnx = cos_n[ix]; cmx = cos_m[ix]
            cny = cos_n[iy]; cmy = cos_m[iy]
            a = cnx * cmy + s * cmx * cny             # |a| <= 2

            # analytic gradient of a -> descend a^2 onto the nodal lines
            dax = -nPI * sin_n[ix] * cmy - s * mPI * sin_m[ix] * cny
            day = -mPI * cnx * sin_m[iy] - s * nPI * cmx * sin_n[iy]
            gx = -lr * a * dax
            if gx > cap: gx = cap
            elif gx < -cap: gx = -cap
            gy = -lr * a * day
            if gy > cap: gy = cap
            elif gy < -cap: gy = -cap

            v = (a if a >= 0 else -a) * 0.5           # 0..1 shake strength
            j = shake * (v + floor)
            nx = x + gx + (rnd() - 0.5) * j
            ny = y + gy + (rnd() - 0.5) * j

            # reflect at the rim
            if nx < 0: nx = -nx
            elif nx > 1: nx = 2 - nx
            if ny < 0: ny = -ny
            elif ny > 1: ny = 2 - ny
            px[i] = 0.0 if nx < 0 else 1.0 if nx > 1 else nx
            py[i] = 0.0 if ny < 0 else 1.0 if ny > 1 else ny
            vb[i] = v

        self.agitation *= 0.92

    # ---------------- render ----------------
    def draw(self):
        pyxel.cls(0)

        # hard tuning rattles the whole plate a pixel or two
        jx = jy = 0
        if self.agitation > 0.35:
            jx, jy = pyxel.rndi(-1, 1), pyxel.rndi(-1, 1)
        if self.flash > 0:
            self.flash -= 1

        border = 10 if self.flash > 4 else 9 if self.flash > 0 else 1
        pyxel.rectb(OX + jx - 1, OY + jy - 1, PLATE + 2, PLATE + 2, border)
        # amber corner brackets give it an instrument-panel look
        bracket = 9 if border == 1 else 10
        for cx in (OX - 1, OX + PLATE):
            for cy in (OY - 1, OY + PLATE):
                pyxel.pset(cx + jx, cy + jy, bracket)

        px, py, vb = self.px, self.py, self.vb
        pset = pyxel.pset
        rnd = random.random
        ox, oy = OX + jx, OY + jy
        for i in range(N):
            v = vb[i]
            b = int(v * 5)
            c = COLS[b] if b < 5 else 1
            # settled grains twinkle: a few flash white each frame
            if v < 0.08 and rnd() < 0.02:
                c = 7
            pset(int(ox + px[i] * PLATE), int(oy + py[i] * PLATE), c)

        pyxel.text(2, 2, "CYMATIC", 10)
        pyxel.text(52, 2, "chladni plate", 5)
        # readout locks white when the plate sits on a pure integer mode
        locked = (abs(self.m - self.pm_i) < 0.07 and abs(self.n - self.pn_i) < 0.07
                  and self.pm_i != self.pn_i)
        by = OY + PLATE + 3
        pyxel.text(2, by, "m%.1f n%.1f" % (self.m, self.n), 7 if locked else 10)
        pyxel.text(64, by, "%d Hz" % self.plate_freq(), 9)
        pyxel.text(107, by, "S:%s" % ("on" if self.sound else "--"), 4)
        hint = ("drag/arrows tune   SPACE shuffle"
                if (pyxel.frame_count // 240) % 2 == 0
                else "P preset  S sound  R-drag pours")
        pyxel.text(2, by + 8, hint, 4)


if __name__ == "__main__":
    App().run()
