"""Starlance -- a wireframe space dogfighter with a roguelite run.

Eight jumps stand between you and the pirate carrier. Pick your route
like FTL, fight like Wing Commander on a 1985 budget: lasers overheat,
missiles need a lock, credits drift out of every kill, and the
waystation shop between jumps sells what it feels like selling.

Controls:  mouse steers (or arrows)      hold SHIFT = burn
           SPACE / left click = lasers   M / right click = missile
           needs a lock: keep the target near your crosshair
           fly into floating pickups     R = new run

Study: a tiny 3D pipeline (translate, yaw, pitch, perspective divide),
wireframe models as vert/edge lists, lead-free missile steering, and
debris made from the dead ship's own edges.
"""
import math
import random

import pyxel

W, H = 240, 180
CX, CY = W // 2, H // 2
FOV = 105
JUMPS = 8

PALETTE = [
    0x05060F, 0x141B33, 0x232C52, 0x00B543, 0x59D88A, 0x3A3E52,
    0x6E7287, 0xE8ECF8, 0xEF3C63, 0xFF8A3D, 0xFFD23E, 0x9A2D4F,
    0x41A6F6, 0x7A83AB, 0xB56DD4, 0x35E8DC,
]

MODELS = {
    "fighter": ([(0, 0, 5), (-4, 0, -3), (4, 0, -3), (0, 2.2, -3), (0, -1.2, -2.5)],
                [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (1, 4), (2, 4)]),
    "bomber": ([(-3, -2, -4), (3, -2, -4), (3, 2, -4), (-3, 2, -4),
                (-3, -2, 4), (3, -2, 4), (3, 2, 4), (-3, 2, 4), (0, 0, 7)],
               [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                (0, 4), (1, 5), (2, 6), (3, 7), (4, 8), (5, 8), (6, 8), (7, 8)]),
    "ace": ([(0, 0, 6), (0, 0, -4), (-5, 0, 0), (5, 0, 0), (0, 3, 0), (0, -2.5, 0)],
            [(0, 2), (0, 3), (0, 4), (0, 5), (1, 2), (1, 3), (1, 4), (1, 5),
             (2, 4), (4, 3), (3, 5), (5, 2)]),
    "carrier": ([(-4, -3, -14), (4, -3, -14), (4, 3, -14), (-4, 3, -14),
                 (-4, -3, 14), (4, -3, 14), (4, 3, 14), (-4, 3, 14),
                 (0, 7, -6), (0, 3, -10), (0, 3, -1)],
                [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                 (0, 4), (1, 5), (2, 6), (3, 7), (8, 9), (8, 10), (9, 10)]),
    "pickup": ([(-2, 0, 0), (2, 0, 0), (0, 2, 0), (0, -2, 0), (0, 0, 2), (0, 0, -2)],
               [(0, 2), (0, 3), (1, 2), (1, 3), (4, 0), (4, 1), (4, 2), (4, 3),
                (5, 0), (5, 1), (5, 2), (5, 3)]),
}

KINDS = {  # hp, speed, fire cooldown, bolt speed, bolt dmg, color, bounty
    "fighter": (3, 0.85, 55, 3.2, 1, 8, 8),
    "bomber": (8, 0.55, 80, 2.3, 2, 9, 15),
    "ace": (5, 1.05, 38, 3.5, 1, 14, 20),
    "carrier": (70, 0.12, 70, 2.2, 2, 8, 60),
}

BLOCK_FONT = {
    "S": (".###", "#...", ".##.", "...#", "...#", "###."),
    "T": ("####", ".##.", ".##.", ".##.", ".##.", ".##."),
    "A": (".##.", "#..#", "#..#", "####", "#..#", "#..#"),
    "R": ("###.", "#..#", "#..#", "###.", "#.#.", "#..#"),
    "L": ("#...", "#...", "#...", "#...", "#...", "####"),
    "N": ("#..#", "##.#", "##.#", "#.##", "#.##", "#..#"),
    "C": (".###", "#...", "#...", "#...", "#...", ".###"),
    "E": ("####", "#...", "###.", "#...", "#...", "####"),
}


def block_text(text, x, y, cell, col):
    for ch in text:
        g = BLOCK_FONT.get(ch)
        if g:
            for gy, row in enumerate(g):
                for gx, c in enumerate(row):
                    if c == "#":
                        pyxel.rect(x + gx * cell, y + gy * cell, cell, cell, col)
        x += 5 * cell


def norm(v):
    d = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1e-6
    return [v[0] / d, v[1] / d, v[2] / d]


def dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


class Ship:
    def __init__(self, kind, pos, scale=1.0):
        self.kind = kind
        self.pos = list(pos)
        hp, spd, cd, _, _, _, _ = KINDS[kind]
        self.hp, self.spd = hp, spd
        self.vel = [0, 0, -self.spd]
        self.cd = random.randint(20, cd)
        self.state, self.t = "pursue", 0
        self.scale = scale
        self.dodged = set()

    def verts(self):
        vx, vz = self.vel[0], self.vel[2]
        yaw = math.atan2(vx, vz)
        pitch = math.atan2(self.vel[1], math.hypot(vx, vz) or 1e-6)
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        out = []
        for x, y, z in MODELS["carrier" if self.kind == "carrier" else self.kind][0]:
            x, y, z = x * self.scale, y * self.scale, z * self.scale
            y, z = y * cp - z * sp, y * sp + z * cp
            x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
            out.append((x + self.pos[0], y + self.pos[1], z + self.pos[2]))
        return out


