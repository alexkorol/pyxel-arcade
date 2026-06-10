"""Undervault -- a cross-section hex roguelike (walking skeleton).

The dungeon is a mountain seen side-on, built from offset brick rows.
Offset rows give every cell six neighbors -- it IS a hex grid, drawn
as masonry. Dig the strata, mind gravity, hoard your torchlight.

Controls:  A / D = step left / right        (arrows work too)
           Q / E = climb up-left / up-right
           Z / C = descend down-left / down-right
           or click an adjacent cell        S = wait a turn
           T = mount a torch (you carry 3)  R = delve anew

Study: offset coordinates as hexagons (Red Blob Games), BFS torchlight
through carved air, pyxel.pal() palette banding for light falloff,
and settle() -- gravity as a while-loop.
"""
import random

import pyxel

SW_, SH_ = 240, 180          # screen
CW, CH = 24, 16              # one brick
COLS, ROWS = 44, 64          # the mountain
AIR, EARTH, STONE, BEDROCK = range(4)
HARDNESS = {EARTH: 1, STONE: 2}

# odd rows shift right half a brick; each parity has its own neighbor set
# order: W, E, NW, NE, SW, SE
NBRS = [
    ((-1, 0), (1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1)),   # even rows
    ((-1, 0), (1, 0), (0, -1), (1, -1), (0, 1), (1, 1)),     # odd rows
]

PALETTE = [
    0x0A0814, 0x16102A, 0x3A2A1C, 0x6B4530, 0x9A6238, 0x343852,
    0x6E7287, 0xC4C8DA, 0xEF3C63, 0xFF8A3D, 0xFFD23E, 0x2563C9,
    0x41A6F6, 0x7A83AB, 0x221A30, 0x33232C,
]
# light bands: 2 = lit (true colors), 1 = dim, 0 = remembered in the dark
REMAPS = {
    1: ((4, 3), (3, 2), (7, 6), (6, 5), (15, 14), (10, 9), (12, 13)),
    0: ((4, 2), (3, 2), (2, 2), (7, 5), (6, 5), (15, 1), (14, 1),
        (10, 5), (9, 5), (12, 5), (13, 5)),
}
LIT, DIM = 4.0, 1.4          # band thresholds on the light field


def nbr(c, r, d):
    dc, dr = NBRS[r & 1][d]
    return c + dc, r + dr


