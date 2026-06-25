"""Shell Lab -- elementary cellular automata, grown into seashells.

A cone snail pigments its shell one row at a time: as the lip advances,
a band of cells along the mantle "decides" to deposit pigment or not,
reading only its neighbours from the row just laid down. That is exactly
a one-dimensional cellular automaton -- and the textile cone (Conus
textilis) really does wear Wolfram's Rule 30. So this is a lab: pick a
rule (0-255), pick a specimen palette, and watch the shell draw itself
from tip to aperture.

The screen is never cleared while a shell grows -- each new generation
is one vertical column painted onto a persistent canvas, shaded by how
far it sits from the shell's rounded spine. The whole circumference is
squeezed into each column, so the pattern curves away at the edges the
way it does on the real animal.

Controls:  <- / ->  rule -/+        up / down  specimen
           SPACE pause   R reseed    S seed mode   W wrap
           [ / ]  speed   - / =  zoom    A auto-loop   C clear seed
           click rule arrows / preview thumbs / specimen / dice / cells

Study: elementary CA rule lookup ((rule >> nbhd) & 1), a flat bytearray
row stepped in place, palette swaps via pyxel.colors[:], and rim-shading
a 1-D signal into a 3-D body.
"""
import math
import random

import pyxel

W, H = 256, 192
N = 128                         # cells around the shell's circumference
CX0, CY = 10, 80               # left tip x, vertical centre of the shell
MAXH = 50                      # half-height of the fattest column, px
SEED_CELLS = 32                # width of the clickable seed editor

SIM = (4, 14, 184, 143)        # x0, y0, x1, y1 of the simulation frame
X_END = 174                    # rightmost x a generation may reach

SPEED_TABLE = [(12, 1), (6, 1), (3, 1), (1, 1), (1, 2)]   # (frames/step, steps)
ZOOMS = [1, 2, 3]
SEED_MODES = ["SINGLE", "RANDOM", "PAIR", "EDIT"]

# Shared UI colours (palette indices that never change between specimens).
UI = {0: 0x0b0b16, 1: 0x161a2e, 2: 0x2b3157, 3: 0x474f78, 4: 0x6a7299,
      5: 0x9aa3c4, 13: 0xffc24a, 14: 0x5bd06a, 15: 0xe7588a}

# Per-specimen shell ramps, in index order: 6 outline, 7 base-hi, 8 pig-shadow,
# 9 pig-mid, 10 pig-hi, 11 base-shadow, 12 base-mid.
SHELL = {
    "textile": (0x1c130b, 0xf6eccf, 0x3a2412, 0x6e4423, 0x97632f, 0xc6a674, 0xe3cda0),
    "marble":  (0x14120e, 0xfbf4e4, 0x15110d, 0x30271c, 0x4c3d2b, 0xc9bda0, 0xe8ddc6),
    "gold":    (0x2a1b06, 0xfff0c2, 0x5a3208, 0x8f5410, 0xc07c1d, 0xd6a23f, 0xf0cf7a),
    "olive":   (0x141a0c, 0xeef0d2, 0x33401a, 0x55662b, 0x788a3f, 0x9aa766, 0xcdd39a),
    "auger":   (0x1a1020, 0xf3e6f2, 0x3a1f4a, 0x5e3470, 0x854f9a, 0xab7fae, 0xd8b8d6),
}

# name, status-bar code, signature rule, three preview rules, palette key.
SPECIES = [
    ("TEXTILE CONE",  "CONUS_TEXTILE", 30,  (30, 45, 73),   "textile"),
    ("MARBLE CONE",   "CONUS_MARM",    90,  (90, 18, 22),   "marble"),
    ("CLOTH OF GOLD", "CYMBIOLA",      150, (150, 105, 22), "gold"),
    ("OLIVE SHELL",   "OLIVA_POR",     110, (110, 124, 193), "olive"),
    ("AUGER SPIRE",   "TEREBRA",       57,  (57, 99, 60),   "auger"),
]