class Roid:
    def __init__(self, pos, scale):
        self.pos = list(pos)
        self.scale = scale
        self.hp = 2
        self.vel = [random.uniform(-0.2, 0.2) for _ in range(3)]
        self.model = []
        for _ in range(8):
            v = norm([random.uniform(-1, 1) for _ in range(3)])
            r = scale * random.uniform(0.7, 1.3)
            self.model.append((v[0] * r, v[1] * r, v[2] * r))
        self.edges = [(i, (i + 1) % 8) for i in range(8)] + \
                     [(i, (i + 3) % 8) for i in range(0, 8, 2)]

    def verts(self):
        return [(x + self.pos[0], y + self.pos[1], z + self.pos[2])
                for x, y, z in self.model]


class App:
    def __init__(self):
        pyxel.init(W, H, title="starlance", fps=30, quit_key=pyxel.KEY_NONE)
        pyxel.mouse(False)
        pyxel.colors[:] = PALETTE
        self.make_sounds()
        self.new_run()
        self.state = "title"

    def run(self):
        pyxel.run(self.update, self.draw)

    def make_sounds(self):
        s = pyxel.sounds
        s[0].set("a3a2", "nn", "42", "ff", 4)            # laser
        s[1].set("c3", "n", "3", "f", 5)                 # spark
        s[2].set("f1c1", "nn", "75", "ff", 16)           # explosion
        s[3].set("g3c4", "tt", "44", "nn", 6)            # lock
        s[4].set("c2g2", "pn", "54", "ff", 8)            # missile away
        s[5].set("c3e3", "tt", "44", "nn", 6)            # pickup
        s[6].set("f1f1", "nn", "64", "ff", 9)            # shields hit
        s[7].set("c3g3c4", "ttt", "444", "nnn", 7)       # buy / jump

    # -- run state ---------------------------------------------------------
    def new_run(self):
        self.pos = [0.0, 0.0, 0.0]
        self.yaw, self.pitch = 0.0, 0.0
        self.speed = 0.9
        self.turn = 0.042
        self.hull, self.max_hull = 8, 8
        self.shield, self.max_shield = 3, 3
        self.heat, self.overheat = 0.0, False
        self.missiles, self.max_missiles = 3, 6
        self.credits = 0
        self.laser_dmg = 1
        self.modules = set()
        self.node = 1
        self.kills = 0
        self.earned = 0
        self.stars = [[random.uniform(-120, 120) for _ in range(3)] for _ in range(70)]
        self.enemies = []
        self.roids = []
        self.bolts = []
        self.missiles_fly = []
        self.pickups = []
        self.debris = []
        self.sparks = []
        self.target = None
        self.lock_t = 0
        self.locked = False
        self.overdrive = 0
        self.fire_fx = 0
        self.hit_t = -99
        self.regen_t = 0
        self.flash = 0
        self.shake = 0.0
        self.msg, self.msg_t = "", 0
        self.mission = None
        self.clear_t = 0
        self.wave = None
        self.salvage = 0
        self.anim_t = 0
        self.choices = self.gen_choices()
        self.sel = 0

    def say(self, text):
        self.msg, self.msg_t = text, 90

    # -- the sector map ----------------------------------------------------
    def gen_choices(self):
        if self.node >= JUMPS:
            return [{"kind": "boss", "label": "THE CARRIER", "threat": 3,
                     "bonus": 0, "desc": "end of the line. burn it down."}]
        pool = ["patrol", "salvage"]
        if self.node >= 3:
            pool.append("ambush")
        if self.node >= 5:
            pool.append("elite")
        out = []
        for kind in random.sample(pool, min(2 + (self.node > 2), len(pool))):
            n = self.node
            out.append({
                "patrol": {"kind": kind, "label": "pirate patrol",
                           "threat": 1, "bonus": 20 + n * 4,
                           "desc": "a few fighters on a lazy sweep"},
                "salvage": {"kind": kind, "label": "belt salvage",
                            "threat": 1, "bonus": 14 + n * 3,
                            "desc": "crack rocks, scoop 4 crystals. raiders lurk"},
                "ambush": {"kind": kind, "label": "pirate ambush",
                           "threat": 2, "bonus": 32 + n * 5,
                           "desc": "they know you are coming. two waves"},
                "elite": {"kind": kind, "label": "ace hunters",
                          "threat": 3, "bonus": 48 + n * 6,
                          "desc": "fast movers and a heavy bomber"},
            }[kind])
        return out

    def start_mission(self, choice):
        self.state = "fly"
        self.mission = choice
        self.enemies = []
        self.roids = []
        self.bolts = []
        self.missiles_fly = []
        self.pickups = []
        self.wave = None
        self.salvage = 0
        self.clear_t = 0
        n = self.node
        k = choice["kind"]
        if k == "patrol":
            self.spawn_ships("fighter", 3 + n // 3)
        elif k == "salvage":
            for _ in range(8):
                self.roids.append(Roid(self.rand_spot(40, 110),
                                       random.uniform(2.2, 4.0)))
            self.spawn_ships("fighter", 2)
        elif k == "ambush":
            self.spawn_ships("fighter", 3)
            self.wave = ["fighter", "fighter"] + (["ace"] if n >= 5 else [])
        elif k == "elite":
            self.spawn_ships("ace", 2)
            self.spawn_ships("bomber", 1 + (n >= 7))
        else:
            boss = Ship("carrier", self.rand_spot(120, 150), 2.4)
            boss.hp = 70
            self.enemies.append(boss)
            self.spawn_ships("fighter", 2)
            self.spawn_ships("bomber", 1)
        self.say(choice["label"] + " -- " +
                 ("collect 4 crystals" if k == "salvage" else "clear hostiles"))
        pyxel.play(3, 7)

    def rand_spot(self, lo, hi):
        f = self.facing()                           # contacts ahead, mostly
        v = norm([f[0] + random.uniform(-0.8, 0.8),
                  f[1] + random.uniform(-0.45, 0.45),
                  f[2] + random.uniform(-0.8, 0.8)])
        d = random.uniform(lo, hi)
        return [self.pos[i] + v[i] * d for i in range(3)]

    def spawn_ships(self, kind, count):
        for _ in range(int(count)):
            s = Ship(kind, self.rand_spot(90, 140))
            if self.node >= 4 and kind == "fighter":
                s.hp += 1
            self.enemies.append(s)

    # -- 3d helpers ----------------------------------------------------------
    def cam(self, p):
        dx = p[0] - self.pos[0]
        dy = p[1] - self.pos[1]
        dz = p[2] - self.pos[2]
        cy_, sy_ = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        x1 = dx * cy_ - dz * sy_
        z1 = dx * sy_ + dz * cy_
        y2 = dy * cp - z1 * sp
        z2 = dy * sp + z1 * cp
        return x1, y2, z2

    def project(self, p):
        x, y, z = self.cam(p)
        if z < 0.4:
            return None
        return CX + x * FOV / z, CY - y * FOV / z, z

    def facing(self):
        cp = math.cos(self.pitch)
        return [math.sin(self.yaw) * cp, math.sin(self.pitch),
                math.cos(self.yaw) * cp]

    # -- update --------------------------------------------------------------
    def update(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.new_run()
            self.state = "map"
        if self.state == "title":
            if pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) \
                    or pyxel.btnp(pyxel.KEY_RETURN):
                self.state = "map"
                pyxel.play(3, 7)
        elif self.state == "map":
            self.update_map()
        elif self.state == "fly":
            self.update_fly()
        elif self.state == "shop":
            self.update_shop()
        elif self.state == "winanim":
            self.anim_t += 1
            self.update_world(combat=False)
            if self.anim_t > 150:
                self.state = "win"
        if self.msg_t > 0:
            self.msg_t -= 1
        self.shake *= 0.8
        self.flash = max(0, self.flash - 1)

    def update_map(self):
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
            self.sel = max(0, self.sel - 1)
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
            self.sel = min(len(self.choices) - 1, self.sel + 1)
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE) or \
                pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.start_mission(self.choices[self.sel])

    # -- flying ----------------------------------------------------------------
    def update_fly(self):
        mx = (pyxel.mouse_x - CX) / CX
        my = (pyxel.mouse_y - CY) / CY
        if abs(mx) > 0.06:
            self.yaw += mx * self.turn
        if abs(my) > 0.06:
            self.pitch = max(-1.45, min(1.45, self.pitch - my * self.turn))
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A):
            self.yaw -= self.turn
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D):
            self.yaw += self.turn
        if pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_W):
            self.pitch = min(1.45, self.pitch + self.turn)
        if pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.KEY_S):
            self.pitch = max(-1.45, self.pitch - self.turn)
        boost = pyxel.btn(pyxel.KEY_SHIFT)
        spd = self.speed * (1.7 if boost else 1.0)
        f = self.facing()
        for i in range(3):
            self.pos[i] += f[i] * spd

        firing = pyxel.btn(pyxel.KEY_SPACE) or pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
        period = 3 if self.overdrive else 5
        if firing and not self.overheat and pyxel.frame_count % period == 0:
            self.fire_laser()
        self.heat = max(0.0, self.heat - 1.7)
        if self.overheat and self.heat < 50:
            self.overheat = False
            self.say("lasers back online")
        if self.overdrive:
            self.overdrive -= 1

        self.update_lock()
        if pyxel.btnp(pyxel.KEY_M) or pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT):
            self.fire_missile()

        self.update_world(combat=True)

        if self.regen_t > 0:
            self.regen_t -= 1
        elif pyxel.frame_count - self.hit_t > 75 and self.shield < self.max_shield:
            self.shield += 1
            self.regen_t = 55

        if self.mission["kind"] == "salvage" and not self.roids and \
                self.salvage < 4:
            for _ in range(2):                      # the belt drifts back in
                self.roids.append(Roid(self.rand_spot(50, 100),
                                       random.uniform(2.8, 4.0)))
        done = not self.enemies if self.mission["kind"] != "salvage" else \
            self.salvage >= 4
        if done:
            self.clear_t += 1
            if self.clear_t == 1:
                bonus = self.mission["bonus"]
                self.credits += bonus
                self.earned += bonus
                if self.mission["kind"] == "boss":
                    self.state = "winanim"
                    self.anim_t = 0
                    return
                self.say("sector clear. bonus %d cr. jumping..." % bonus)
                pyxel.play(3, 2)
            if self.clear_t > 80:
                pyxel.play(3, 7)
                self.node += 1
                self.market = random.uniform(0.7, 1.3)
                self.shop_items = self.gen_shop()
                self.sel = 0
                self.state = "shop"

    def update_world(self, combat):
        for e in list(self.enemies):
            self.ai(e, combat)
        for r in self.roids:
            for i in range(3):
                r.pos[i] += r.vel[i]
        for b in list(self.bolts):
            hit = False
            for _ in range(2):                      # substep: no tunneling
                for i in range(3):
                    b[0][i] += b[1][i] * 0.5
                if dist(b[0], self.pos) < 2.6:
                    hit = True
                    break
            b[2] -= 1
            if hit or b[2] <= 0:
                self.bolts.remove(b)
                if hit:
                    self.player_hit(b[3])
        for m in list(self.missiles_fly):
            t = m["target"]
            if t in self.enemies:
                want = norm([t.pos[i] - m["pos"][i] for i in range(3)])
                v = norm([m["vel"][i] * 0.82 + want[i] * 0.18 for i in range(3)])
                m["vel"] = [c * 2.6 for c in v]
                if t.kind == "ace" and dist(m["pos"], t.pos) < 20 and \
                        id(m) not in t.dodged and random.random() < 0.5:
                    t.dodged.add(id(m))
                    perp = norm([random.uniform(-1, 1) for _ in range(3)])
                    t.vel = [t.vel[i] + perp[i] * 1.6 for i in range(3)]
            for i in range(3):
                m["pos"][i] += m["vel"][i]
            m["trail"].append(list(m["pos"]))
            del m["trail"][:-7]
            m["fuel"] -= 1
            if t in self.enemies and dist(m["pos"], t.pos) < 3.5 + t.scale:
                self.damage(t, 14 if t.kind == "carrier" else 8)
                self.boom_at(m["pos"], 9)
                self.missiles_fly.remove(m)
            elif m["fuel"] <= 0:
                self.boom_at(m["pos"], 5)
                self.missiles_fly.remove(m)
        for p in list(self.pickups):
            for i in range(3):
                p["pos"][i] += p["vel"][i]
            rad = 5 * (3 if "magscoop" in self.modules else 1)
            if dist(p["pos"], self.pos) < rad:
                self.collect(p)
                self.pickups.remove(p)
        for d in list(self.debris):
            for seg in d[0]:
                for pt in (seg[0], seg[1]):
                    for i in range(3):
                        pt[i] += d[1][i]
            d[2] -= 1
            if d[2] <= 0:
                self.debris.remove(d)
        for s in list(self.sparks):
            s[0] += s[2]
            s[1] += s[3]
            s[4] -= 1
            if s[4] <= 0:
                self.sparks.remove(s)
        if self.wave and len(self.enemies) <= 1:
            for kind in self.wave:
                self.spawn_ships(kind, 1)
            self.wave = None
            self.say("second wave on scope")

    def ai(self, e, combat):
        to_p = [self.pos[i] - e.pos[i] for i in range(3)]
        d = dist(e.pos, self.pos)
        if e.kind == "carrier":
            want = norm(to_p)
            e.vel = [e.vel[i] * 0.97 + want[i] * 0.01 for i in range(3)]
            e.t += 1
            if e.t % 260 == 0 and combat and \
                    sum(s.kind == "fighter" for s in self.enemies) < 3:
                f = Ship("fighter", [e.pos[0], e.pos[1] - 6, e.pos[2]])
                self.enemies.append(f)
                self.say("the carrier scrambles a fighter")
        else:
            if e.state == "pursue":
                want = norm(to_p)
                k = 0.10 if e.kind == "ace" else 0.07
                e.vel = [e.vel[i] * (1 - k) + want[i] * e.spd * k for i in range(3)]
                if e.kind == "ace":
                    e.t += 1
                    side = math.sin(e.t * 0.15) * 0.35
                    e.vel[0] += side * math.cos(self.yaw)
                    e.vel[2] += side * -math.sin(self.yaw)
                if d < 20:
                    e.state = "break"
                    e.t = random.randint(45, 85)
                    e.bdir = norm([random.uniform(-1, 1) for _ in range(3)])
            else:
                e.vel = [e.vel[i] * 0.92 + e.bdir[i] * e.spd * 0.10
                         for i in range(3)]
                e.t -= 1
                if e.t <= 0:
                    e.state = "pursue"
            v = norm(e.vel)
            sp = min(e.spd, 1.4)
            e.vel = [c * sp for c in norm(e.vel)] if d > 1 else e.vel
            aim = norm(to_p)
            align = sum(v[i] * aim[i] for i in range(3))
            e.cd -= 1
            if combat and e.cd <= 0 and d < 95 and align > 0.9:
                _, _, cd, bspd, bdmg, _, _ = KINDS[e.kind]
                spread = [random.uniform(-1.6, 1.6) for _ in range(3)]
                bv = norm([self.pos[i] + spread[i] - e.pos[i] for i in range(3)])
                self.bolts.append([list(e.pos), [c * bspd for c in bv], 130, bdmg])
                e.cd = cd
        for i in range(3):
            e.pos[i] += e.vel[i]
        if e.kind == "carrier":
            e.cd -= 1
            if combat and e.cd <= 0 and d < 130:
                bv = norm([self.pos[i] - e.pos[i] + random.uniform(-2, 2)
                           for i in range(3)])
                self.bolts.append([list(e.pos), [c * 2.2 for c in bv], 170, 2])
                e.cd = 70

    # -- weapons -----------------------------------------------------------------
    def fire_laser(self):
        self.heat += 16
        if self.heat >= 100:
            self.overheat = True
            self.say("LASERS OVERHEATED")
        self.fire_fx = 2
        pyxel.play(2, 0)
        best, bz = None, 1e9
        for e in self.enemies + self.roids:
            pr = self.project(e.pos)
            if not pr:
                continue
            sx, sy, z = pr
            if z > 140:
                continue
            r = max(5, e.scale * FOV / z * (4 if isinstance(e, Ship) else 1))
            if math.hypot(sx - CX, sy - CY) < r * 0.8 + 4 and z < bz:
                best, bz = e, z
        if best:
            pr = self.project(best.pos)
            self.sparks += [[pr[0], pr[1], random.uniform(-1.5, 1.5),
                             random.uniform(-1.5, 1.5), random.randint(4, 10), 7]
                            for _ in range(4)]
            pyxel.play(1, 1)
            self.damage(best, self.laser_dmg)

    def damage(self, e, n):
        e.hp -= n
        if e.hp > 0:
            return
        if isinstance(e, Roid):
            self.roids.remove(e)
            if e.scale > 2.6:
                for _ in range(2):
                    r = Roid([e.pos[i] + random.uniform(-2, 2) for i in range(3)],
                             e.scale * 0.55)
                    self.roids.append(r)
            elif random.random() < 0.6:
                self.drop(e.pos, "crystal")
            self.boom(e.verts(), e.edges, e.pos, 6)
            return
        self.enemies.remove(e)
        self.kills += 1
        bounty = KINDS[e.kind][6]
        self.drop(e.pos, "credit", bounty // 2)
        if random.random() < 0.22:
            self.drop(e.pos, random.choice(("missile", "shield", "over")))
        if "autoloader" in self.modules:
            self.missiles = min(self.max_missiles, self.missiles + 1)
        model = MODELS["carrier" if e.kind == "carrier" else e.kind][1]
        self.boom(e.verts(), model, e.pos, 12 if e.kind == "carrier" else 8)
        if self.target is e:
            self.target, self.lock_t, self.locked = None, 0, False

    def boom(self, verts, edges, pos, power):
        pyxel.play(2, 2)
        self.shake = min(5, power * 0.5)
        segs = []
        for a, b in edges:
            p1, p2 = list(verts[a]), list(verts[b])
            mid = [(p1[i] + p2[i]) / 2 for i in range(3)]
            v = [(mid[i] - pos[i]) * 0.06 + random.uniform(-0.2, 0.2)
                 for i in range(3)]
            segs.append(([list(p1), list(p2)], v))
        for seg, v in segs:
            self.debris.append([[seg], v, random.randint(25, 45)])

    def boom_at(self, pos, power):
        pyxel.play(2, 2)
        pr = self.project(pos)
        if pr:
            self.sparks += [[pr[0], pr[1], random.uniform(-2, 2),
                             random.uniform(-2, 2), random.randint(6, 14),
                             random.choice((7, 9, 10))] for _ in range(power)]

    def drop(self, pos, kind, val=0):
        self.pickups.append({
            "pos": [pos[i] + random.uniform(-2, 2) for i in range(3)],
            "vel": [random.uniform(-0.08, 0.08) for _ in range(3)],
            "kind": kind, "val": val or random.randint(4, 9), "t": 0,
        })

    def collect(self, p):
        pyxel.play(3, 5)
        k = p["kind"]
        if k == "credit":
            self.credits += p["val"]
            self.earned += p["val"]
            self.say("+%d cr" % p["val"])
        elif k == "crystal":
            self.salvage += 1
            self.credits += 8
            self.earned += 8
            self.say("salvage crystal %d/4" % self.salvage)
        elif k == "missile":
            self.missiles = min(self.max_missiles, self.missiles + 2)
            self.say("+2 missiles")
        elif k == "shield":
            self.shield = self.max_shield
            self.say("shields restored")
        else:
            self.overdrive = 240
            self.say("LASER OVERDRIVE")

    def update_lock(self):
        rate = 2 if "targeting" in self.modules else 1
        best, bd = None, 1e9
        for e in self.enemies:
            pr = self.project(e.pos)
            if not pr:
                continue
            sx, sy, z = pr
            r = math.hypot(sx - CX, sy - CY)
            if r < 30 and z < bd:
                best, bd = e, z
        if best is self.target and best is not None:
            self.lock_t += rate
            if self.lock_t >= 36 and not self.locked:
                self.locked = True
                pyxel.play(3, 3)
        else:
            self.target = best
            self.lock_t = 0
            self.locked = False

    def fire_missile(self):
        if self.missiles <= 0:
            self.say("missile bay empty")
            return
        if not self.locked or self.target not in self.enemies:
            self.say("no lock")
            return
        self.missiles -= 1
        f = self.facing()
        pyxel.play(3, 4)
        self.missiles_fly.append({
            "pos": [self.pos[i] + f[i] * 3 for i in range(3)],
            "vel": [c * 2.6 for c in f],
            "target": self.target, "fuel": 240,
            "trail": [],
        })

    def player_hit(self, dmg):
        self.hit_t = pyxel.frame_count
        self.flash = 6
        self.shake = 3
        if self.shield > 0:
            self.shield -= 1
            pyxel.play(3, 6)
            return
        self.hull -= dmg
        pyxel.play(3, 6)
        if self.hull <= 0:
            self.boom_at(self.pos, 14)
            self.state = "dead"

    # -- shop ------------------------------------------------------------------
    def gen_shop(self):
        m = self.market
        items = [
            ["patch hull +3", int(16 * m), "hull"],
            ["missile rack +2", int(14 * m), "missile"],
            ["laser focus +1 dmg", int(42 * m), "laser"],
            ["shield cell +1", int(46 * m), "shieldcap"],
            ["engine tune +turn", int(34 * m), "engine"],
        ]
        for mod, price, label in (("magscoop", 44, "mag-scoop: triple pickup range"),
                                  ("targeting", 50, "targeting comp: fast lock"),
                                  ("autoloader", 58, "autoloader: +1 missile per kill"),
                                  ("plating", 52, "plating: +3 max hull")):
            if mod not in self.modules:
                items.append([label, int(price * m), mod])
        items.append(["depart -- jump to the next beacon", 0, "depart"])
        return items

    def update_shop(self):
        if pyxel.btnp(pyxel.KEY_UP, 12, 4) or pyxel.btnp(pyxel.KEY_W, 12, 4):
            self.sel = max(0, self.sel - 1)
        if pyxel.btnp(pyxel.KEY_DOWN, 12, 4) or pyxel.btnp(pyxel.KEY_S, 12, 4):
            self.sel = min(len(self.shop_items) - 1, self.sel + 1)
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            label, cost, key = self.shop_items[self.sel]
            if key == "depart":
                self.choices = self.gen_choices()
                self.sel = 0
                self.state = "map"
                pyxel.play(3, 7)
                return
            if self.credits < cost:
                self.say("not enough credits")
                return
            self.credits -= cost
            pyxel.play(3, 7)
            if key == "hull":
                self.hull = min(self.max_hull, self.hull + 3)
            elif key == "missile":
                self.missiles = min(self.max_missiles, self.missiles + 2)
            elif key == "laser":
                self.laser_dmg += 1
            elif key == "shieldcap":
                self.max_shield += 1
                self.shield = self.max_shield
            elif key == "engine":
                self.turn += 0.007
            else:
                self.modules.add(key)
                if key == "plating":
                    self.max_hull += 3
                    self.hull += 3
            self.shop_items = self.gen_shop()
            self.say("purchased: " + label)

    # -- drawing -----------------------------------------------------------------
    def draw_wire(self, verts, edges, col, far_dim=True):
        pts = [self.project(v) for v in verts]
        for a, b in edges:
            pa, pb = pts[a], pts[b]
            if not pa or not pb:
                continue
            c = col
            if far_dim and (pa[2] + pb[2]) * 0.5 > 95:
                c = 1
            pyxel.line(pa[0], pa[1], pb[0], pb[1], c)

    def draw_space(self):
        pyxel.cls(0)
        for s in self.stars:
            rel = [(s[i] - self.pos[i] + 120) % 240 - 120 for i in range(3)]
            pr = self.project([self.pos[i] + rel[i] for i in range(3)])
            if pr:
                pyxel.pset(pr[0], pr[1], 7 if pr[2] < 60 else 13 if pr[2] < 100 else 1)
        for p in self.pickups:
            p["t"] += 1
            a = p["t"] * 0.08
            ca, sa = math.cos(a), math.sin(a)
            verts = [(x * ca + z * sa + p["pos"][0], y + p["pos"][1],
                      -x * sa + z * ca + p["pos"][2])
                     for x, y, z in MODELS["pickup"][0]]
            col = {"credit": 10, "crystal": 10, "missile": 12,
                   "shield": 3, "over": 14}[p["kind"]]
            self.draw_wire(verts, MODELS["pickup"][1], col, far_dim=False)
        for r in self.roids:
            self.draw_wire(r.verts(), r.edges, 6)
        for e in self.enemies:
            model = MODELS["carrier" if e.kind == "carrier" else e.kind][1]
            self.draw_wire(e.verts(), model, KINDS[e.kind][5])
        for segs, _, ttl in self.debris:
            for seg in segs:
                pa = self.project(seg[0])
                pb = self.project(seg[1])
                if pa and pb:
                    pyxel.line(pa[0], pa[1], pb[0], pb[1], 9 if ttl > 30 else 5)
        for b in self.bolts:
            pr = self.project(b[0])
            if pr:
                tail = self.project([b[0][i] - b[1][i] * 1.5 for i in range(3)])
                col = 9 if b[3] > 1 else 8
                if tail:
                    pyxel.line(pr[0], pr[1], tail[0], tail[1], col)
                pyxel.pset(pr[0], pr[1], 10)
        for m in self.missiles_fly:
            pts = [self.project(p) for p in m["trail"]]
            pts = [p for p in pts if p]
            for i in range(len(pts) - 1):
                pyxel.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], 13)
            pr = self.project(m["pos"])
            if pr:
                pyxel.circ(pr[0], pr[1], 1, 10 if pyxel.frame_count % 2 else 9)
        for x, y, _, _, life, col in self.sparks:
            pyxel.pset(x, y, col if life > 4 else 5)
        if self.fire_fx > 0:
            self.fire_fx -= 1
            tx, ty = CX, CY
            if self.target:
                pr = self.project(self.target.pos)
                if pr and math.hypot(pr[0] - CX, pr[1] - CY) < 24:
                    tx, ty = pr[0], pr[1]
            pyxel.line(26, H - 4, tx, ty, 15)
            pyxel.line(W - 26, H - 4, tx, ty, 15)
            pyxel.circ(tx, ty, 1, 7)

    def draw_hud(self):
        pyxel.text(4, 4, "cr %d" % self.credits, 10)
        pyxel.text(4, 12, "jump %d/%d" % (self.node, JUMPS), 13)
        for i in range(self.missiles):
            pyxel.tri(54 + i * 6, 10, 52 + i * 6, 14, 56 + i * 6, 14, 12)
        pyxel.text(W - 70, 4, self.mission["label"][:17] if self.mission else "", 13)
        obj = ("crystals %d/4" % self.salvage) if self.mission and \
            self.mission["kind"] == "salvage" else "hostiles %d" % len(self.enemies)
        pyxel.text(W - 70, 12, obj, 8 if self.enemies else 3)

        pyxel.text(4, H - 22, "shd", 12)
        pyxel.rect(18, H - 21, 30, 3, 1)
        if self.max_shield:
            pyxel.rect(18, H - 21, int(30 * self.shield / self.max_shield), 3, 12)
        pyxel.text(4, H - 14, "hul", 3)
        pyxel.rect(18, H - 13, 30, 3, 1)
        frac = max(0, self.hull / self.max_hull)
        pyxel.rect(18, H - 13, int(30 * frac), 3, 3 if frac > 0.4 else 8)
        pyxel.text(W - 48, H - 22, "heat", 9)
        pyxel.rect(W - 28, H - 21, 24, 3, 1)
        pyxel.rect(W - 28, H - 21, int(24 * min(1, self.heat / 100)), 3,
                   8 if self.overheat else 9)
        if self.overdrive:
            pyxel.text(W - 48, H - 14, "OVRD", 14)

        rx, ry, rr = CX, H - 16, 13                  # the scanner
        pyxel.circb(rx, ry, rr, 2)
        pyxel.pset(rx, ry - rr, 3)
        for e in self.enemies:
            x1, _, z2 = self.cam(e.pos)
            d = math.hypot(x1, z2) or 1
            k = rr * min(1, d / 150) / d
            pyxel.pset(rx + x1 * k, ry - z2 * k, KINDS[e.kind][5])
        for p in self.pickups:
            x1, _, z2 = self.cam(p["pos"])
            d = math.hypot(x1, z2) or 1
            k = rr * min(1, d / 150) / d
            pyxel.pset(rx + x1 * k, ry - z2 * k, 10)

        pyxel.line(CX - 7, CY, CX - 3, CY, 3)        # crosshair
        pyxel.line(CX + 3, CY, CX + 7, CY, 3)
        pyxel.line(CX, CY - 7, CX, CY - 3, 3)
        pyxel.line(CX, CY + 3, CX, CY + 7, 3)
        pyxel.pset(pyxel.mouse_x, pyxel.mouse_y, 13)

        if self.target in self.enemies:
            pr = self.project(self.target.pos)
            if pr:
                r = max(6, int(self.target.scale * FOV / pr[2] * 3))
                col = 8 if self.locked else 13
                for dx, dy in ((-r, -r), (r - 4, -r), (-r, r - 1), (r - 4, r - 1)):
                    pyxel.line(pr[0] + dx, pr[1] + dy, pr[0] + dx + 4,
                               pr[1] + dy, col)
                if self.locked:
                    if pyxel.frame_count % 10 < 6:
                        pyxel.text(pr[0] - 7, pr[1] - r - 8, "LOCK", 8)
                else:
                    pyxel.rect(pr[0] - 10, pr[1] + r + 3,
                               int(20 * min(1, self.lock_t / 36)), 1, 13)
        if self.flash:
            pyxel.rectb(0, 0, W, H, 8)
            pyxel.rectb(1, 1, W - 2, H - 2, 8)
        if self.msg_t > 0:
            pyxel.text(CX - len(self.msg) * 2, H - 34, self.msg, 7)

    def draw_panel(self, title):
        pyxel.rect(16, 14, W - 32, H - 28, 0)
        pyxel.rectb(16, 14, W - 32, H - 28, 2)
        pyxel.rectb(17, 15, W - 34, H - 30, 1)
        pyxel.text(24, 20, title, 10)
        pyxel.line(24, 27, W - 24, 27, 2)

    def draw(self):
        if self.shake > 0.5:
            pyxel.camera(random.uniform(-self.shake, self.shake),
                         random.uniform(-self.shake, self.shake))
        else:
            pyxel.camera()
        if self.state == "title":
            self.draw_title()
            return
        self.draw_space()
        pyxel.camera()
        if self.state == "fly":
            self.draw_hud()
        elif self.state == "map":
            self.draw_map()
        elif self.state == "shop":
            self.draw_shop()
        elif self.state == "winanim":
            if self.anim_t % 8 < 4:
                t = "SECTOR LIBERATED"
                pyxel.text(CX - len(t) * 2, 60, t, 10)
        elif self.state in ("dead", "win"):
            self.draw_end()
        if self.state != "fly" and self.msg_t > 0:
            pyxel.text(CX - len(self.msg) * 2, H - 10, self.msg, 7)

    def draw_title(self):
        pyxel.cls(0)
        t = pyxel.frame_count
        for s in self.stars:
            x = (s[0] * 9 + t) % W
            y = (s[1] * 7) % H
            pyxel.pset(x, y, 1 if int(s[2]) % 3 else 13)
        yaw = t * 0.03
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        verts = []
        for x, y, z in MODELS["fighter"][0]:
            x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
            s = 5.5
            verts.append((CX + x * s, 116 + y * s - z * 1.5, 0))
        for a, b in MODELS["fighter"][1]:
            pyxel.line(verts[a][0], verts[a][1], verts[b][0], verts[b][1], 15)
        block_text("STARLANCE", CX - 89, 34, 2, 1)
        block_text("STARLANCE", CX - 90, 33, 2, (15, 12, 7)[(t // 8) % 3])
        pyxel.text(CX - 66, 52, "eight jumps. one carrier. no refunds.", 13)
        if (t // 14) % 2:
            pyxel.text(CX - 32, 150, "click / space to fly", 7)
        pyxel.text(CX - 70, 162, "mouse steers  space lasers  m missile", 5)
        pyxel.text(3, H - 7, "v1", 5)
        pyxel.text(W - 60, H - 7, "pyxel arcade", 5)

    def draw_map(self):
        self.draw_panel("jump %d of %d -- choose a beacon" % (self.node, JUMPS))
        pyxel.text(24, 32, "hull %d/%d  shield %d  missiles %d  %d cr" %
                   (self.hull, self.max_hull, self.shield, self.missiles,
                    self.credits), 13)
        n = len(self.choices)
        cw = 62
        x0 = CX - (n * cw + (n - 1) * 8) // 2
        for i, c in enumerate(self.choices):
            x = x0 + i * (cw + 8)
            col = 10 if i == self.sel else 2
            pyxel.rectb(x, 46, cw, 86, col)
            pyxel.text(x + 4, 52, c["label"][:14], 7 if i == self.sel else 13)
            for s in range(c["threat"]):
                pyxel.text(x + 4 + s * 8, 62, "!", 8)
            pyxel.text(x + 4, 74, "bonus", 13)
            pyxel.text(x + 4, 82, "%d cr" % c["bonus"], 10)
            words, line, yy = c["desc"].split(), "", 96
            for w_ in words:
                if len(line) + len(w_) + 1 > 14:
                    pyxel.text(x + 4, yy, line, 5)
                    yy += 7
                    line = w_
                else:
                    line = (line + " " + w_).strip()
            pyxel.text(x + 4, yy, line, 5)
        pyxel.text(CX - 56, 142, "arrows pick  enter / click embark", 5)

    def draw_shop(self):
        self.draw_panel("waystation %d  --  market drift %+d%%" %
                        (self.node, int((self.market - 1) * 100)))
        pyxel.text(W - 70, 20, "%d cr" % self.credits, 10)
        for i, (label, cost, key) in enumerate(self.shop_items):
            y = 34 + i * 11
            sel = i == self.sel
            if sel:
                pyxel.rect(20, y - 2, W - 40, 10, 1)
                pyxel.text(24, y, ">", 10)
            col = 7 if sel else 13
            if cost and cost > self.credits:
                col = 5
            pyxel.text(32, y, label, col)
            if cost:
                pyxel.text(W - 52, y, "%d cr" % cost, 10 if cost <= self.credits else 5)
        pyxel.text(24, H - 22, "up/down + enter", 5)

    def draw_end(self):
        won = self.state == "win"
        self.draw_panel("SECTOR LIBERATED" if won else "lost with all hands")
        head = "the carrier burns. the lanes are free." if won else \
            "your wreck joins the drift."
        pyxel.text(24, 34, head, 10 if won else 8)
        rows = (("jumps made", "%d / %d" % (self.node, JUMPS)),
                ("kills", str(self.kills)),
                ("credits earned", str(self.earned)),
                ("modules", str(len(self.modules))))
        for i, (k, v) in enumerate(rows):
            pyxel.text(30, 52 + i * 11, k, 13)
            pyxel.text(140, 52 + i * 11, v, 7)
        pyxel.text(24, H - 26, "R flies again", 10)


if __name__ == "__main__":
    App().run()
