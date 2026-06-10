"""Undervault -- a room-by-room dungeon dive with depth.

Each room is a stone box seen from the front: a floor three lanes deep,
a torch-lit back wall, doors in the side walls, stairs and hatches in
the floor. Fight down through eight strata and take the Ember Crown.

Controls:  arrows / WASD = step (up-down changes floor lane)
           bump a monster = attack       bump a cracked tile = dig
           T = plant a torch             SPACE = wait
           I inventory   L message log   C character   H help
           click an adjacent tile to step there        R = new delve

Study: lane-based pseudo-3D (three floor strips with converging
widths), pyxel.pal() light banding, a tiny turn scheduler, and
modal UI screens over a paused world.
"""
import random

import pyxel

SW_, SH_ = 240, 180
RW, RD = 10, 3                  # room floor: 10 tiles wide, 3 lanes deep
LEVELS, ROOMS = 8, 5
GOAL_LEVEL = LEVELS - 1

# lane geometry: back lane is narrow and high, front is wide and low
LANE_Y = (96, 119, 145)
LANE_H = (23, 26, 30)
TILE_W = (19, 21, 23)
LANE_X0 = (25, 15, 5)
WALL_Y = 36                     # top of the back wall

PALETTE = [
    0x0A0814, 0x16102A, 0x3A2A1C, 0x6B4530, 0x9A6238, 0x343852,
    0x6E7287, 0xC4C8DA, 0xEF3C63, 0xFF8A3D, 0xFFD23E, 0x20315E,
    0x41A6F6, 0x7A83AB, 0x221A30, 0x33232C,
]
REMAPS = {
    1: ((4, 3), (3, 2), (7, 6), (6, 5), (15, 14), (10, 9), (12, 13),
        (8, 2), (9, 3), (13, 5), (11, 5)),
    0: ((4, 2), (3, 2), (2, 2), (7, 5), (6, 5), (15, 1), (14, 1),
        (10, 5), (9, 5), (12, 5), (13, 5), (8, 5), (11, 1)),
}

THEMES = [  # per two levels: name, wall (lit, mid, dark), floor pair
    ("cellar", (4, 3, 2), (4, 3)),
    ("crypt", (7, 6, 5), (6, 5)),
    ("mines", (3, 2, 5), (4, 2)),
    ("vault", (12, 11, 5), (6, 11)),
]

KINDS = {  # hp, damage, xp, speed flavor
    "rat":      {"hp": 1, "xp": 1},
    "bat":      {"hp": 1, "xp": 1},
    "slime":    {"hp": 3, "xp": 2},
    "skeleton": {"hp": 2, "xp": 2},
}
SPAWN_MIX = [("rat", "bat"), ("skeleton", "bat"), ("rat", "slime"),
             ("skeleton", "slime")]