def step_row(row, rule, wrap):
    """One generation of an elementary CA over a flat bytearray."""
    n = len(row)
    out = bytearray(n)
    for i in range(n):
        left = row[i - 1] if i > 0 else (row[n - 1] if wrap else 0)
        right = row[i + 1] if i < n - 1 else (row[0] if wrap else 0)
        out[i] = (rule >> ((left << 2) | (row[i] << 1) | right)) & 1
    return out


def ca_triangle(rule, w, h):
    """Classic top-down evolution from a single seed, for a preview thumb."""
    row = bytearray(w)
    row[w // 2] = 1
    rows = [bytes(row)]
    for _ in range(h - 1):
        row = step_row(row, rule, False)
        rows.append(bytes(row))
    return rows


class Cursor:
    """Software crosshair: remembers the pixels it covers and restores them
    next frame, so it never smears the persistent shell canvas (the engine
    cursor would -- same trick as hex_bloom)."""

    ARMS = ((-2, 0), (-1, 0), (1, 0), (2, 0), (0, -2), (0, -1), (0, 1), (0, 2))

    def __init__(self):
        self.under = []

    def erase(self):
        for x, y, c in self.under:
            pyxel.pset(x, y, c)
        self.under = []

    def draw(self):
        for dx, dy in self.ARMS:
            x, y = pyxel.mouse_x + dx, pyxel.mouse_y + dy
            if 0 <= x < W and 0 <= y < H:
                self.under.append((x, y, pyxel.pget(x, y)))
                pyxel.pset(x, y, 13)


class App:
    def __init__(self):
        pyxel.init(W, H, title="shell lab", fps=60, quit_key=pyxel.KEY_NONE)
        pyxel.mouse(False)
        self.cursor = Cursor()
        self.species_i = 0
        self.rule = SPECIES[0][2]
        self.seed_mode = 0
        self.seed_bits = bytearray(SEED_CELLS)
        self.seed_val = 0x5E3A
        self.wrap = True
        self.paused = False
        self.auto = True
        self.speed_i = 2
        self.zoom_i = 1
        self.layout()
        self.apply_palette()
        self.restart()

    def run(self):
        pyxel.run(self.update, self.draw)

    # ---- layout & palette -------------------------------------------------

    def layout(self):
        self.hot = {
            "rule_l": (190, 25, 16, 16), "rule_r": (234, 25, 16, 16),
            "thumb0": (196, 62, 31, 15), "thumb1": (196, 84, 31, 15),
            "thumb2": (196, 106, 31, 15), "species": (190, 124, 62, 11),
            "dice": (238, 146, 11, 9), "pause": (116, 15, 64, 9),
            "spd_l": (172, 180, 7, 9), "spd_r": (188, 180, 7, 9),
            "zoom_l": (222, 180, 7, 9), "zoom_r": (238, 180, 7, 9),
        }

    def apply_palette(self):
        pal = [0] * 16
        for i, c in UI.items():
            pal[i] = c
        ramp = SHELL[SPECIES[self.species_i][4]]
        for i, c in zip((6, 7, 8, 9, 10, 11, 12), ramp):
            pal[i] = c
        pyxel.colors[:] = pal

    # ---- simulation lifecycle --------------------------------------------

    def build_seed(self):
        bits = bytearray(SEED_CELLS)
        mode = SEED_MODES[self.seed_mode]
        if mode == "SINGLE":
            bits[SEED_CELLS // 2] = 1
        elif mode == "RANDOM":
            rng = random.Random(self.seed_val)
            for i in range(SEED_CELLS):
                bits[i] = 1 if rng.random() < 0.5 else 0
        elif mode == "PAIR":
            bits[SEED_CELLS // 2 - 3] = 1
            bits[SEED_CELLS // 2 + 3] = 1
        else:                                   # EDIT keeps whatever is drawn
            bits = bytearray(self.seed_bits)
        self.seed_bits = bits
        row = bytearray(N)
        off = (N - SEED_CELLS) // 2
        for i in range(SEED_CELLS):
            row[off + i] = bits[i]
        return row

    def thumb_rules(self):
        pool = SPECIES[self.species_i][3]
        alts = [r for r in pool if r != self.rule][:2]
        while len(alts) < 2:
            alts.append((self.rule + len(alts) + 1) % 256)
        return [self.rule, alts[0], alts[1]]

    def restart(self):
        self.col_w = ZOOMS[self.zoom_i]
        self.total_gens = max(8, (X_END - CX0) // self.col_w)
        self.row = self.build_seed()
        self.gen = 0
        self.complete = False
        self.complete_frame = 0
        self.dhist = [sum(self.row) / N]
        self.pending = [(0, bytes(self.row))]
        self.draw_lip = False
        self.need_static = True

    def step_once(self):
        if self.complete:
            return
        self.row = step_row(self.row, self.rule, self.wrap)
        self.gen += 1
        self.dhist.append(sum(self.row) / N)
        if len(self.dhist) > 110:
            self.dhist.pop(0)
        self.pending.append((self.gen, bytes(self.row)))
        if self.gen >= self.total_gens - 1:
            self.complete = True
            self.complete_frame = pyxel.frame_count
            self.draw_lip = True

    def set_rule(self, v):
        self.rule = v % 256
        self.restart()

    def cycle_species(self, d):
        self.species_i = (self.species_i + d) % len(SPECIES)
        self.rule = SPECIES[self.species_i][2]
        self.apply_palette()
        self.restart()

    # ---- input ------------------------------------------------------------

    def update(self):
        rep = lambda k: pyxel.btnp(k, 15, 3)
        if rep(pyxel.KEY_RIGHT):
            self.set_rule(self.rule + 1)
        if rep(pyxel.KEY_LEFT):
            self.set_rule(self.rule - 1)
        if pyxel.btnp(pyxel.KEY_UP):
            self.cycle_species(-1)
        if pyxel.btnp(pyxel.KEY_DOWN):
            self.cycle_species(1)
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.paused = not self.paused
        if pyxel.btnp(pyxel.KEY_R):
            self.seed_val = random.randint(0, 0xFFFF)
            self.restart()
        if pyxel.btnp(pyxel.KEY_S):
            self.seed_mode = (self.seed_mode + 1) % len(SEED_MODES)
            self.restart()
        if pyxel.btnp(pyxel.KEY_W):
            self.wrap = not self.wrap
            self.restart()
        if pyxel.btnp(pyxel.KEY_A):
            self.auto = not self.auto
        if pyxel.btnp(pyxel.KEY_C) and SEED_MODES[self.seed_mode] == "EDIT":
            self.seed_bits = bytearray(SEED_CELLS)
            self.restart()
        if rep(pyxel.KEY_LEFTBRACKET):
            self.speed_i = max(0, self.speed_i - 1)
        if rep(pyxel.KEY_RIGHTBRACKET):
            self.speed_i = min(len(SPEED_TABLE) - 1, self.speed_i + 1)
        if pyxel.btnp(pyxel.KEY_MINUS) and self.zoom_i > 0:
            self.zoom_i -= 1
            self.restart()
        if pyxel.btnp(pyxel.KEY_EQUALS) and self.zoom_i < len(ZOOMS) - 1:
            self.zoom_i += 1
            self.restart()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.click(pyxel.mouse_x, pyxel.mouse_y)

        if not self.paused and not self.complete:
            every, steps = SPEED_TABLE[self.speed_i]
            if pyxel.frame_count % every == 0:
                for _ in range(steps):
                    self.step_once()
        if self.complete and self.auto and \
                pyxel.frame_count - self.complete_frame > 120:
            if SEED_MODES[self.seed_mode] == "RANDOM":
                self.seed_val = random.randint(0, 0xFFFF)
            self.restart()

    def click(self, mx, my):
        for name, (x, y, w, h) in self.hot.items():
            if x <= mx < x + w and y <= my < y + h:
                self.dispatch(name)
                return
        # seed editor cells
        if 157 <= my < 170 and 100 <= mx < 100 + SEED_CELLS * 4:
            i = (mx - 100) // 4
            self.seed_mode = SEED_MODES.index("EDIT")
            self.seed_bits[i] ^= 1
            self.restart()

    def dispatch(self, name):
        if name == "rule_l":
            self.set_rule(self.rule - 1)
        elif name == "rule_r":
            self.set_rule(self.rule + 1)
        elif name == "species":
            self.cycle_species(1)
        elif name == "dice":
            self.seed_val = random.randint(0, 0xFFFF)
            self.restart()
        elif name == "pause":
            self.paused = not self.paused
        elif name.startswith("thumb"):
            self.set_rule(self.thumb_rules()[int(name[5])])
        elif name == "spd_l":
            self.speed_i = max(0, self.speed_i - 1)
        elif name == "spd_r":
            self.speed_i = min(len(SPEED_TABLE) - 1, self.speed_i + 1)
        elif name == "zoom_l" and self.zoom_i > 0:
            self.zoom_i -= 1
            self.restart()
        elif name == "zoom_r" and self.zoom_i < len(ZOOMS) - 1:
            self.zoom_i += 1
            self.restart()

    # ---- drawing ----------------------------------------------------------

    def profile(self, t):
        """Shell silhouette: pointed tip (t=0) swelling to a rounded
        aperture (t=1). Returns a half-height fraction in [0, 1]."""
        b = t ** 0.6
        if t > 0.85:
            b *= math.sqrt(max(0.0, 1 - ((t - 0.85) / 0.17) ** 2))
        return min(1.0, b * 1.1)

    def draw_column(self, g, row):
        sx = CX0 + g * self.col_w
        t = g / max(1, self.total_gens - 1)
        ph = max(1, int(self.profile(t) * MAXH))
        top, span = CY - ph, 2 * ph
        for sy in range(CY - ph, CY + ph + 1):
            frac = (sy - top) / span
            on = row[int(frac * (N - 1) + 0.5)]
            rim = abs(frac - 0.5) * 2
            lit = rim < 0.4 or 0.27 < frac < 0.36          # spine + sheen band
            if rim > 0.93:
                c = 6                                       # dark contour edge
            elif on:
                c = 10 if lit else (9 if rim < 0.78 else 8)
            else:
                c = 7 if lit else (12 if rim < 0.78 else 11)
            for k in range(self.col_w):
                pyxel.pset(sx + k, sy, c)

    def draw_aperture(self):
        ap = CX0 + (self.total_gens - 1) * self.col_w
        ph = max(3, int(self.profile(1.0) * MAXH))
        for i in range(5):                                  # stacked lip whorls
            pyxel.ellib(ap + i, CY - ph + i * 2, 7, 2 * (ph - i * 2),
                        7 if i % 2 == 0 else 12)
        pyxel.elli(ap + 6, CY - ph + 9, 5, max(2, 2 * (ph - 9)), 6)

    def draw_static(self):
        pyxel.cls(0)
        pyxel.rect(0, 0, W, 12, 1)
        pyxel.text(4, 3, "PYXEL SHELL LAB", 7)
        pyxel.text(96, 4, "natural cellular automata", 4)
        pyxel.rectb(SIM[0], SIM[1], SIM[2] - SIM[0], SIM[3] - SIM[1], 3)

        # right panel ------------------------------------------------------
        pyxel.rect(188, 14, 64, 129, 1)
        pyxel.rectb(188, 14, 64, 129, 2)
        pyxel.text(192, 17, "RULE", 4)
        pyxel.rectb(190, 25, 60, 16, 3)
        pyxel.text(194, 30, "<", 5)
        pyxel.text(244, 30, ">", 5)
        rs = str(self.rule)
        pyxel.text(220 - len(rs) * 2, 30, rs, 13)
        for i in range(8):                                  # the 8 rule bits
            on = (self.rule >> (7 - i)) & 1
            pyxel.rect(192 + i * 7, 44, 6, 6, 13 if on else 2)

        pyxel.text(192, 54, "PREVIEW", 4)
        trules = self.thumb_rules()
        for s, rule in enumerate(trules):
            tx, ty = 196, 62 + s * 22
            active = rule == self.rule and s == 0
            pyxel.rect(tx - 1, ty - 1, 33, 17, 0)
            pyxel.rectb(tx - 1, ty - 1, 33, 17, 13 if active else 3)
            for y, r in enumerate(ca_triangle(rule, 31, 15)):
                for x in range(31):
                    if r[x]:
                        pyxel.pset(tx + x, ty + y, 13 if active else 5)
            pyxel.text(231, ty + 5, str(rule), 13 if active else 4)
        # specimen selector
        pyxel.text(191, 125, "<", 5)
        pyxel.text(245, 125, ">", 5)
        nm = SPECIES[self.species_i][0]
        pyxel.text(220 - len(nm) * 2, 125, nm, 13)

        # bottom: palette + seed editor -----------------------------------
        pyxel.rectb(4, 145, 90, 30, 2)
        pyxel.text(8, 148, "PALETTE 16", 4)
        for i in range(16):
            pyxel.rect(8 + (i % 8) * 10, 158 + (i // 8) * 8, 9, 7, i)
        pyxel.rectb(96, 145, 156, 30, 2)
        pyxel.text(100, 148, f"SEED {self.seed_val:04X}", 4)
        pyxel.text(160, 148, f"MODE {SEED_MODES[self.seed_mode]}", 4)
        pyxel.rect(238, 146, 11, 9, 3)                       # dice button
        pyxel.text(241, 148, "R", 13)
        for i in range(SEED_CELLS):
            pyxel.rect(100 + i * 4, 158, 3, 11, 13 if self.seed_bits[i] else 2)

        # status bar -------------------------------------------------------
        pyxel.rect(0, 177, W, 15, 1)
        code = SPECIES[self.species_i][1]
        pyxel.text(4, 181, f"SHELL LAB v1   MODEL: {code}", 4)
        pyxel.text(150, 181, "SPD", 4)
        pyxel.text(173, 181, "-", 5)
        pyxel.text(181, 181, str(self.speed_i + 1), 13)
        pyxel.text(189, 181, "+", 5)
        pyxel.text(200, 181, "ZOOM", 4)
        pyxel.text(223, 181, "-", 5)
        pyxel.text(230, 181, f"{ZOOMS[self.zoom_i]}", 13)
        pyxel.text(239, 181, "+", 5)

    def draw_overlays(self):
        # top strip (clear of the shell body)
        pyxel.rect(6, 15, 176, 10, 0)
        pyxel.text(8, 17, f"SIMULATION {N}x{self.total_gens}", 4)
        pyxel.text(120, 17, f"GEN {self.gen}", 13)
        if self.paused:
            st, sc = "PAUSED", 13
        elif self.complete:
            st, sc = "COMPLETE", 12
        else:
            st, sc = "RUNNING", 14
        pyxel.text(180 - len(st) * 4, 17, st, sc)
        # bottom strip
        pyxel.rect(6, 131, 176, 11, 0)
        dens = int(self.dhist[-1] * 100) if self.dhist else 0
        pyxel.text(8, 134, f"DENSITY {dens}%", 5)
        pyxel.text(154, 134, f"WRAP {'ON' if self.wrap else 'OFF'}", 4)
        for i, d in enumerate(self.dhist):                  # density sparkline
            pyxel.pset(60 + i, 141 - int(d * 8), 9)

    def draw(self):
        self.cursor.erase()
        if self.need_static:
            self.draw_static()
            self.need_static = False
        for g, row in self.pending:
            self.draw_column(g, row)
        self.pending = []
        if self.draw_lip:
            self.draw_aperture()
            self.draw_lip = False
        self.draw_overlays()
        self.cursor.draw()


if __name__ == "__main__":
    App().run()
