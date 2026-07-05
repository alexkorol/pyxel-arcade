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
a bowed plate. A trickle of re-pouring keeps the main diagonal (a node of
every mode) from hoarding grains. NumPy vectorizes the whole cloud.
"""
import math

import numpy as np
import pyxel

W = H = 128
PLATE = 98
OX = (W - PLATE) // 2
OY = 11                       # header band above the plate
N = 3000                      # sand grains

# settled sand (on the nodes) glows warm amber; shaken sand cools to violet
COLS = np.array([10, 9, 4, 5, 1], dtype=np.int32)

PRESETS = [(1, 2), (2, 3), (1, 4), (3, 5), (2, 5),
           (4, 5), (3, 7), (5, 6), (6, 7), (5, 8)]
NAMES = "c c# d d# e f f# g g# a a# b".split()


def clamp(v, a, b):
    return a if v < a else b if v > b else v


class App:
    def __init__(self):
        pyxel.init(W, H, title="Cymatic", fps=60)
        pyxel.mouse(True)
        self.px = np.random.random(N).astype(np.float32)
        self.py = np.random.random(N).astype(np.float32)
        self.v = np.zeros(N, dtype=np.float32)   # local amplitude per grain

        self.m = self.tm = 3.0
        self.n = self.tn = 5.0
        self.s_ph = np.random.random() * math.tau
        self.s = -1.0
        self.agitation = 0.0
        self.preset_i = 0
        self.interacted = False

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
            a, b = 1 + int(pyxel.rndi(0, 7)), 1 + int(pyxel.rndi(0, 7))
        self.tm, self.tn = a, b
        self.s_ph = np.random.random() * math.tau
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

        step = 0.12
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
                idx = np.random.randint(0, N, 40)
                self.px[idx] = np.clip(
                    ux + np.random.normal(0, 0.03, 40), 0, 1).astype(np.float32)
                self.py[idx] = np.clip(
                    uy + np.random.normal(0, 0.03, 40), 0, 1).astype(np.float32)

    def idle_drift(self):
        if self.interacted:
            return
        t = pyxel.frame_count / 60.0
        self.tm = 3.5 + 2.4 * math.sin(t * 0.11)
        self.tn = 4.5 + 2.4 * math.sin(t * 0.073 + 2.1)

    # ---------------- simulation ----------------
    def update(self):
        self.handle_input()
        self.idle_drift()

        # glide toward the target mode; drift the degeneracy-mixing sign
        self.m += (self.tm - self.m) * 0.06
        self.n += (self.tn - self.n) * 0.06
        self.s_ph += 0.0025
        self.s = math.sin(self.s_ph)

        # detent ticks: the dial clicks as the mode crosses each integer
        mi, ni = round(self.m), round(self.n)
        if (mi, ni) != (self.pm_i, self.pn_i):
            self.pm_i, self.pn_i = mi, ni
            if self.sound and self.interacted:
                pyxel.play(1, 1)

        shake = 0.0058 + self.agitation * 0.02
        lr, cap, floor, recycle = 0.00028, 0.0042, 0.05, 0.00004
        nPI, mPI, s = self.n * math.pi, self.m * math.pi, self.s
        px, py = self.px, self.py

        # fresh sand trickle so no node line hoards grains across mode changes
        m_recycle = np.random.random(N) < recycle
        k = int(m_recycle.sum())
        if k:
            px[m_recycle] = np.random.random(k).astype(np.float32)
            py[m_recycle] = np.random.random(k).astype(np.float32)

        cnx, cmx = np.cos(nPI * px), np.cos(mPI * px)
        cny, cmy = np.cos(nPI * py), np.cos(mPI * py)
        a = cnx * cmy + s * cmx * cny                       # |a| <= 2

        # analytic gradient of a -> descend a^2 onto the nodal lines
        dax = -nPI * np.sin(nPI * px) * cmy - s * mPI * np.sin(mPI * px) * cny
        day = -mPI * cnx * np.sin(mPI * py) - s * nPI * cmx * np.sin(nPI * py)
        gx = np.clip(-lr * a * dax, -cap, cap)
        gy = np.clip(-lr * a * day, -cap, cap)

        v = np.abs(a) * 0.5                                  # 0..1 shake strength
        j = shake * (v + floor)
        nx = px + gx + (np.random.random(N).astype(np.float32) - 0.5) * j
        ny = py + gy + (np.random.random(N).astype(np.float32) - 0.5) * j

        # reflect at the rim
        nx = np.where(nx < 0, -nx, nx); nx = np.where(nx > 1, 2 - nx, nx)
        ny = np.where(ny < 0, -ny, ny); ny = np.where(ny > 1, 2 - ny, ny)
        self.px = np.clip(nx, 0.0, 1.0)
        self.py = np.clip(ny, 0.0, 1.0)
        self.v = v

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
        for cx in (OX - 1, OX + PLATE):
            for cy in (OY - 1, OY + PLATE):
                pyxel.pset(cx + jx, cy + jy, 9 if border == 1 else 10)

        sx = (OX + jx + self.px * PLATE).astype(np.int32)
        sy = (OY + jy + self.py * PLATE).astype(np.int32)
        b = np.clip((self.v * 5).astype(np.int32), 0, 4)
        col = COLS[b]
        # settled grains twinkle: a few flash white each frame
        spark = (self.v < 0.08) & (np.random.random(N) < 0.02)
        col = np.where(spark, 7, col)
        # single-pixel grains, brightest where the sand has settled
        for x, y, c in zip(sx.tolist(), sy.tolist(), col.tolist()):
            pyxel.pset(x, y, c)

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