def cell_px(c, r):
    """Top-left pixel of a cell (the half-brick shift makes the hex)."""
    return c * CW + (r & 1) * (CW // 2), r * CH


class Bat:
    def __init__(self, c, r):
        self.c, self.r = c, r
        x, y = cell_px(c, r)
        self.px, self.py = float(x), float(y)

    def flit(self, app):
        opts = [nbr(self.c, self.r, d) for d in range(6)]
        opts = [p for p in opts if app.mat(*p) == AIR and p != (app.pc, app.pr)]
        if opts and random.random() < 0.7:
            self.c, self.r = random.choice(opts)

    def update(self):
        x, y = cell_px(self.c, self.r)
        self.px += (x - self.px) * 0.2
        self.py += (y - self.py) * 0.2

    def draw(self, ox, oy):
        x = int(self.px) - ox + CW // 2
        y = int(self.py) - oy + CH // 2
        flap = (pyxel.frame_count // 6) % 2
        w = 5 if flap else 7
        pyxel.tri(x - w, y - flap * 2, x - 1, y, x - 2, y - 3, 13)
        pyxel.tri(x + w, y - flap * 2, x + 1, y, x + 2, y - 3, 13)
        pyxel.rect(x - 2, y - 3, 4, 4, 5)
        pyxel.pset(x - 1, y - 2, 8)
        pyxel.pset(x + 1, y - 2, 8)


class App:
    def __init__(self):
        pyxel.init(SW_, SH_, title="undervault", fps=30)
        pyxel.mouse(True)
        pyxel.colors[:] = PALETTE
        self.delve()

    def run(self):
        pyxel.run(self.update, self.draw)

    # -- world generation ----------------------------------------------
    def delve(self):
        self.grid = bytearray(COLS * ROWS)
        for r in range(ROWS):
            for c in range(COLS):
                stratum = EARTH if r < 24 else STONE
                if c < 2 or c > COLS - 3 or r < 2 or r > ROWS - 3:
                    stratum = BEDROCK
                self.grid[c + r * COLS] = stratum

        self.carve_blob(COLS // 2, 5, 4, 2)             # the entry hall
        for _ in range(4):                              # wandering tunnels
            c, r = COLS // 2, 6
            for _ in range(100):
                d = random.choice((0, 1, 2, 3, 4, 4, 5, 5))
                c, r = nbr(c, r, d)
                c = max(3, min(COLS - 4, c))
                r = max(3, min(ROWS - 4, r))
                self.set_air(c, r)
                if random.random() < 0.25:
                    self.set_air(*nbr(c, r, random.randrange(6)))
        for _ in range(7):                              # cosy caverns
            self.carve_blob(random.randint(5, COLS - 6),
                            random.randint(12, ROWS - 8),
                            random.randint(2, 4), random.randint(1, 2))
        for _ in range(3):                              # vertical shafts
            c = random.randint(5, COLS - 6)
            top = random.randint(4, 34)
            for r in range(top, min(ROWS - 4, top + random.randint(6, 12))):
                self.set_air(c, r)
        for r in range(3, ROWS - 3):                    # drop orphan bricks
            for c in range(3, COLS - 3):
                if self.mat(c, r) in (EARTH, STONE) and \
                        sum(self.mat(*nbr(c, r, d)) == AIR for d in range(6)) >= 5:
                    self.set_air(c, r)

        self.torches = []                               # mounted lights
        spots = [(c, r) for r in range(3, ROWS - 3) for c in range(3, COLS - 3)
                 if self.mat(c, r) == AIR and self.wallside(c, r)]
        for c, r in random.sample(spots, min(5, len(spots))):
            self.torches.append((c, r))

        self.pc, self.pr = COLS // 2, 5
        self.set_air(self.pc, self.pr)
        x, y = cell_px(self.pc, self.pr)
        self.ppx, self.ppy = float(x), float(y)
        self.face = 1
        self.hp = 3
        self.packs = 3                                  # torches carried
        self.cracks = {}
        self.explored = set()
        self.bats = []
        deep = [(c, r) for c, r in spots if r > 14]
        for c, r in random.sample(deep, min(3, len(deep))):
            self.bats.append(Bat(c, r))
        self.settle(quiet=True)
        self.cam_x, self.cam_y = self.cam_target()
        self.shake = 0.0
        self.msg = "the undervault swallows your footsteps"

    def carve_blob(self, cx, cy, rx, ry):
        for r in range(cy - ry, cy + ry + 1):
            for c in range(cx - rx, cx + rx + 1):
                if 2 < c < COLS - 3 and 2 < r < ROWS - 3 and \
                        (c - cx) ** 2 / (rx * rx + .1) + (r - cy) ** 2 / (ry * ry + .1) <= 1:
                    self.set_air(c, r)

    def wallside(self, c, r):
        return self.mat(*nbr(c, r, 0)) != AIR or self.mat(*nbr(c, r, 1)) != AIR

    # -- grid helpers ----------------------------------------------------
    def mat(self, c, r):
        if 0 <= c < COLS and 0 <= r < ROWS:
            return self.grid[c + r * COLS]
        return BEDROCK

    def set_air(self, c, r):
        if self.mat(c, r) != BEDROCK:
            self.grid[c + r * COLS] = AIR

    # -- light: BFS radiance through carved air ---------------------------
    def relight(self):
        flick = pyxel.frame_count * 0.31
        srcs = [(self.pc, self.pr, 7.0 + 0.4 * pyxel.sin(flick * 57.3))]
        for i, (c, r) in enumerate(self.torches):
            srcs.append((c, r, 6.2 + 0.5 * pyxel.sin(flick * 57.3 + i * 40)))
        light = {}
        queue = []
        for c, r, lum in srcs:
            if light.get((c, r), 0) < lum:
                light[(c, r)] = lum
                queue.append((c, r, lum))
        while queue:
            c, r, lum = queue.pop()
            if lum <= 1:
                continue
            for d in range(6):
                nc, nr = nbr(c, r, d)
                if light.get((nc, nr), 0) >= lum - 1:
                    continue
                if self.mat(nc, nr) == AIR:
                    light[(nc, nr)] = lum - 1
                    queue.append((nc, nr, lum - 1))
                else:                       # walls catch spill from the air
                    light[(nc, nr)] = max(light.get((nc, nr), 0), lum - 0.6)
        self.light = light
        for cell, lum in light.items():
            if lum >= 0.8:                  # seen once, remembered forever
                self.explored.add(cell)

    # -- gravity ----------------------------------------------------------
    def settle(self, quiet=False):
        fell = 0
        while True:
            below = [nbr(self.pc, self.pr, 4), nbr(self.pc, self.pr, 5)]
            opts = [p for p in below if self.mat(*p) == AIR]
            if len(opts) < 2:               # one solid brick is footing enough
                break
            self.pc, self.pr = opts[self.face > 0]  # tumble with momentum
            fell += 1
        if fell >= 4 and not quiet:
            self.hp -= 1
            self.shake = 4
            self.msg = "you crash down %d fathoms" % fell
            if self.hp <= 0:
                self.msg = "the fall takes you. R delves anew"
        elif fell and not quiet:
            self.msg = "you tumble into the dark"

    # -- one player turn ---------------------------------------------------
    def act(self, d):
        if self.hp <= 0:
            return
        nc, nr = nbr(self.pc, self.pr, d)
        if d in (0, 2, 4):
            self.face = -1
        elif d in (1, 3, 5):
            self.face = 1
        m = self.mat(nc, nr)
        if m == AIR:
            self.pc, self.pr = nc, nr
            for b in self.bats:
                if (b.c, b.r) == (nc, nr):
                    b.flit(self)
                    self.msg = "a bat shrieks past your ear"
            self.settle()
        elif m == BEDROCK:
            self.msg = "the bedrock defies your pick"
        else:
            hits = self.cracks.get((nc, nr), 0) + 1
            if hits >= HARDNESS[m]:
                self.grid[nc + nr * COLS] = AIR
                self.cracks.pop((nc, nr), None)
                self.msg = "you dig through packed earth" if m == EARTH \
                    else "the old stonework gives way"
                self.settle()
            else:
                self.cracks[(nc, nr)] = hits
                self.msg = "the stone cracks under your pick"
        for b in self.bats:
            b.flit(self)

    def place_torch(self):
        if self.hp <= 0 or self.packs <= 0:
            self.msg = "no torches left in your pack"
            return
        if (self.pc, self.pr) in self.torches:
            self.msg = "a torch already burns here"
            return
        self.torches.append((self.pc, self.pr))
        self.packs -= 1
        self.msg = "you mount a torch on the brickwork"
        for b in self.bats:
            b.flit(self)

    # -- io loop ------------------------------------------------------------
    def cam_target(self):
        x, y = cell_px(self.pc, self.pr)
        tx = min(max(x + CW // 2 - SW_ // 2, 0), COLS * CW - SW_)
        ty = min(max(y + CH // 2 - SH_ // 2, 0), ROWS * CH - SH_)
        return tx, ty

    def hovered(self):
        mx, my = pyxel.mouse_x + self.cam_x, pyxel.mouse_y + self.cam_y
        r = int(my // CH)
        c = int((mx - (r & 1) * (CW // 2)) // CW)
        for d in range(6):
            if nbr(self.pc, self.pr, d) == (c, r):
                return d
        return None

    def update(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.delve()
        keys = ((pyxel.KEY_A, 0), (pyxel.KEY_LEFT, 0), (pyxel.KEY_D, 1),
                (pyxel.KEY_RIGHT, 1), (pyxel.KEY_Q, 2), (pyxel.KEY_E, 3),
                (pyxel.KEY_Z, 4), (pyxel.KEY_C, 5))
        for key, d in keys:
            if pyxel.btnp(key, 14, 5):
                self.act(d)
                break
        else:
            if pyxel.btnp(pyxel.KEY_S):
                self.msg = "you listen to the dripping dark"
                for b in self.bats:
                    b.flit(self)
            if pyxel.btnp(pyxel.KEY_T):
                self.place_torch()
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                d = self.hovered()
                if d is not None:
                    self.act(d)

        x, y = cell_px(self.pc, self.pr)
        self.ppx += (x - self.ppx) * 0.35
        self.ppy += (y - self.ppy) * 0.35
        tx, ty = self.cam_target()
        self.cam_x += (tx - self.cam_x) * 0.15
        self.cam_y += (ty - self.cam_y) * 0.15
        self.shake *= 0.8
        for b in self.bats:
            b.update()
        self.relight()

    # -- rendering ------------------------------------------------------------
    def band(self, c, r):
        lum = self.light.get((c, r), 0)
        if lum >= LIT:
            return 2
        if lum >= DIM:
            return 1
        return 0 if (c, r) in self.explored else None

    def apply_band(self, b):
        pyxel.pal()
        if b < 2:
            for src, dst in REMAPS[b]:
                pyxel.pal(src, dst)

    def draw_cell(self, c, r, ox, oy):
        b = self.band(c, r)
        if b is None:
            return
        self.apply_band(b)
        x, y = cell_px(c, r)
        x, y = x - ox, y - oy
        m = self.mat(c, r)
        if m == AIR:
            pyxel.rect(x, y, CW, CH, 15)
            pyxel.rect(x, y + CH - 1, CW, 1, 14)        # rear masonry seam
            h = c * 7 + r * 13                          # stony backdrop
            pyxel.pset(x + h % CW, y + (h // 3) % (CH - 2), 14)
            pyxel.pset(x + (h * 5 + 9) % CW, y + (h * 7 + 4) % (CH - 2), 14)
        else:
            lit, mid, dark = (4, 3, 2) if m == EARTH else (7, 6, 5)
            pyxel.rect(x, y, CW, CH, 1)                 # mortar seam
            pyxel.rect(x + 1, y + 1, CW - 2, CH - 2, mid)
            pyxel.rect(x + 1, y + 1, CW - 2, 2, lit)    # catching the light
            pyxel.rect(x + 1, y + CH - 3, CW - 2, 2, dark)
            if m == BEDROCK:
                for i in range(4):
                    pyxel.pset(x + 4 + i * 5, y + 4 + (i * 7 + c * 3 + r) % 8, 0)
            if (c, r) in self.cracks:
                pyxel.line(x + CW // 2 - 2, y + 3, x + CW // 2 + 2, y + CH - 4, dark)
                pyxel.pset(x + CW // 2 + 1, y + CH // 2, 0)
        pyxel.pal()

    def draw_torch(self, c, r, ox, oy):
        if self.band(c, r) is None:
            return
        x, y = cell_px(c, r)
        x, y = x - ox + CW // 2, y - oy
        pyxel.rect(x - 1, y + 8, 2, 5, 3)
        f = (pyxel.frame_count // 4 + c * 7 + r) % 3
        pyxel.tri(x, y + 1 + f % 2, x - 3, y + 8, x + 3, y + 8, 9)
        pyxel.tri(x, y + 4 + f % 2, x - 1, y + 8, x + 2, y + 8, 10)

    def draw_player(self, ox, oy):
        x = int(self.ppx) - ox + CW // 2
        y = int(self.ppy) - oy + CH
        f = self.face
        bob = (pyxel.frame_count // 12) % 2             # idle breathing
        pyxel.rect(x - 4, y - 2, 3, 2, 5)               # boots
        pyxel.rect(x + 1, y - 2, 3, 2, 5)
        pyxel.rect(x - 4 - f, y - 8 + bob, 8, 6 - bob, 8)   # tabard
        pyxel.rect(x - 4 - f, y - 5, 8, 1, 2)           # belt
        pyxel.rect(x - f * 6, y - 7 + bob, 3, 4, 6)     # shield arm
        pyxel.rect(x - 3, y - 13 + bob, 7, 6, 7)        # helm
        pyxel.rect(x - 3 + (f > 0) * 4, y - 12 + bob, 3, 2, 0)  # visor
        pyxel.rect(x - 1, y - 15 + bob, 2, 2, 12)       # plume
        px_ = x + f * 5                                 # the pick
        pyxel.rect(px_, y - 12 + bob, 1, 9, 3)
        pyxel.rect(px_ - 1, y - 14 + bob, 3, 2, 6)

    def draw(self):
        ox = int(self.cam_x + random.uniform(-self.shake, self.shake))
        oy = int(self.cam_y + random.uniform(-self.shake, self.shake))
        pyxel.cls(0)
        c0, r0 = max(0, ox // CW - 1), max(0, oy // CH)
        c1, r1 = min(COLS, (ox + SW_) // CW + 2), min(ROWS, (oy + SH_) // CH + 2)
        for r in range(r0, r1):
            for c in range(c0, c1):
                self.draw_cell(c, r, ox, oy)
        for c, r in self.torches:
            self.draw_torch(c, r, ox, oy)
        for b in self.bats:
            bb = self.band(b.c, b.r)
            if bb:
                self.apply_band(bb)
                b.draw(ox, oy)
                pyxel.pal()
        if self.hp > 0:
            self.draw_player(ox, oy)

        d = self.hovered()                              # move preview
        if d is not None and self.hp > 0:
            hc, hr = nbr(self.pc, self.pr, d)
            x, y = cell_px(hc, hr)
            pyxel.rectb(x - ox, y - oy, CW, CH, 10)

        pyxel.rect(0, 0, SW_, 9, 0)                     # hud strip
        for i in range(3):
            col = 8 if i < self.hp else 5
            x = 5 + i * 9
            pyxel.tri(x, 2, x + 4, 2, x + 2, 6, col)
            pyxel.rect(x + 1, 1, 3, 2, col)
        for i in range(self.packs):
            pyxel.rect(36 + i * 5, 2, 2, 5, 9)
            pyxel.pset(36 + i * 5, 1, 10)
        depth = max(0, self.pr - 5)
        pyxel.text(SW_ - 44, 2, "depth %2dm" % depth, 13)
        pyxel.rect(0, SH_ - 9, SW_, 9, 0)
        pyxel.text(3, SH_ - 7, self.msg, 13)
        pyxel.text(SW_ - 78, SH_ - 7, "QEZC+AD T R", 5)


if __name__ == "__main__":
    App().run()