BLOCK_FONT = {  # 4x6 cells, drawn chunky for the title
    "U": ("#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "N": ("#..#", "##.#", "##.#", "#.##", "#.##", "#..#"),
    "D": ("###.", "#..#", "#..#", "#..#", "#..#", "###."),
    "E": ("####", "#...", "###.", "#...", "#...", "####"),
    "R": ("###.", "#..#", "#..#", "###.", "#.#.", "#..#"),
    "V": ("#..#", "#..#", "#..#", "#..#", ".##.", ".##."),
    "A": (".##.", "#..#", "#..#", "####", "#..#", "#..#"),
    "L": ("#...", "#...", "#...", "#...", "#...", "####"),
    "T": ("####", ".##.", ".##.", ".##.", ".##.", ".##."),
}


def block_text(text, x, y, cell, col):
    for ch in text:
        glyph = BLOCK_FONT.get(ch)
        if glyph:
            for gy, row in enumerate(glyph):
                for gx, c in enumerate(row):
                    if c == "#":
                        pyxel.rect(x + gx * cell, y + gy * cell, cell, cell, col)
        x += 5 * cell


def tile_anchor(x, z):
    """Bottom-center screen point of a floor tile."""
    px = LANE_X0[z] + int((x + 0.5) * TILE_W[z])
    return px, LANE_Y[z] + LANE_H[z] - 3


class Monster:
    def __init__(self, kind, x, z):
        self.kind, self.x, self.z = kind, x, z
        self.hp = KINDS[kind]["hp"]
        self.face = random.choice((-1, 1))
        self.awake = False
        ax, ay = tile_anchor(x, z)
        self.sx, self.sy = float(ax), float(ay)

    def glide(self):
        ax, ay = tile_anchor(self.x, self.z)
        self.sx += (ax - self.sx) * 0.3
        self.sy += (ay - self.sy) * 0.3


class Room:
    def __init__(self, level, index):
        self.level, self.index = level, index
        self.theme = THEMES[min(level // 2, 3)]
        self.visited = False
        self.blocked = set()
        self.stairs_down = None
        self.stairs_up = None
        self.hatches = set()
        self.cracked = set()
        self.sconces = []
        self.props = []
        self.monsters = []
        self.items = {}             # (x, z) -> "potion" | "gold" | "torch"
        self.torches = []           # player-planted
        self.crown = None

    def open_tiles(self):
        out = []
        for z in range(RD):
            for x in range(RW):
                p = (x, z)
                if p in self.blocked or p in self.hatches or p in self.cracked:
                    continue
                if p in (self.stairs_down, self.stairs_up, self.crown):
                    continue
                if p in self.items or any((m.x, m.z) == p for m in self.monsters):
                    continue
                if p in ((0, 1), (RW - 1, 1)):      # keep doorways clear
                    continue
                out.append(p)
        return out

    def furnish(self):
        for _ in range(random.randint(0, 3)):       # pillars
            t = self.open_tiles()
            if t:
                self.blocked.add(random.choice(t))
        if random.random() < 0.7:                   # wall sconces
            for _ in range(random.randint(1, 2)):
                self.sconces.append(random.randint(1, RW - 2))
        for _ in range(random.randint(1, 2)):       # back-wall set dressing
            self.props.append((random.randint(0, RW - 1), random.randrange(3)))
        if random.random() < 0.25:
            t = self.open_tiles()
            if t:
                self.hatches.add(random.choice(t))
        if random.random() < 0.25:
            t = self.open_tiles()
            if t:
                self.cracked.add(random.choice(t))
        n = (1 if self.level else 0) + self.level // 3 + (random.random() < 0.6)
        if self.level == 0 and self.index == 0:
            n = 0                                   # the entry hall is safe
        mix = SPAWN_MIX[min(self.level // 2, 3)]
        for _ in range(int(n)):
            t = self.open_tiles()
            if t:
                x, z = random.choice(t)
                self.monsters.append(Monster(random.choice(mix), x, z))
        for kind, odds in (("potion", 0.35), ("gold", 0.55), ("torch", 0.3)):
            if random.random() < odds:
                t = self.open_tiles()
                if t:
                    self.items[random.choice(t)] = kind

    def solid(self, x, z):
        return not (0 <= x < RW and 0 <= z < RD) or (x, z) in self.blocked

    def monster_at(self, x, z):
        for m in self.monsters:
            if (m.x, m.z) == (x, z):
                return m
        return None


class App:
    def __init__(self):
        pyxel.init(SW_, SH_, title="undervault", fps=30,
                   quit_key=pyxel.KEY_NONE)
        pyxel.mouse(True)
        pyxel.colors[:] = PALETTE
        self.make_sounds()
        self.delve()
        self.screen = "title"

    def run(self):
        pyxel.run(self.update, self.draw)

    def make_sounds(self):
        s = pyxel.sounds
        s[0].set("c2e2", "pp", "44", "ff", 9)            # your hit lands
        s[1].set("f1c1", "nn", "54", "ff", 11)           # you are hit
        s[2].set("c3e3g3", "ttt", "444", "nnn", 8)       # pickup
        s[3].set("g2e2c2", "ppp", "444", "fff", 10)      # descend
        s[4].set("f1f1", "nn", "43", "ff", 7)            # dig
        s[5].set("c3e3g3c4", "tttt", "5555", "nnnn", 7)  # level up
        s[6].set("c2a1f1c1", "pppp", "5554", "ffff", 14) # death
        s[7].set("c4g3", "tt", "33", "nn", 6)            # door

    # -- world generation ----------------------------------------------
    def delve(self):
        self.world = [[Room(lv, i) for i in range(ROOMS)] for lv in range(LEVELS)]
        for lv in range(LEVELS):
            for room in self.world[lv]:
                room.furnish()
            if lv < LEVELS - 1:                     # guarantee a way down
                for i in random.sample(range(ROOMS), random.randint(1, 2)):
                    room = self.world[lv][i]
                    t = room.open_tiles()
                    if t:
                        spot = random.choice(t)
                        room.stairs_down = spot
                        below = self.world[lv + 1][i]
                        t2 = below.open_tiles()
                        below.stairs_up = random.choice(t2) if t2 else (1, 1)
        goal = self.world[GOAL_LEVEL][random.randrange(ROOMS)]
        t = goal.open_tiles()
        goal.crown = random.choice(t) if t else (5, 1)
        t = goal.open_tiles()
        if t:                                       # the crown has a keeper
            goal.monsters.append(Monster("skeleton", *random.choice(t)))

        self.lv, self.ri = 0, 0
        self.room().visited = True
        self.x, self.z = RW // 2, 1
        ax, ay = tile_anchor(self.x, self.z)
        self.sx, self.sy = float(ax), float(ay)
        self.hop = 0.0
        self.face = 1
        self.hearts, self.max_hearts = 3, 3
        self.level, self.xp, self.kills, self.gold = 1, 0, 0, 0
        self.potions, self.packs = 1, 2
        self.turn = 0
        self.shake = 0.0
        self.screen = None
        self.inv_sel = 0
        self.log_off = 0
        self.log = []
        self.say("the undervault swallows your footsteps")
        self.say("somewhere below burns the Ember Crown")

    def room(self):
        return self.world[self.lv][self.ri]

    def say(self, text):
        self.log.append(text)
        del self.log[:-60]

    # -- character ----------------------------------------------------
    def attack_power(self):
        return 1 + self.level // 3

    def gain_xp(self, n):
        self.xp += n
        need = 2 + 2 * self.level
        if self.xp >= need:
            self.xp -= need
            self.level += 1
            self.max_hearts = min(5, self.max_hearts + 1)
            self.hearts = self.max_hearts
            pyxel.play(3, 5)
            self.say("you feel hardened by the dark (level %d)" % self.level)

    def hurt(self, n, why):
        self.hearts -= n
        self.shake = 4
        pyxel.play(3, 1)
        if self.hearts <= 0:
            pyxel.play(3, 6)
            self.say(why)
            self.screen = "dead"

    # -- the player turn ------------------------------------------------
    def try_step(self, dx, dz):
        if dx:
            self.face = 1 if dx > 0 else -1
        room = self.room()
        nx, nz = self.x + dx, self.z + dz

        if nx < 0 or nx >= RW:                       # through a side door
            if nz == self.z and self.z == 1:
                ni = self.ri + (1 if nx >= RW else -1)
                if 0 <= ni < ROOMS:
                    self.ri = ni
                    self.x = 0 if nx >= RW else RW - 1
                    self.room().visited = True
                    pyxel.play(3, 7)
                    self.say("you push through a heavy door")
                    ax, ay = tile_anchor(self.x, self.z)
                    self.sx = ax - 30 * (1 if nx >= RW else -1)
                    self.sy = float(ay)
                    self.end_turn()
                    return
            self.say("cold stone. the way is %s" %
                     ("down" if self.lv < GOAL_LEVEL else "near"))
            return
        if not 0 <= nz < RD:
            return

        m = room.monster_at(nx, nz)
        if m:                                        # bump attack
            m.hp -= self.attack_power()
            m.awake = True
            m.face = -self.face
            pyxel.play(3, 0)
            if m.hp <= 0:
                room.monsters.remove(m)
                self.kills += 1
                self.say("the %s is destroyed" % m.kind)
                self.gain_xp(KINDS[m.kind]["xp"])
            else:
                self.say("you strike the %s" % m.kind)
            self.end_turn()
            return
        if (nx, nz) in room.blocked:
            self.say("a pillar of old stone blocks you")
            return
        if (nx, nz) in room.cracked:                 # dig open a hatch
            room.cracked.discard((nx, nz))
            room.hatches.add((nx, nz))
            pyxel.play(3, 4)
            self.say("your pick opens the cracked floor")
            self.end_turn()
            return

        self.x, self.z = nx, nz
        self.hop = 1.0
        self.after_step()
        self.end_turn()

    def after_step(self):
        room = self.room()
        p = (self.x, self.z)
        item = room.items.pop(p, None)
        if item:
            pyxel.play(3, 2)
            if item == "potion":
                self.potions += 1
                self.say("you pocket a red draught")
            elif item == "torch":
                self.packs += 1
                self.say("you gather a fresh torch")
            else:
                g = random.randint(3, 9)
                self.gold += g
                self.say("you scoop up %d gold" % g)
        if p == room.crown:
            room.crown = None
            self.screen = "winanim"
            self.anim_t = 0
            self.sparks = []
            pyxel.play(3, 5)
            self.say("the Ember Crown is yours")
        elif p == room.stairs_down:
            self.travel(1, "you descend the worn stair")
        elif p == room.stairs_up:
            self.travel(-1, "you climb toward fresher air")
        elif p in room.hatches:
            self.travel(1, "you drop through the hatch", fall=True)

    def travel(self, dlv, text, fall=False):
        self.lv += dlv
        room = self.room()
        room.visited = True
        pyxel.play(3, 3)
        self.say(text)
        spot = room.stairs_up if dlv > 0 and not fall else \
            room.stairs_down if dlv < 0 else None
        if fall or spot is None:
            opts = room.open_tiles()
            spot = random.choice(opts) if opts else (RW // 2, 1)
        self.x, self.z = spot
        ax, ay = tile_anchor(self.x, self.z)
        self.sx = float(ax)
        self.sy = ay - (60 if fall else 12)
        if fall:
            self.hurt(1, "the fall breaks you on the flagstones")
            if self.screen != "dead":
                self.say("you land hard. one heart bleeds away")

    def plant_torch(self):
        room = self.room()
        if self.packs <= 0:
            self.say("no torches left in your pack")
            return
        if (self.x, self.z) in room.torches:
            self.say("a torch already burns here")
            return
        room.torches.append((self.x, self.z))
        self.packs -= 1
        self.say("you plant a torch in the cracks")
        self.end_turn()

    def quaff(self):
        if self.potions <= 0:
            self.say("you have no draughts to drink")
            return
        if self.hearts >= self.max_hearts:
            self.say("you feel hale already")
            return
        self.potions -= 1
        self.hearts = min(self.max_hearts, self.hearts + 2)
        pyxel.play(3, 2)
        self.say("warmth floods back into you")
        self.end_turn()

    # -- monsters --------------------------------------------------------
    def end_turn(self):
        self.turn += 1
        room = self.room()
        for m in list(room.monsters):
            if self.screen == "dead":
                break
            if not m.awake:                          # dozing until you near
                if abs(self.x - m.x) + abs(self.z - m.z) <= 4:
                    m.awake = True
                    self.say("the %s stirs in the dark" % m.kind)
                elif random.random() < 0.4:
                    dx, dz = random.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
                    nx, nz = m.x + dx, m.z + dz
                    if not (room.solid(nx, nz) or room.monster_at(nx, nz)
                            or (nx, nz) == (self.x, self.z)
                            or (nx, nz) in room.hatches
                            or (nx, nz) == room.stairs_down):
                        m.x, m.z = nx, nz
                continue
            steps = 2 if m.kind == "rat" else 1
            if m.kind == "slime" and self.turn % 2:
                steps = 0
            for si in range(steps):
                dx, dz = self.x - m.x, self.z - m.z
                if abs(dx) + abs(dz) == 1:           # adjacent: bite
                    if si > 0:
                        break                        # a sprinting rat can't bite
                    m.face = 1 if dx > 0 else -1 if dx < 0 else m.face
                    self.hurt(1, "the %s tears you down" % m.kind)
                    self.say("the %s strikes you" % m.kind)
                    break
                if m.kind == "bat" and random.random() < 0.5:
                    moves = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                    random.shuffle(moves)
                else:
                    moves = sorted(
                        [(1, 0), (-1, 0), (0, 1), (0, -1)],
                        key=lambda d: abs(self.x - (m.x + d[0])) +
                                      abs(self.z - (m.z + d[1])))
                for sx, sz in moves:
                    nx, nz = m.x + sx, m.z + sz
                    if room.solid(nx, nz) or room.monster_at(nx, nz):
                        continue
                    if (nx, nz) == (self.x, self.z):
                        continue
                    if (nx, nz) in room.hatches or (nx, nz) == room.stairs_down:
                        continue
                    m.x, m.z = nx, nz
                    if sx:
                        m.face = 1 if sx > 0 else -1
                    break

    # -- light -------------------------------------------------------------
    def relight(self):
        if self.screen == "winanim":                 # the vault ignites
            self.light = {(x, z): 9.0 for z in range(RD) for x in range(RW)}
            return
        room = self.room()
        srcs = [(self.x, self.z, 4.6)]
        for x, z in room.torches:
            srcs.append((x, z, 4.4))
        for x in room.sconces:
            srcs.append((x, 0, 5.2))
        flick = 0.25 * pyxel.sin(pyxel.frame_count * 9)
        self.light = {}
        for z in range(RD):
            for x in range(RW):
                best = 0.0
                for sx, sz, rad in srcs:
                    d = max(abs(x - sx), abs(z - sz)) + \
                        0.4 * min(abs(x - sx), abs(z - sz))
                    best = max(best, rad + flick - d)
                self.light[(x, z)] = best

    def band(self, x, z):
        lum = self.light.get((x, z), 0)
        return 2 if lum >= 1.9 else 1 if lum >= 0.45 else 0

    def apply_band(self, b):
        pyxel.pal()
        if b < 2:
            for src, dst in REMAPS[b]:
                pyxel.pal(src, dst)

    # -- input ---------------------------------------------------------------
    def hovered(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for z in range(RD):
            if LANE_Y[z] <= my < LANE_Y[z] + LANE_H[z]:
                x = int((mx - LANE_X0[z]) // TILE_W[z])
                if 0 <= x < RW:
                    dx, dz = x - self.x, z - self.z
                    if abs(dx) + abs(dz) == 1:
                        return dx, dz
        return None

    def update(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.delve()
        if self.screen:
            self.update_screen()
        else:
            self.update_game()
        ax, ay = tile_anchor(self.x, self.z)
        self.sx += (ax - self.sx) * 0.28
        self.sy += (ay - self.sy) * 0.28
        self.hop = max(0.0, self.hop - 0.12)
        self.shake *= 0.8
        for m in self.room().monsters:
            m.glide()
        self.relight()

    def update_game(self):
        for keys, d in (((pyxel.KEY_A, pyxel.KEY_LEFT), (-1, 0)),
                        ((pyxel.KEY_D, pyxel.KEY_RIGHT), (1, 0)),
                        ((pyxel.KEY_W, pyxel.KEY_UP), (0, -1)),
                        ((pyxel.KEY_S, pyxel.KEY_DOWN), (0, 1))):
            for k in keys:
                if pyxel.btnp(k, 12, 4):
                    self.try_step(*d)
                    return
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.say("you hold your breath and listen")
            self.end_turn()
        elif pyxel.btnp(pyxel.KEY_T):
            self.plant_torch()
        elif pyxel.btnp(pyxel.KEY_P):
            self.quaff()
        elif pyxel.btnp(pyxel.KEY_I):
            self.screen, self.inv_sel = "inv", 0
        elif pyxel.btnp(pyxel.KEY_L):
            self.screen, self.log_off = "log", 0
        elif pyxel.btnp(pyxel.KEY_C):
            self.screen = "char"
        elif pyxel.btnp(pyxel.KEY_H):
            self.screen = "help"
        elif pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            d = self.hovered()
            if d:
                self.try_step(*d)

    def update_screen(self):
        s = self.screen
        if s == "title":
            for k in (pyxel.KEY_SPACE, pyxel.KEY_RETURN, pyxel.KEY_W,
                      pyxel.KEY_A, pyxel.KEY_S, pyxel.KEY_D, pyxel.KEY_UP,
                      pyxel.KEY_DOWN, pyxel.KEY_LEFT, pyxel.KEY_RIGHT,
                      pyxel.MOUSE_BUTTON_LEFT):
                if pyxel.btnp(k):
                    self.screen = None
                    pyxel.play(3, 7)
                    return
            return
        if s == "winanim":
            self.anim_t += 1
            x, y = self.sx, self.sy
            for _ in range(3):
                self.sparks.append([x + random.uniform(-22, 22),
                                    y - random.uniform(0, 26),
                                    random.uniform(-0.3, 0.3),
                                    random.uniform(-1.6, -0.6),
                                    random.randint(20, 55),
                                    random.choice((8, 9, 10, 10, 7))])
            for sp in self.sparks:
                sp[0] += sp[2]
                sp[1] += sp[3]
                sp[4] -= 1
            self.sparks = [sp for sp in self.sparks if sp[4] > 0]
            if self.anim_t % 36 == 1:
                pyxel.play(3, 5)
            if self.anim_t > 170:
                self.screen = "win"
            return
        if s in ("dead", "win"):
            return                                   # only R applies
        if pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.KEY_Q) or \
                pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT):
            self.screen = None
            return
        if s == "inv":
            if pyxel.btnp(pyxel.KEY_I):
                self.screen = None
            items = self.inventory()
            if pyxel.btnp(pyxel.KEY_UP, 12, 4) or pyxel.btnp(pyxel.KEY_W, 12, 4):
                self.inv_sel = max(0, self.inv_sel - 1)
            if pyxel.btnp(pyxel.KEY_DOWN, 12, 4) or pyxel.btnp(pyxel.KEY_S, 12, 4):
                self.inv_sel = min(len(items) - 1, self.inv_sel + 1)
            if pyxel.btnp(pyxel.KEY_RETURN) and items:
                name = items[self.inv_sel][0]
                self.screen = None
                if name == "red draught":
                    self.quaff()
                elif name == "torch":
                    self.plant_torch()
        elif s == "log":
            if pyxel.btnp(pyxel.KEY_L):
                self.screen = None
            if pyxel.btnp(pyxel.KEY_UP, 12, 4):
                self.log_off = min(max(0, len(self.log) - 14), self.log_off + 1)
            if pyxel.btnp(pyxel.KEY_DOWN, 12, 4):
                self.log_off = max(0, self.log_off - 1)
        elif s == "char" and pyxel.btnp(pyxel.KEY_C):
            self.screen = None
        elif s == "help" and pyxel.btnp(pyxel.KEY_H):
            self.screen = None

    def inventory(self):
        out = []
        if self.potions:
            out.append(("red draught", self.potions, "heals two hearts (P)"))
        if self.packs:
            out.append(("torch", self.packs, "plant to light a room (T)"))
        out.append(("gold", self.gold, "the dead have no use for it"))
        return out

    # -- drawing: the room box ------------------------------------------------
    def draw_scene(self):
        room = self.room()
        wall_lit, wall_mid, wall_dark = room.theme[1]
        fa, fb = room.theme[2]

        pyxel.cls(0)
        pyxel.rect(0, 10, SW_, WALL_Y - 10, 1)               # ceiling void
        for i in range(5):
            pyxel.line(20 + i * 48, 10, 28 + i * 48, WALL_Y - 1, 0)

        for x in range(RW):                                  # back wall
            b = self.band(x, 0)
            self.apply_band(b)
            px = LANE_X0[0] + x * TILE_W[0]
            for row in range(5):
                y = WALL_Y + row * 12
                off = (row % 2) * (TILE_W[0] // 2)
                pyxel.rect(px + 1 - off, y + 1, TILE_W[0] - 2, 10, wall_mid)
                pyxel.rect(px + 1 - off, y + 1, TILE_W[0] - 2, 2, wall_lit)
            pyxel.pal()

        for x, kind in room.props:                           # set dressing
            b = self.band(x, 0)
            self.apply_band(b)
            px = LANE_X0[0] + int((x + 0.5) * TILE_W[0])
            base = LANE_Y[0] + 2
            t = room.theme[0]
            if t == "cellar":
                pyxel.rect(px - 4, base - 9, 8, 9, 3)
                pyxel.rect(px - 4, base - 7, 8, 1, 2)
                pyxel.rect(px - 4, base - 4, 8, 1, 2)
            elif t == "crypt":
                pyxel.rect(px - 5, base - 10, 10, 10, 6)
                pyxel.rect(px - 3, base - 8, 6, 4, 5)
            elif t == "mines":
                pyxel.rect(px - 6, base - 14, 2, 14, 3)
                pyxel.rect(px + 4, base - 14, 2, 14, 3)
                pyxel.rect(px - 6, base - 14, 12, 2, 3)
            else:
                pyxel.rect(px - 5, base - 6, 10, 6, 5)
                pyxel.rect(px - 3, base - 8, 6, 2, 10)
            pyxel.pal()

        for x in room.sconces:                               # sconce flames
            px = LANE_X0[0] + int((x + 0.5) * TILE_W[0])
            y = WALL_Y + 18
            pyxel.rect(px - 1, y + 6, 2, 5, 3)
            f = (pyxel.frame_count // 4 + x) % 2
            pyxel.tri(px, y - 2 + f, px - 3, y + 6, px + 3, y + 6, 9)
            pyxel.tri(px, y + 1 + f, px - 1, y + 6, px + 2, y + 6, 10)

        for z in range(RD):                                  # floor lanes
            for x in range(RW):
                b = self.band(x, z)
                self.apply_band(b)
                px = LANE_X0[z] + x * TILE_W[z]
                col = fa if (x + z) % 2 else fb
                pyxel.rect(px + 1, LANE_Y[z] + 1, TILE_W[z] - 2, LANE_H[z] - 2, col)
                pyxel.rect(px + 1, LANE_Y[z] + LANE_H[z] - 2, TILE_W[z] - 2, 1, 1)
                p = (x, z)
                cx = px + TILE_W[z] // 2
                if p in room.hatches:
                    pyxel.rect(px + 2, LANE_Y[z] + 3, TILE_W[z] - 4, LANE_H[z] - 7, 0)
                    pyxel.rect(px + 2, LANE_Y[z] + 3, TILE_W[z] - 4, 2, 1)
                elif p in room.cracked:
                    pyxel.line(px + 4, LANE_Y[z] + 4, cx, LANE_Y[z] + LANE_H[z] - 6, 1)
                    pyxel.line(cx, LANE_Y[z] + 8, px + TILE_W[z] - 5,
                               LANE_Y[z] + LANE_H[z] - 4, 1)
                elif p == room.stairs_down:
                    for i in range(3):
                        pyxel.rect(px + 2 + i * 2, LANE_Y[z] + 2 + i * 5,
                                   TILE_W[z] - 4 - i * 4, 5, (5, 1, 0)[i])
                elif p == room.stairs_up:
                    for i in range(3):
                        pyxel.rect(px + 2 + i * 2, LANE_Y[z] + LANE_H[z] - 6 - i * 5,
                                   TILE_W[z] - 4 - i * 4, 4, (6, 7, 13)[i])
                elif p == room.crown:
                    pyxel.rect(cx - 4, LANE_Y[z] + 4, 8, LANE_H[z] - 10, 6)
                    f = (pyxel.frame_count // 6) % 2
                    pyxel.rect(cx - 4, LANE_Y[z] - f, 8, 4, 10)
                    pyxel.tri(cx - 4, LANE_Y[z] - f, cx - 2, LANE_Y[z] - 4 - f,
                              cx, LANE_Y[z] - f, 10)
                    pyxel.tri(cx, LANE_Y[z] - f, cx + 2, LANE_Y[z] - 4 - f,
                              cx + 4, LANE_Y[z] - f, 10)
                    pyxel.pset(cx, LANE_Y[z] + 1 - f, 8)
                item = room.items.get(p)
                if item:
                    ay = LANE_Y[z] + LANE_H[z] // 2
                    if item == "potion":
                        pyxel.rect(cx - 2, ay - 3, 4, 5, 8)
                        pyxel.rect(cx - 1, ay - 5, 2, 2, 6)
                    elif item == "torch":
                        pyxel.rect(cx - 1, ay - 4, 2, 7, 3)
                        pyxel.pset(cx, ay - 5, 9)
                    else:
                        pyxel.circ(cx, ay, 2, 10)
                        pyxel.pset(cx - 2, ay + 1, 9)
                        pyxel.pset(cx + 2, ay + 1, 9)
                pyxel.pal()

        for x, z in room.torches:                            # planted torches
            px_, py_ = tile_anchor(x, z)
            pyxel.rect(px_ - 1, py_ - 8, 2, 8, 3)
            f = (pyxel.frame_count // 4 + x) % 2
            pyxel.tri(px_, py_ - 13 + f, px_ - 3, py_ - 7, px_ + 3, py_ - 7, 9)
            pyxel.pset(px_, py_ - 9, 10)

        wl, wm, wd = room.theme[1]                           # side walls
        for side in (0, 1):
            sx0 = SW_ if side else 0
            bx = LANE_X0[0] + RW * TILE_W[0] if side else LANE_X0[0]
            fx = LANE_X0[2] + RW * TILE_W[2] if side else LANE_X0[2]
            pyxel.tri(sx0, 10, bx, WALL_Y, sx0, LANE_Y[2] + LANE_H[2], wd)
            pyxel.tri(bx, WALL_Y, bx, LANE_Y[0], sx0, LANE_Y[2] + LANE_H[2], wd)
            pyxel.tri(bx, LANE_Y[0], fx, LANE_Y[2] + LANE_H[2], sx0,
                      LANE_Y[2] + LANE_H[2], wd)
            ni = self.ri + (1 if side else -1)
            if 0 <= ni < ROOMS:                              # a door stands open
                dx0 = SW_ - 16 if side else 2
                pyxel.rect(dx0, 88, 14, 44, 1)
                pyxel.rect(dx0 + (2 if side else 0), 88, 12, 3, wm)
                pyxel.rect(dx0 + (10 if side else 0), 88, 4, 44, wm)
                pyxel.circ(dx0 + 7, 88, 6, wm)
                pyxel.circ(dx0 + 7, 89, 4, 1)

    def draw_pillars(self, z):
        room = self.room()
        wall_lit, wall_mid, wall_dark = room.theme[1]
        for x in range(RW):
            if (x, z) not in room.blocked:
                continue
            b = self.band(x, z)
            if b is None:
                continue
            self.apply_band(b)
            px = LANE_X0[z] + x * TILE_W[z]
            top = LANE_Y[z] - 26
            pyxel.rect(px + 2, top, TILE_W[z] - 4, LANE_H[z] + 22, wall_dark)
            pyxel.rect(px + 2, top, TILE_W[z] - 4, 3, wall_lit)
            pyxel.rect(px + 2, top + 3, 2, LANE_H[z] + 19, wall_mid)
            pyxel.pal()

    def draw_knight(self):
        x, y = int(self.sx), int(self.sy) - int(self.hop * 5)
        f = self.face
        bob = (pyxel.frame_count // 12) % 2
        pyxel.elli(x - 5, int(self.sy) - 2, 10, 3, 1)        # shadow
        pyxel.rect(x - 4, y - 4, 3, 3, 5)
        pyxel.rect(x + 1, y - 4, 3, 3, 5)
        pyxel.rect(x - 4 - f, y - 10 + bob, 8, 6 - bob, 8)
        pyxel.rect(x - 4 - f, y - 7, 8, 1, 2)
        pyxel.rect(x - f * 6, y - 9 + bob, 3, 4, 6)
        pyxel.rect(x - 3, y - 15 + bob, 7, 6, 7)
        pyxel.rect(x - 3 + (f > 0) * 4, y - 14 + bob, 3, 2, 0)
        pyxel.rect(x - 1, y - 17 + bob, 2, 2, 12)
        px_ = x + f * 5
        pyxel.rect(px_, y - 14 + bob, 1, 9, 3)
        pyxel.rect(px_ - 1, y - 16 + bob, 3, 2, 6)

    def draw_monster(self, m):
        x, y = int(m.sx), int(m.sy)
        b = self.band(m.x, m.z)
        if b == 0:
            return
        self.apply_band(b)
        pyxel.elli(x - 5, y - 2, 10, 3, 1)
        if m.kind == "rat":
            pyxel.rect(x - 4, y - 4, 8, 4, 3)
            pyxel.rect(x + m.face * 4, y - 5, 3, 3, 3)
            pyxel.pset(x + m.face * 5, y - 4, 8)
            pyxel.line(x - m.face * 4, y - 3, x - m.face * 7, y - 5, 14)
        elif m.kind == "bat":
            fl = (pyxel.frame_count // 5) % 2
            yy = y - 8 - fl
            pyxel.tri(x - 7, yy - 2 + fl * 3, x - 1, yy, x - 2, yy - 3, 13)
            pyxel.tri(x + 7, yy - 2 + fl * 3, x + 1, yy, x + 2, yy - 3, 13)
            pyxel.rect(x - 2, yy - 3, 4, 4, 5)
            pyxel.pset(x - 1, yy - 2, 8)
            pyxel.pset(x + 1, yy - 2, 8)
        elif m.kind == "slime":
            sq = (pyxel.frame_count // 8) % 2
            pyxel.elli(x - 5, y - 7 + sq, 10, 7 - sq, 12)
            pyxel.pset(x - 2, y - 5 + sq, 7)
            pyxel.pset(x + 1, y - 5 + sq, 0)
            pyxel.pset(x - 1, y - 5 + sq, 0)
        else:                                                # skeleton
            pyxel.rect(x - 3, y - 14, 7, 6, 7)
            pyxel.pset(x - 1 + (m.face > 0) * 2, y - 12, 8)
            pyxel.rect(x - 3, y - 8, 7, 5, 6)
            pyxel.rect(x - 3, y - 6, 7, 1, 5)
            pyxel.rect(x - 4, y - 3, 2, 3, 6)
            pyxel.rect(x + 2, y - 3, 2, 3, 6)
            pyxel.rect(x + m.face * 5, y - 12, 1, 8, 6)
        if m.hp < KINDS[m.kind]["hp"]:                       # wound pips
            for i in range(m.hp):
                pyxel.pset(x - 2 + i * 2, y - 18, 8)
        pyxel.pal()

    # -- drawing: hud and screens ----------------------------------------------
    def draw_hud(self):
        pyxel.rect(0, 0, SW_, 10, 0)
        for i in range(self.max_hearts):
            col = 8 if i < self.hearts else 5
            x = 5 + i * 8
            pyxel.tri(x, 3, x + 4, 3, x + 2, 7, col)
            pyxel.rect(x, 2, 5, 2, col)
        x = 5 + self.max_hearts * 8 + 6
        pyxel.circ(x + 2, 4, 2, 10)
        pyxel.text(x + 7, 2, str(self.gold), 13)
        pyxel.rect(x + 26, 2, 2, 6, 9)
        pyxel.text(x + 31, 2, str(self.packs), 13)
        pyxel.rect(x + 44, 3, 4, 5, 8)
        pyxel.text(x + 51, 2, str(self.potions), 13)
        pyxel.text(SW_ - 72, 2, "lv%d  depth %dm" % (self.level, self.lv * 10), 13)

        pyxel.rect(0, SH_ - 9, SW_, 9, 0)
        if self.log:
            pyxel.text(3, SH_ - 7, self.log[-1][:46], 13)
        pyxel.text(SW_ - 26, SH_ - 7, "H ?", 5)

    def draw_title(self):
        pyxel.cls(0)
        t = pyxel.frame_count
        for i in range(26):                          # drifting embers
            ex = (i * 67 + t // 3 * (1 + i % 3)) % SW_
            ey = SH_ - ((i * 41 + t * (1 + i % 2)) // 4) % SH_
            pyxel.pset(ex, ey, (9, 10, 2, 5)[i % 4])
        cx = SW_ // 2
        pyxel.rect(0, 142, SW_, 38, 1)               # dark hall floor
        for x in range(0, SW_, 24):                  # floor brick seams
            pyxel.rect(x + (142 // 16 % 2) * 12, 152, 22, 10, 2)
            pyxel.rect(x + 12, 164, 22, 10, 2)
        glow = (t // 5) % 3                          # crown above it all
        pyxel.rect(cx - 7, 26 - glow % 2, 14, 5, 10)
        for dx in (-7, -2, 3):
            pyxel.tri(cx + dx, 26 - glow % 2, cx + dx + 2, 20 - glow % 2,
                      cx + dx + 4, 26 - glow % 2, 10)
        pyxel.pset(cx - 4 + (t // 7) % 9, 28 - glow % 2, 7)
        col = (10, 9, 4)[(t // 8) % 3]               # ember-lit lettering
        block_text("UNDERVAULT", cx - 99, 44, 2, 2)
        block_text("UNDERVAULT", cx - 100, 43, 2, col)
        pyxel.text(cx - 62, 62, "a dive for the ember crown", 13)
        for tx in (cx - 70, cx + 70):                # flanking torches
            pyxel.rect(tx - 1, 96, 2, 12, 3)
            f = (t // 4 + tx) % 2
            pyxel.tri(tx, 86 + f, tx - 4, 97, tx + 4, 97, 9)
            pyxel.tri(tx, 91 + f, tx - 2, 97, tx + 2, 97, 10)
        sx_, sy_ = self.sx, self.sy                  # borrow the knight pose
        self.sx, self.sy = cx, 158
        self.draw_knight()
        self.sx, self.sy = sx_, sy_
        bx = (t * 2) % (SW_ + 60) - 30               # a bat crosses the hall
        by = 78 + pyxel.sin(t * 6) * 5
        fl = (t // 5) % 2
        pyxel.tri(bx - 6, by - fl * 3, bx - 1, by, bx - 1, by - 3, 13)
        pyxel.tri(bx + 6, by - fl * 3, bx + 1, by, bx + 1, by - 3, 13)
        pyxel.rect(bx - 1, by - 2, 3, 3, 5)
        if (t // 14) % 2:
            pyxel.text(cx - 36, 118, "press any key", 7)
        pyxel.text(cx - 56, 130, "arrows move   H knows more", 5)
        pyxel.text(3, SH_ - 7, "v2", 5)
        pyxel.text(SW_ - 60, SH_ - 7, "pyxel arcade", 5)

    def panel(self, title):
        pyxel.rect(20, 18, SW_ - 40, SH_ - 36, 0)
        pyxel.rectb(20, 18, SW_ - 40, SH_ - 36, 13)
        pyxel.rectb(21, 19, SW_ - 42, SH_ - 38, 5)
        pyxel.text(28, 24, title, 10)
        pyxel.line(28, 31, SW_ - 28, 31, 5)

    def draw_screen(self):
        s = self.screen
        if s == "inv":
            self.panel("inventory")
            items = self.inventory()
            for i, (name, count, note) in enumerate(items):
                y = 38 + i * 16
                if i == self.inv_sel:
                    pyxel.rect(24, y - 2, SW_ - 48, 13, 1)
                    pyxel.text(28, y, ">", 10)
                pyxel.text(36, y, "%s x%d" % (name, count), 7)
                pyxel.text(36, y + 7, note, 13)
            pyxel.text(28, SH_ - 28, "up/down + enter to use, I closes", 5)
        elif s == "log":
            self.panel("message log")
            lines = self.log[-(14 + self.log_off):len(self.log) - self.log_off]
            for i, line in enumerate(lines[-14:]):
                pyxel.text(28, 36 + i * 8, line[:46], 13 if i < 13 else 7)
            pyxel.text(28, SH_ - 28, "up/down scrolls, L closes", 5)
        elif s == "char":
            self.panel("the delver")
            rows = (
                ("level", str(self.level)),
                ("experience", "%d / %d" % (self.xp, 2 + 2 * self.level)),
                ("hearts", "%d of %d" % (self.hearts, self.max_hearts)),
                ("pick damage", str(self.attack_power())),
                ("gold", str(self.gold)),
                ("kills", str(self.kills)),
                ("depth", "%d of %dm" % (self.lv * 10, GOAL_LEVEL * 10)),
                ("turns in the dark", str(self.turn)),
            )
            for i, (k, v) in enumerate(rows):
                pyxel.text(30, 38 + i * 11, k, 13)
                pyxel.text(150, 38 + i * 11, v, 7)
            pyxel.text(28, SH_ - 28, "C closes", 5)
        elif s == "help":
            self.panel("how to delve")
            rows = (
                "arrows or wasd  step / change lane",
                "bump a monster  attack with your pick",
                "bump cracks     dig the floor open",
                "stairs + holes  carry you between depths",
                "T plant torch   P drink a draught",
                "I inventory     L log     C character",
                "",
                "reach depth %dm and take the Ember Crown" % (GOAL_LEVEL * 10),
            )
            for i, line in enumerate(rows):
                pyxel.text(28, 38 + i * 11, line, 7 if i < 6 else 10)
            pyxel.text(28, SH_ - 28, "H closes", 5)
        elif s in ("dead", "win"):
            self.panel("the delve ends" if s == "dead" else "the crown burns")
            head = "the undervault keeps your bones" if s == "dead" else \
                "you carry fire back to the sun"
            pyxel.text(28, 40, head, 8 if s == "dead" else 10)
            rows = (
                ("depth reached", "%dm" % (self.lv * 10)),
                ("level", str(self.level)),
                ("kills", str(self.kills)),
                ("gold", str(self.gold)),
                ("turns", str(self.turn)),
            )
            for i, (k, v) in enumerate(rows):
                pyxel.text(30, 58 + i * 11, k, 13)
                pyxel.text(150, 58 + i * 11, v, 7)
            pyxel.text(28, SH_ - 28, "R delves anew", 10)

    def draw_winanim(self):
        t = self.anim_t
        x, y = int(self.sx), int(self.sy)
        rise = min(t, 28)
        cy = y - 18 - rise * 0.5                     # the crown ascends
        for r in (t * 2 % 90, (t * 2 + 45) % 90):    # rings of triumph
            if 4 < r < 80:
                pyxel.circb(x, y - 12, r, 10 if r % 2 else 9)
        for sx_, sy_, _, _, life, col in self.sparks:
            pyxel.pset(int(sx_), int(sy_), col if life > 12 else 9)
        pyxel.rect(x - 7, cy, 14, 5, 10)
        for dx in (-7, -2, 3):
            pyxel.tri(x + dx, cy, x + dx + 2, cy - 6, x + dx + 4, cy, 10)
        pyxel.pset(x - 4 + (t // 5) % 9, cy + 2, 7)
        if t > 24:
            label = "THE EMBER CROWN"
            pyxel.text(x - len(label) * 2 + 1, cy - 16, label, 0)
            pyxel.text(x - len(label) * 2, cy - 17, label,
                       (10, 9, 7)[(t // 6) % 3])

    def draw(self):
        if self.screen == "title":
            self.draw_title()
            return
        if self.shake > 0.5:
            pyxel.camera(random.uniform(-self.shake, self.shake),
                         random.uniform(-self.shake, self.shake))
        self.draw_scene()
        room = self.room()
        for z in range(RD):                                  # painter's order
            self.draw_pillars(z)
            for m in room.monsters:
                if m.z == z:
                    self.draw_monster(m)
            if self.z == z and self.screen not in ("dead",):
                self.draw_knight()
        d = self.hovered()
        if d and not self.screen:
            hx, hz = self.x + d[0], self.z + d[1]
            px = LANE_X0[hz] + hx * TILE_W[hz]
            pyxel.rectb(px, LANE_Y[hz], TILE_W[hz], LANE_H[hz], 10)
        if self.screen == "winanim":
            self.draw_winanim()
        pyxel.camera()
        self.draw_hud()
        if self.screen and self.screen != "winanim":
            self.draw_screen()


if __name__ == "__main__":
    App().run()
