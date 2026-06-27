"""Noita Demake -- a tiny wand-and-powder cave crawl for Pyxel.

Controls:  A/D or arrows = move       W/Space = jump / levitate
           mouse = aim                left click or Z = cast wand
           right click or F = pour flask       1-3 = switch wands
           E = use portal / pickup    Tab = wands     R = restart

This is an original Pyxel demake inspired by Noita's broad shape:
pixel materials, wand stats, spell slots, liquids, fire, gold, caves,
and Holy-Mountain-style wand editing between biomes.
"""
import math
import os
import random
import sys

import pyxel


SW, SH = 256, 192
HUD_H, LOG_H = 16, 18
VIEW_H = SH - HUD_H - LOG_H
WORLD_W, WORLD_H = 560, 176

AIR, DIRT, ROCK, COAL, GOLD_ORE, WATER, TOXIC, LAVA, OIL, FIRE, SMOKE, VINE, BRICK, SAND = range(14)

PALETTE = [
    0x050409, 0x101119, 0x251A16, 0x49312B, 0x876141, 0x1E2A2F,
    0x4A5560, 0xD7D0C5, 0xFF3B6E, 0xFF8A32, 0xFFD95A, 0x6EA22B,
    0x38BDF8, 0x4850A8, 0xB45BE3, 0x00A686,
]

SOLIDS = (DIRT, ROCK, COAL, GOLD_ORE, BRICK, SAND)
LIQUIDS = (WATER, TOXIC, LAVA, OIL)
FLOW_EMPTY = (AIR, FIRE, SMOKE)
BIOMES = [
    {
        "name": "Mines",
        "rock": (DIRT, ROCK, COAL),
        "liquids": (WATER, TOXIC, OIL),
        "enemies": ("slime", "hiisi"),
        "base_y": 83,
    },
    {
        "name": "Fungal Caves",
        "rock": (DIRT, ROCK, COAL),
        "liquids": (WATER, TOXIC, TOXIC, OIL),
        "enemies": ("slime", "fly", "stendari"),
        "base_y": 78,
    },
    {
        "name": "Snowy Depths",
        "rock": (ROCK, ROCK, COAL, GOLD_ORE),
        "liquids": (WATER, TOXIC, LAVA),
        "enemies": ("hiisi", "fly", "stendari"),
        "base_y": 86,
    },
    {
        "name": "Lava Temple",
        "rock": (ROCK, ROCK, GOLD_ORE, BRICK),
        "liquids": (LAVA, LAVA, TOXIC, OIL),
        "enemies": ("stendari", "fly", "alchemist"),
        "base_y": 82,
    },
]

SPELLS = {
    "spark": {
        "name": "Spark Bolt", "cost": 4, "dmg": 1, "speed": 3.8, "life": 45,
        "color": 12, "dig": 2, "radius": 1, "price": 20,
    },
    "arrow": {
        "name": "Magic Arrow", "cost": 7, "dmg": 2, "speed": 4.4, "life": 55,
        "color": 13, "dig": 3, "radius": 1, "price": 38,
    },
    "digger": {
        "name": "Digging Spark", "cost": 3, "dmg": 0.2, "speed": 2.4, "life": 30,
        "color": 10, "dig": 11, "radius": 5, "price": 32,
    },
    "bubble": {
        "name": "Bubble Spark", "cost": 3, "dmg": 0.7, "speed": 2.1, "life": 72,
        "color": 15, "dig": 1, "radius": 1, "bounce": 2, "price": 28,
    },
    "fire": {
        "name": "Firebolt", "cost": 9, "dmg": 1.4, "speed": 3.2, "life": 42,
        "color": 9, "dig": 3, "radius": 4, "element": FIRE, "burn": 70,
        "price": 45,
    },
    "toxic": {
        "name": "Toxic Arc", "cost": 6, "dmg": 0.8, "speed": 3.1, "life": 46,
        "color": 11, "dig": 2, "radius": 2, "element": TOXIC, "trail": TOXIC,
        "price": 42,
    },
    "bomb": {
        "name": "Bomb", "cost": 34, "dmg": 5, "speed": 1.7, "life": 72,
        "color": 10, "dig": 30, "radius": 16, "gravity": 0.055, "boom": True,
        "price": 70,
    },
    "rain": {
        "name": "Water Drop", "cost": 5, "dmg": 0.1, "speed": 2.0, "life": 46,
        "color": 12, "dig": 0, "radius": 2, "trail": WATER, "price": 26,
    },
}

SPELL_POOL = ("spark", "arrow", "digger", "bubble", "fire", "toxic", "bomb", "rain")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def chance(p):
    return random.random() < p


def dist2(ax, ay, bx, by):
    dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy


class Player:
    def __init__(self):
        self.x = 20.0
        self.y = 70.0
        self.w = 6
        self.h = 10
        self.vx = 0.0
        self.vy = 0.0
        self.face = 1
        self.ground = False
        self.hp = 5
        self.max_hp = 5
        self.gold = 0
        self.fuel = 100.0
        self.wet = 0
        self.burn = 0
        self.toxic = 0
        self.invuln = 0
        self.has_orb = False


class Enemy:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.vx = random.choice((-0.6, 0.6))
        self.vy = 0.0
        self.face = 1 if self.vx >= 0 else -1
        self.w = 7 if kind != "fly" else 8
        self.h = 9 if kind != "fly" else 7
        data = {
            "slime": (3, 0, 0),
            "hiisi": (4, 80, 0),
            "stendari": (5, 55, 1),
            "fly": (2, 45, 1),
            "alchemist": (12, 46, 1),
        }[kind]
        self.hp, self.fire_cd, self.flying = data
        self.max_hp = self.hp
        self.ground = False
        self.burn = 0
        self.toxic = 0
        self.awake = False
        self.hurt_flash = 0


class Shot:
    def __init__(self, x, y, vx, vy, sid, owner):
        spec = SPELLS.get(sid, {})
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.sid = sid
        self.owner = owner
        self.life = spec.get("life", 50)
        self.dmg = spec.get("dmg", 1)
        self.color = spec.get("color", 12)
        self.radius = spec.get("radius", 1)
        self.dig = spec.get("dig", 1)
        self.element = spec.get("element")
        self.trail = spec.get("trail")
        self.gravity = spec.get("gravity", 0.0)
        self.bounce = spec.get("bounce", 0)
        self.burn = spec.get("burn", 0)
        self.boom = spec.get("boom", False)


class Pickup:
    def __init__(self, kind, x, y, value=None):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.value = value
        self.vy = 0.0
        self.t = random.randrange(1000)


class Wand:
    def __init__(self, name, slots, shuffle=False, multicast=1,
                 mana=60, regen=0.8, delay=10, recharge=24):
        self.name = name
        self.slots = list(slots)[:5]
        while len(self.slots) < 5:
            self.slots.append(None)
        self.shuffle = shuffle
        self.multicast = multicast
        self.mana_max = mana
        self.mana = float(mana)
        self.regen = regen
        self.delay = delay
        self.recharge = recharge
        self.cool = 0
        self.step = 0

    def nonempty(self):
        return [sid for sid in self.slots if sid]

    def short_stats(self):
        return "%s  cast %d  mana %d/%d" % (
            "SHF" if self.shuffle else "SEQ",
            self.multicast,
            int(self.mana),
            self.mana_max,
        )

    def tick(self):
        self.cool = max(0, self.cool - 1)
        self.mana = min(self.mana_max, self.mana + self.regen)


class App:
    def __init__(self):
        pyxel.init(SW, SH, title="Noita Demake", fps=30, quit_key=pyxel.KEY_NONE)
        pyxel.mouse(True)
        pyxel.colors[:] = PALETTE
        self.make_sounds()
        self.screen = "title"
        self.menu = 0
        self.seed = random.randrange(999999)
        self.depth = 0
        self.message = []
        self.shop = []
        self.shop_sel = 0
        self.edit_wand = 0
        self.edit_slot = 0
        self.return_screen = "shop"
        self.edit_allowed = False
        self.new_run(from_title=True)

    def run(self):
        pyxel.run(self.update, self.draw)

    def make_sounds(self):
        pyxel.sounds[0].set("c3e3g3", "ttt", "432", "fff", 6)
        pyxel.sounds[1].set("g2c3", "pp", "54", "ff", 8)
        pyxel.sounds[2].set("c2f1", "nn", "65", "ff", 12)
        pyxel.sounds[3].set("c3g3c4", "sss", "432", "nnn", 7)
        pyxel.sounds[4].set("f1c1f0", "nnn", "765", "fff", 15)
        pyxel.sounds[5].set("c3e3g3c4", "tttt", "3456", "nnnn", 8)
        pyxel.sounds[6].set("a1e2a2", "ppp", "654", "fff", 10)
        pyxel.sounds[7].set("c4g3e3c3", "tttt", "6543", "nnnn", 12)

    # -- run setup -----------------------------------------------------
    def new_run(self, from_title=False):
        self.player = Player()
        self.wands = [
            Wand("Blue Starter", ["spark", "spark", "spark"], False, 1, 52, 0.75, 9, 22),
            Wand("Mud Cutter", ["digger", "spark"], False, 1, 44, 0.65, 12, 28),
        ]
        self.spell_bag = ["spark", "digger"]
        self.active_wand = 0
        self.flask_mat = WATER
        self.flask_amt = 100
        self.depth = 0
        self.turns = 0
        self.kills = 0
        self.shake = 0
        self.portal_t = 0
        self.win_t = 0
        self.message = []
        self.start_biome(0)
        if not from_title:
            self.screen = "play"
            self.say("You kick a lantern into the dark.")

    def start_biome(self, depth):
        self.depth = depth
        self.biome = BIOMES[depth]
        self.grid = bytearray(WORLD_W * WORLD_H)
        self.pickups = []
        self.enemies = []
        self.shots = []
        self.parts = []
        self.camx = 0
        self.camy = 0
        self.path = []
        self.generate_world()
        sx = 28
        gy = self.find_ground(sx, self.path[sx] - 35)
        self.player.x = sx
        self.player.y = gy - self.player.h
        self.player.vx = self.player.vy = 0
        self.player.wet = max(self.player.wet, 30)
        self.portal_x = WORLD_W - 44
        pgy = self.find_ground(self.portal_x, self.path[self.portal_x] - 35)
        self.portal_y = pgy - 16
        self.portal_t = 0
        self.say("%s. Find the portal." % self.biome["name"])

    def idx(self, x, y):
        return x + y * WORLD_W

    def inb(self, x, y):
        return 0 <= x < WORLD_W and 0 <= y < WORLD_H

    def get(self, x, y):
        if 0 <= x < WORLD_W and 0 <= y < WORLD_H:
            return self.grid[x + y * WORLD_W]
        return BRICK

    def set(self, x, y, m):
        if 0 <= x < WORLD_W and 0 <= y < WORLD_H:
            self.grid[x + y * WORLD_W] = m

    def solid(self, x, y):
        return self.get(x, y) in SOLIDS

    def material_color(self, m, x, y):
        if m == AIR:
            return 0
        if m == DIRT:
            return 3 if (x * 5 + y * 3) % 9 else 4
        if m == ROCK:
            return 5 if (x + y) % 5 else 6
        if m == COAL:
            return 2 if (x + y) % 3 else 1
        if m == GOLD_ORE:
            return 10 if (x + y + pyxel.frame_count // 8) % 4 else 9
        if m == WATER:
            return 12 if (x + y + pyxel.frame_count // 5) % 5 else 13
        if m == TOXIC:
            pulse = x * 7 + y * 11 + pyxel.frame_count // 3
            if pulse % 29 == 0:
                return 0
            if (x - y + pyxel.frame_count // 6) % 6 == 0:
                return 15
            return 11
        if m == LAVA:
            return (9, 10, 8)[(x + y + pyxel.frame_count // 3) % 3]
        if m == OIL:
            return 1 if (x + y) % 2 else 2
        if m == FIRE:
            return (8, 9, 10)[(x + y + pyxel.frame_count // 2) % 3]
        if m == SMOKE:
            return 5 if (x + y + pyxel.frame_count // 7) % 4 else 6
        if m == VINE:
            return 11 if (x + y) % 2 else 15
        if m == BRICK:
            return 3 if (x // 5 + y // 3) % 2 else 5
        if m == SAND:
            return 4
        return 7

    # -- generation ----------------------------------------------------
    def generate_world(self):
        random.seed(self.seed + self.depth * 8191)
        rocks = self.biome["rock"]
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                if x < 3 or x >= WORLD_W - 3 or y < 3 or y >= WORLD_H - 3:
                    self.set(x, y, BRICK if self.depth >= 3 else ROCK)
                    continue
                pick = random.random()
                if pick < 0.07 and GOLD_ORE in rocks:
                    m = GOLD_ORE
                elif pick < 0.16:
                    m = COAL
                elif pick < 0.42:
                    m = DIRT
                else:
                    m = ROCK
                self.set(x, y, m)

        base = self.biome["base_y"]
        drift = random.uniform(0, 6.28)
        for x in range(WORLD_W):
            yy = base + int(math.sin(x / 38.0 + drift) * 15 +
                            math.sin(x / 17.0 + drift * 1.7) * 7)
            self.path.append(clamp(yy, 48, WORLD_H - 42))

        for x in range(10, WORLD_W - 10, 3):
            r = 25 + int(5 * math.sin(x / 29.0 + drift))
            self.carve_circle(x, self.path[x], r, AIR)
        for _ in range(36 + self.depth * 7):
            cx = random.randrange(45, WORLD_W - 55)
            cy = self.path[cx] + random.randint(-35, 35)
            self.carve_circle(cx, cy, random.randint(10, 24), AIR)

        self.carve_circle(30, self.path[30], 36, AIR)
        self.carve_circle(WORLD_W - 44, self.path[WORLD_W - 44], 32, AIR)
        for x in range(14, 72):
            g = self.find_ground(x, 20)
            for y in range(g - 2, g + 4):
                if self.inb(x, y):
                    self.set(x, y, DIRT if self.depth == 0 else ROCK)

        for _ in range(10 + self.depth * 5):
            cx = random.randrange(80, WORLD_W - 70)
            cy = self.path[cx] + random.randint(15, 45)
            mat = random.choice(self.biome["liquids"])
            self.carve_pool(cx, cy, random.randint(12, 24), random.randint(7, 14), mat)

        for _ in range(18 + self.depth * 6):
            cx = random.randrange(70, WORLD_W - 60)
            cy = self.path[cx] + random.randint(22, 48)
            for y in range(cy - 4, cy + 5):
                for x in range(cx - 6, cx + 7):
                    if self.inb(x, y) and random.random() < 0.45:
                        self.set(x, y, GOLD_ORE)

        if self.depth == 1:
            for _ in range(160):
                x = random.randrange(10, WORLD_W - 10)
                y = random.randrange(12, WORLD_H - 20)
                if self.get(x, y) == AIR and self.solid(x, y - 1):
                    self.set(x, y, VINE)

        if self.depth >= 3:
            for x in range(4, WORLD_W - 4):
                if random.random() < 0.7:
                    self.set(x, WORLD_H - 8, LAVA)
                    self.set(x, WORLD_H - 7, LAVA)

        self.settle_materials_global(8)
        self.place_world_items()
        self.place_enemies()

    def carve_circle(self, cx, cy, r, mat=AIR):
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if self.inb(x, y) and dist2(x, y, cx, cy) <= r2:
                    self.set(x, y, mat)

    def carve_ellipse(self, cx, cy, rx, ry, mat=AIR):
        rx2, ry2 = rx * rx, ry * ry
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if not self.inb(x, y):
                    continue
                dx, dy = x - cx, y - cy
                if dx * dx * ry2 + dy * dy * rx2 <= rx2 * ry2:
                    self.set(x, y, mat)

    def carve_pool(self, cx, cy, rx, ry, mat):
        self.carve_ellipse(cx, cy, rx, ry, AIR)
        surface = cy + random.randint(-1, 2)
        for x in range(cx - rx + 1, cx + rx):
            floor = None
            for y in range(cy + ry, max(cy - ry, surface) - 1, -1):
                if self.inb(x, y) and self.get(x, y) == AIR and self.solid(x, y + 1):
                    floor = y
                    break
            if floor is None or floor < surface:
                continue
            for y in range(surface, floor + 1):
                dx, dy = x - cx, y - cy
                if dx * dx * ry * ry + dy * dy * rx * rx <= rx * rx * ry * ry:
                    if self.get(x, y) in FLOW_EMPTY:
                        self.set(x, y, mat)

    def settle_materials_global(self, passes):
        for step in range(passes):
            for y in range(WORLD_H - 4, 3, -1):
                xs = range(3, WORLD_W - 3) if (y + step) % 2 else range(WORLD_W - 4, 2, -1)
                for x in xs:
                    m = self.get(x, y)
                    if m in LIQUIDS:
                        below = self.get(x, y + 1)
                        if m == LAVA and below == WATER:
                            self.set(x, y, ROCK)
                            self.set(x, y + 1, SMOKE)
                            continue
                        if below in FLOW_EMPTY:
                            self.swap(x, y, x, y + 1)
                            continue
                        dirs = (-1, 1) if (x + y + step) % 2 else (1, -1)
                        moved = False
                        for dx in dirs:
                            if self.get(x + dx, y + 1) in FLOW_EMPTY:
                                self.swap(x, y, x + dx, y + 1)
                                moved = True
                                break
                        if moved:
                            continue
                        if m != LAVA or (x + y + step) % 4 == 0:
                            for dx in dirs:
                                if self.get(x + dx, y) in FLOW_EMPTY:
                                    self.swap(x, y, x + dx, y)
                                    break
                    elif m == SAND:
                        if self.get(x, y + 1) in (AIR, WATER, TOXIC):
                            self.swap(x, y, x, y + 1)
                        else:
                            dx = -1 if (x + y + step) % 2 else 1
                            if self.get(x + dx, y + 1) in (AIR, WATER, TOXIC):
                                self.swap(x, y, x + dx, y + 1)

    def find_ground(self, x, start=8):
        x = int(clamp(x, 4, WORLD_W - 5))
        for y in range(max(6, int(start)), WORLD_H - 5):
            if self.get(x, y) == AIR and self.solid(x, y + 1):
                return y + 1
        return WORLD_H - 12

    def place_on_floor(self, kind, value, x):
        gy = self.find_ground(x, max(8, self.path[int(clamp(x, 0, WORLD_W - 1))] - 50))
        self.pickups.append(Pickup(kind, x, gy - 6, value))

    def place_world_items(self):
        for _ in range(4 + self.depth):
            x = random.randrange(90, WORLD_W - 80)
            self.place_on_floor("gold", random.randint(5, 16), x)
        for _ in range(2):
            sid = random.choice(SPELL_POOL[1:])
            self.place_on_floor("spell", sid, random.randrange(110, WORLD_W - 95))
        if random.random() < 0.75:
            self.place_on_floor("wand", self.random_wand(self.depth + 1), random.randrange(140, WORLD_W - 110))
        if random.random() < 0.45:
            self.place_on_floor("heal", 1, random.randrange(130, WORLD_W - 100))
        if self.depth == len(BIOMES) - 1:
            self.place_on_floor("orb", None, WORLD_W - 86)

    def place_enemies(self):
        count = 8 + self.depth * 5
        for _ in range(count):
            x = random.randrange(100, WORLD_W - 80)
            gy = self.find_ground(x, self.path[x] - 50)
            kind = random.choice(self.biome["enemies"])
            y = gy - (9 if kind != "fly" else random.randint(20, 48))
            self.enemies.append(Enemy(kind, x, y))
        if self.depth == len(BIOMES) - 1:
            x = WORLD_W - 108
            gy = self.find_ground(x, self.path[x] - 40)
            self.enemies.append(Enemy("alchemist", x, gy - 14))

    def random_wand(self, tier=1):
        names = ("Crooked Wand", "Bone Wand", "Glass Wand", "Ash Wand", "Green Wand")
        slots = []
        for _ in range(random.randint(2, 4 + min(1, tier))):
            slots.append(random.choice(SPELL_POOL[:min(len(SPELL_POOL), 4 + tier)]))
        return Wand(
            random.choice(names),
            slots,
            shuffle=chance(0.35),
            multicast=random.choice((1, 1, 1, 2 + (tier > 2))),
            mana=random.randint(45 + tier * 8, 80 + tier * 22),
            regen=random.uniform(0.55, 1.0 + tier * 0.18),
            delay=random.randint(max(5, 13 - tier * 2), 15),
            recharge=random.randint(max(12, 30 - tier * 3), 40),
        )

    # -- messages ------------------------------------------------------
    def say(self, text, col=7):
        self.message.append((text, col, 150))
        del self.message[:-5]

    def play(self, sound):
        pyxel.play(3, sound)

    # -- input and update ----------------------------------------------
    def update(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.new_run()
            return
        if self.screen == "title":
            self.update_title()
        elif self.screen == "play":
            self.update_play()
        elif self.screen == "shop":
            self.update_shop()
        elif self.screen == "wands":
            self.update_wands_screen()
        elif self.screen in ("dead", "win"):
            if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
                self.new_run()

        self.message = [(t, c, n - 1) for t, c, n in self.message if n > 0]

    def update_title(self):
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.menu = (self.menu - 1) % 3
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.menu = (self.menu + 1) % 3
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if self.menu == 0:
                self.new_run()
            elif self.menu == 1:
                self.return_screen = "title"
                self.edit_allowed = False
                self.edit_wand = min(self.active_wand, len(self.wands) - 1)
                self.edit_slot = min(self.edit_slot, len(self.wands[self.edit_wand].slots) - 1)
                self.screen = "wands"
            else:
                self.new_run(from_title=True)
                self.screen = "title"

    def update_play(self):
        self.turns += 1
        self.update_player()
        for w in self.wands:
            w.tick()
        self.update_materials()
        self.update_shots()
        self.update_enemies()
        self.update_pickups()
        self.update_particles()
        self.update_camera()
        self.check_portal()
        if self.player.hp <= 0:
            self.screen = "dead"
            self.play(4)
            self.say("Your bones become cave geometry.", 8)

    def update_player(self):
        p = self.player
        p.invuln = max(0, p.invuln - 1)
        left = pyxel.btn(pyxel.KEY_A) or pyxel.btn(pyxel.KEY_LEFT)
        right = pyxel.btn(pyxel.KEY_D) or pyxel.btn(pyxel.KEY_RIGHT)
        jump = pyxel.btn(pyxel.KEY_W) or pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.KEY_SPACE)
        if left:
            p.vx -= 0.28
            p.face = -1
        if right:
            p.vx += 0.28
            p.face = 1
        if not left and not right:
            p.vx *= 0.78 if p.ground else 0.96
        p.vx = clamp(p.vx, -2.15, 2.15)

        if jump and p.ground and (pyxel.btnp(pyxel.KEY_W) or pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_SPACE)):
            p.vy = -3.7
            p.ground = False
            self.play(3)
        elif jump and not p.ground and p.fuel > 0:
            p.vy -= 0.17
            p.fuel -= 1.35
            if chance(0.25):
                self.parts.append([p.x + 3, p.y + 9, random.uniform(-0.4, 0.4), 0.6, 14, 13])
        if not jump:
            p.vy += 0.18
        else:
            p.vy += 0.10
        p.vy = clamp(p.vy, -4.0, 4.2)
        if p.ground:
            p.fuel = min(100, p.fuel + 2.6)
        else:
            p.fuel = min(100, p.fuel + 0.35)

        self.move_body(p)
        self.sample_player_materials()
        self.handle_casting()
        if pyxel.btnp(pyxel.KEY_TAB):
            self.return_screen = "play"
            self.edit_allowed = False
            self.edit_wand = min(self.active_wand, len(self.wands) - 1)
            self.edit_slot = min(self.edit_slot, len(self.wands[self.edit_wand].slots) - 1)
            self.screen = "wands"
        for i, key in enumerate((pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3)):
            if pyxel.btnp(key) and i < len(self.wands):
                self.active_wand = i
                self.say("Wand %d: %s" % (i + 1, self.wands[i].name), 13)

    def move_body(self, body):
        body.ground = False
        steps = max(1, int(abs(body.vx) / 0.5) + 1)
        dx = body.vx / steps
        for _ in range(steps):
            if not self.rect_solid(body.x + dx, body.y, body.w, body.h):
                body.x += dx
            else:
                body.vx = 0
                break
        steps = max(1, int(abs(body.vy) / 0.5) + 1)
        dy = body.vy / steps
        for _ in range(steps):
            if not self.rect_solid(body.x, body.y + dy, body.w, body.h):
                body.y += dy
            else:
                if dy > 0:
                    body.ground = True
                body.vy = 0
                break
        body.x = clamp(body.x, 4, WORLD_W - body.w - 4)
        body.y = clamp(body.y, 4, WORLD_H - body.h - 4)

    def rect_solid(self, x, y, w, h):
        x0 = int(math.floor(x))
        y0 = int(math.floor(y))
        x1 = int(math.floor(x + w - 0.1))
        y1 = int(math.floor(y + h - 0.1))
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if self.solid(xx, yy):
                    return True
        return False

    def sample_player_materials(self):
        p = self.player
        counts = {WATER: 0, TOXIC: 0, LAVA: 0, FIRE: 0, OIL: 0}
        for yy in range(int(p.y), int(p.y + p.h)):
            for xx in range(int(p.x), int(p.x + p.w)):
                m = self.get(xx, yy)
                if m in counts:
                    counts[m] += 1
        if counts[WATER]:
            p.wet = min(100, p.wet + 4)
            p.burn = max(0, p.burn - 8)
            p.toxic = max(0, p.toxic - 6)
        if counts[TOXIC]:
            buildup = 1 if p.wet else 2
            if counts[TOXIC] > 18:
                buildup += 1
            p.toxic = min(100, p.toxic + buildup)
        if counts[OIL]:
            p.burn = min(100, p.burn + 2)
        if counts[FIRE] or counts[LAVA]:
            p.burn = min(100, p.burn + (8 if counts[LAVA] else 4))
            if p.invuln == 0 and counts[LAVA]:
                self.hurt_player(1, "Lava chews through your cloak.", 9)
        p.wet = max(0, p.wet - 1)
        if not counts[TOXIC]:
            decay = 2 if p.wet else 1
            if pyxel.frame_count % 2 == 0:
                p.toxic = max(0, p.toxic - decay)
        p.burn = max(0, p.burn - (3 if p.wet else 1))
        if pyxel.frame_count % 60 == 0:
            if p.burn and p.invuln == 0:
                self.hurt_player(1, "You are burning.", 8)
            elif p.toxic >= 28 and p.invuln == 0:
                self.hurt_player(1, "Toxic stain seeps in.", 11)

    def hurt_player(self, n, text, col=8):
        if self.player.invuln > 0:
            return
        self.player.hp -= n
        self.player.invuln = 38
        self.shake = 5
        self.say(text, col)
        self.play(2)

    def handle_casting(self):
        p = self.player
        if pyxel.btnp(pyxel.KEY_E):
            self.try_use_nearby()
        if (pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT) or pyxel.btn(pyxel.KEY_F)) and self.flask_amt > 0:
            self.pour_flask()
        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT) or pyxel.btn(pyxel.KEY_Z):
            self.cast_active_wand()

    def aim_angle(self):
        wx = self.camx + pyxel.mouse_x
        wy = self.camy + (pyxel.mouse_y - HUD_H)
        p = self.player
        dx = wx - (p.x + p.w / 2)
        dy = wy - (p.y + p.h / 2)
        if abs(dx) + abs(dy) < 2:
            dx, dy = p.face, 0
        return math.atan2(dy, dx)

    def cast_active_wand(self):
        if not self.wands:
            return
        wand = self.wands[self.active_wand]
        if wand.cool > 0:
            return
        spells = wand.nonempty()
        if not spells:
            self.say("The wand is empty.", 5)
            wand.cool = 10
            return
        chosen = []
        if wand.shuffle:
            for _ in range(wand.multicast):
                chosen.append(random.choice(spells))
        else:
            tries = 0
            while len(chosen) < wand.multicast and tries < len(wand.slots) + 2:
                sid = wand.slots[wand.step % len(wand.slots)]
                wand.step = (wand.step + 1) % len(wand.slots)
                tries += 1
                if sid:
                    chosen.append(sid)
            if wand.step == 0:
                wand.cool = wand.recharge
        cost = sum(SPELLS[s]["cost"] for s in chosen)
        if wand.mana < cost:
            if pyxel.frame_count % 16 == 0:
                self.say("Not enough mana.", 5)
            wand.cool = 5
            return
        wand.mana -= cost
        wand.cool = max(wand.cool, wand.delay)
        p = self.player
        ang = self.aim_angle()
        px = p.x + p.w / 2 + math.cos(ang) * 5
        py = p.y + p.h / 2 + math.sin(ang) * 5
        spread = 0.18 if len(chosen) > 1 else 0.04
        for i, sid in enumerate(chosen):
            spec = SPELLS[sid]
            a = ang + random.uniform(-spread, spread) + (i - (len(chosen) - 1) / 2) * 0.08
            speed = spec["speed"]
            self.shots.append(Shot(px, py, math.cos(a) * speed, math.sin(a) * speed, sid, "player"))
        self.play(0)

    def pour_flask(self):
        p = self.player
        ang = self.aim_angle()
        for _ in range(2):
            x = int(p.x + p.w / 2 + math.cos(ang) * random.randint(4, 9) + random.randint(-1, 1))
            y = int(p.y + p.h / 2 + math.sin(ang) * random.randint(4, 9) + random.randint(-1, 1))
            if self.inb(x, y) and self.get(x, y) in (AIR, FIRE, SMOKE, VINE):
                self.set(x, y, self.flask_mat)
                self.flask_amt -= 1
                if self.flask_amt <= 0:
                    self.flask_amt = 0
                    break

    # -- materials -----------------------------------------------------
    def update_materials(self):
        x0 = int(clamp(self.camx - 24, 1, WORLD_W - 2))
        x1 = int(clamp(self.camx + SW + 24, 2, WORLD_W - 1))
        y0 = int(clamp(self.camy - 16, 1, WORLD_H - 2))
        y1 = int(clamp(self.camy + VIEW_H + 18, 2, WORLD_H - 1))
        for _ in range(1250):
            x = random.randrange(x0, x1)
            y = random.randrange(y0, y1)
            m = self.get(x, y)
            if m == WATER:
                self.flow_liquid(x, y, WATER, 1)
                for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
                    n = self.get(x + dx, y + dy)
                    if n == LAVA:
                        self.set(x, y, SMOKE)
                        self.set(x + dx, y + dy, ROCK)
                        break
                    if n == TOXIC and chance(0.05):
                        self.set(x + dx, y + dy, WATER)
            elif m == TOXIC:
                self.flow_liquid(x, y, TOXIC, 1)
            elif m == OIL:
                self.flow_liquid(x, y, OIL, 1)
                if self.neighbor_is(x, y, FIRE) or self.neighbor_is(x, y, LAVA):
                    self.set(x, y, FIRE)
            elif m == LAVA:
                if pyxel.frame_count % 3 == 0:
                    self.flow_liquid(x, y, LAVA, 0)
                if chance(0.015) and self.get(x, y - 1) == AIR:
                    self.set(x, y - 1, FIRE)
            elif m == SAND:
                if self.get(x, y + 1) in (AIR, WATER, TOXIC):
                    self.swap(x, y, x, y + 1)
                else:
                    dx = random.choice((-1, 1))
                    if self.get(x + dx, y + 1) in (AIR, WATER, TOXIC):
                        self.swap(x, y, x + dx, y + 1)
            elif m == FIRE:
                self.burn_cell(x, y)
            elif m == SMOKE:
                if chance(0.035):
                    self.set(x, y, AIR)
                elif self.get(x, y - 1) == AIR:
                    self.swap(x, y, x + random.choice((-1, 0, 1)), y - 1)

    def swap(self, x, y, nx, ny):
        if not self.inb(nx, ny):
            return False
        i, j = self.idx(x, y), self.idx(nx, ny)
        self.grid[i], self.grid[j] = self.grid[j], self.grid[i]
        return True

    def flow_liquid(self, x, y, mat, fast):
        below = self.get(x, y + 1)
        if below in FLOW_EMPTY:
            self.swap(x, y, x, y + 1)
            return
        if mat == LAVA and below == WATER:
            self.set(x, y, ROCK)
            self.set(x, y + 1, SMOKE)
            return
        dirs = (-1, 1) if chance(0.5) else (1, -1)
        for dx in dirs:
            if self.get(x + dx, y + 1) in FLOW_EMPTY:
                self.swap(x, y, x + dx, y + 1)
                return
        if fast or chance(0.45):
            for dx in dirs:
                if self.get(x + dx, y) in FLOW_EMPTY:
                    self.swap(x, y, x + dx, y)
                    return

    def neighbor_is(self, x, y, mat):
        return self.get(x + 1, y) == mat or self.get(x - 1, y) == mat or \
            self.get(x, y + 1) == mat or self.get(x, y - 1) == mat

    def burn_cell(self, x, y):
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            n = self.get(x + dx, y + dy)
            if n in (VINE, OIL, COAL) and chance(0.18):
                self.set(x + dx, y + dy, FIRE)
            elif n == WATER:
                self.set(x, y, SMOKE)
                return
        if chance(0.03):
            self.set(x, y, SMOKE)
        elif chance(0.07) and self.get(x, y - 1) == AIR:
            self.swap(x, y, x + random.choice((-1, 0, 1)), y - 1)

    # -- shots, enemies, pickups ---------------------------------------
    def update_shots(self):
        for s in list(self.shots):
            s.life -= 1
            s.vy += s.gravity
            if s.trail and chance(0.45):
                self.drop_material(int(s.x), int(s.y), s.trail, 1)
            hit = False
            steps = max(1, int(max(abs(s.vx), abs(s.vy))) + 1)
            for _ in range(steps):
                nx = s.x + s.vx / steps
                ny = s.y + s.vy / steps
                if not self.inb(int(nx), int(ny)):
                    hit = True
                    break
                if s.owner == "player":
                    e = self.enemy_at(nx, ny, 5)
                    if e:
                        self.damage_enemy(e, s.dmg, s.element, s.burn)
                        hit = True
                        break
                else:
                    p = self.player
                    if p.x - 2 <= nx <= p.x + p.w + 2 and p.y - 2 <= ny <= p.y + p.h + 2:
                        self.hurt_player(1, "A hostile spell hits you.", 8)
                        if s.element == FIRE:
                            p.burn = min(100, p.burn + 55)
                        elif s.element == TOXIC:
                            p.toxic = min(100, p.toxic + 35)
                        hit = True
                        break
                m = self.get(int(nx), int(ny))
                if m in SOLIDS or m in LIQUIDS:
                    if s.bounce > 0 and m in SOLIDS:
                        if self.solid(int(s.x + s.vx / steps), int(s.y)):
                            s.vx = -s.vx * 0.72
                        if self.solid(int(s.x), int(s.y + s.vy / steps)):
                            s.vy = -s.vy * 0.72
                        s.bounce -= 1
                    else:
                        hit = True
                    break
                s.x, s.y = nx, ny
            if hit or s.life <= 0:
                self.spell_impact(s)
                if s in self.shots:
                    self.shots.remove(s)

    def spell_impact(self, s):
        r = s.radius
        if s.boom:
            self.shake = max(self.shake, 8)
            self.play(6)
        self.damage_terrain(int(s.x), int(s.y), r, s.dig, s.element)
        for e in list(self.enemies):
            if dist2(e.x + e.w / 2, e.y + e.h / 2, s.x, s.y) < (r + 9) * (r + 9):
                self.damage_enemy(e, s.dmg * (2 if s.boom else 1), s.element, s.burn)
        p = self.player
        if s.owner != "player" and dist2(p.x + 3, p.y + 5, s.x, s.y) < (r + 8) * (r + 8):
            self.hurt_player(1 + int(s.boom), "The blast catches you.", 8)
        for _ in range(8 + r):
            a = random.random() * math.tau
            self.parts.append([s.x, s.y, math.cos(a) * random.uniform(0.3, 1.9),
                               math.sin(a) * random.uniform(0.3, 1.9), random.randint(8, 20), s.color])

    def damage_terrain(self, cx, cy, radius, power, element=None):
        if power <= 0 and element is None:
            return
        r = max(1, radius)
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if not self.inb(x, y) or dist2(x, y, cx, cy) > r * r:
                    continue
                m = self.get(x, y)
                if m == BRICK:
                    continue
                if element == FIRE and m in (AIR, VINE, OIL, COAL):
                    self.set(x, y, FIRE)
                elif element == TOXIC and m == AIR and chance(0.35):
                    self.set(x, y, TOXIC)
                elif m in SOLIDS:
                    resist = {DIRT: 2, SAND: 1, COAL: 2, GOLD_ORE: 4, ROCK: 7}.get(m, 99)
                    if power >= resist or chance(power / (resist * 3.0)):
                        if m == GOLD_ORE and chance(0.35):
                            self.pickups.append(Pickup("gold", x, y, random.randint(2, 8)))
                        self.set(x, y, AIR if element != FIRE else FIRE)
                elif m in LIQUIDS and element == FIRE:
                    self.set(x, y, SMOKE if m == WATER else FIRE)

    def drop_material(self, x, y, mat, n):
        for _ in range(n):
            px = x + random.randint(-1, 1)
            py = y + random.randint(-1, 1)
            if self.inb(px, py) and self.get(px, py) in (AIR, FIRE, SMOKE, VINE):
                self.set(px, py, mat)

    def enemy_at(self, x, y, r):
        for e in self.enemies:
            if e.x - r <= x <= e.x + e.w + r and e.y - r <= y <= e.y + e.h + r:
                return e
        return None

    def damage_enemy(self, e, dmg, element=None, burn=0):
        if e.kind == "stendari" and element == FIRE:
            dmg *= 0.25
        if e.kind == "alchemist":
            dmg *= 0.75
        e.hp -= dmg
        e.awake = True
        e.hurt_flash = 8
        if burn:
            e.burn = max(e.burn, burn)
        if element == TOXIC:
            e.toxic = max(e.toxic, 80)
        if e.hp <= 0 and e in self.enemies:
            self.enemies.remove(e)
            self.kills += 1
            self.play(1)
            for _ in range(random.randint(2, 5) + (4 if e.kind == "alchemist" else 0)):
                self.pickups.append(Pickup("gold", e.x + random.randint(-2, 6), e.y, random.randint(4, 11)))
            if e.kind == "alchemist" and not self.player.has_orb:
                self.pickups.append(Pickup("spell", e.x, e.y - 5, random.choice(("bomb", "fire", "toxic"))))
                self.say("The alchemist's wand cracks open.", 10)

    def update_enemies(self):
        p = self.player
        for e in list(self.enemies):
            e.hurt_flash = max(0, e.hurt_flash - 1)
            if dist2(e.x, e.y, p.x, p.y) < 9800:
                e.awake = True
            if e.burn:
                e.burn -= 1
                if pyxel.frame_count % 35 == 0:
                    self.damage_enemy(e, 0.6, FIRE, 0)
                if chance(0.12):
                    self.drop_material(int(e.x + e.w / 2), int(e.y + e.h / 2), FIRE, 1)
            if e.toxic:
                e.toxic -= 1
                if pyxel.frame_count % 48 == 0:
                    self.damage_enemy(e, 0.4, TOXIC, 0)
            if e not in self.enemies:
                continue
            if not e.awake:
                continue
            if e.flying:
                self.fly_enemy(e)
            else:
                self.walk_enemy(e)
            if self.enemy_touches_player(e):
                self.hurt_player(1, "A %s bites you." % e.kind, 8)
            if e.fire_cd > 0:
                e.fire_cd -= 1
            if e.fire_cd == 0 and dist2(e.x, e.y, p.x, p.y) < 6500:
                self.enemy_cast(e)

    def walk_enemy(self, e):
        p = self.player
        if abs(p.x - e.x) < 90:
            e.vx += 0.08 if p.x > e.x else -0.08
        elif chance(0.02):
            e.vx *= -1
        e.vx = clamp(e.vx, -1.15, 1.15)
        e.face = 1 if e.vx >= 0 else -1
        if e.kind == "slime" and e.ground and chance(0.03):
            e.vy = -2.6
        e.vy += 0.18
        e.vy = min(e.vy, 3.6)
        self.move_body(e)
        if e.kind == "slime" and chance(0.03):
            self.drop_material(int(e.x + e.w / 2), int(e.y + e.h), TOXIC, 1)

    def fly_enemy(self, e):
        p = self.player
        tx = p.x - e.x
        ty = p.y - e.y - 8
        d = max(1, math.sqrt(tx * tx + ty * ty))
        e.vx += tx / d * 0.08
        e.vy += ty / d * 0.06
        e.vx = clamp(e.vx, -1.45, 1.45)
        e.vy = clamp(e.vy, -1.35, 1.35)
        if self.rect_solid(e.x + e.vx, e.y, e.w, e.h):
            e.vx *= -0.6
        else:
            e.x += e.vx
        if self.rect_solid(e.x, e.y + e.vy, e.w, e.h):
            e.vy *= -0.6
        else:
            e.y += e.vy
        e.face = 1 if e.vx >= 0 else -1

    def enemy_touches_player(self, e):
        p = self.player
        return not (e.x + e.w < p.x or p.x + p.w < e.x or e.y + e.h < p.y or p.y + p.h < e.y)

    def enemy_cast(self, e):
        p = self.player
        dx = p.x + p.w / 2 - (e.x + e.w / 2)
        dy = p.y + p.h / 2 - (e.y + e.h / 2)
        a = math.atan2(dy, dx)
        sid = "fire" if e.kind in ("stendari", "alchemist") else "spark"
        speed = 2.35 if e.kind != "alchemist" else 3.0
        self.shots.append(Shot(e.x + e.w / 2, e.y + e.h / 2,
                               math.cos(a) * speed, math.sin(a) * speed, sid, "enemy"))
        self.shots[-1].dmg = 1
        self.shots[-1].owner = "enemy"
        e.fire_cd = random.randint(50, 95) if e.kind != "alchemist" else random.randint(28, 48)

    def update_pickups(self):
        p = self.player
        for it in list(self.pickups):
            it.t += 1
            if it.kind in ("gold", "heal"):
                it.vy = min(2.3, it.vy + 0.12)
                if not self.rect_solid(it.x, it.y + it.vy, 3, 3):
                    it.y += it.vy
                else:
                    it.vy *= -0.25
            if dist2(it.x, it.y, p.x + p.w / 2, p.y + p.h / 2) < 95:
                if it.kind == "gold":
                    p.gold += int(it.value)
                    self.pickups.remove(it)
                    if chance(0.3):
                        self.play(3)
                elif it.kind == "heal":
                    p.hp = min(p.max_hp, p.hp + 1)
                    self.pickups.remove(it)
                    self.say("A heart warms under your coat.", 8)
                    self.play(5)
                elif it.kind == "orb":
                    p.has_orb = True
                    self.pickups.remove(it)
                    self.say("You take the Sampo shard. Escape.", 10)
                    self.play(7)
                elif pyxel.btnp(pyxel.KEY_E):
                    if it.kind == "spell":
                        self.spell_bag.append(it.value)
                        self.pickups.remove(it)
                        self.say("Learned %s." % SPELLS[it.value]["name"], 13)
                        self.play(5)
                    elif it.kind == "wand":
                        self.add_or_replace_wand(it.value)
                        self.pickups.remove(it)
                        self.say("Picked up %s." % it.value.name, 14)
                        self.play(5)

    def try_use_nearby(self):
        for it in self.pickups:
            if it.kind in ("spell", "wand") and dist2(it.x, it.y, self.player.x, self.player.y) < 260:
                return

    def add_or_replace_wand(self, wand):
        if len(self.wands) < 3:
            self.wands.append(wand)
            self.active_wand = len(self.wands) - 1
        else:
            self.wands[self.active_wand] = wand

    def update_particles(self):
        for p in list(self.parts):
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.04
            p[4] -= 1
            if p[4] <= 0:
                self.parts.remove(p)
        self.shake = max(0, self.shake - 0.45)

    def update_camera(self):
        p = self.player
        self.camx += ((p.x + p.w / 2) - SW / 2 - self.camx) * 0.12
        self.camy += ((p.y + p.h / 2) - VIEW_H / 2 - self.camy) * 0.10
        self.camx = int(clamp(self.camx, 0, WORLD_W - SW))
        self.camy = int(clamp(self.camy, 0, WORLD_H - VIEW_H))

    def check_portal(self):
        self.portal_t += 1
        p = self.player
        near = dist2(p.x + p.w / 2, p.y + p.h / 2, self.portal_x, self.portal_y) < 210
        if near and pyxel.btnp(pyxel.KEY_E):
            if self.depth == len(BIOMES) - 1:
                if p.has_orb:
                    self.screen = "win"
                    self.win_t = 0
                    self.play(7)
                else:
                    self.say("The portal wants the Sampo shard.", 10)
            else:
                self.enter_shop()

    # -- shop and wand lab ---------------------------------------------
    def enter_shop(self):
        self.prepare_shop()
        self.screen = "shop"
        self.shop_sel = 0
        self.player.hp = min(self.player.max_hp, self.player.hp + 2)
        self.flask_amt = min(100, self.flask_amt + 45)
        self.say("The Holy Mountain grants a breath.", 10)
        self.play(7)

    def prepare_shop(self):
        self.shop = [
            {"kind": "heal", "name": "Heart refill", "price": 45 + self.depth * 20},
            {"kind": "flask", "name": "Fill water flask", "price": 20 + self.depth * 8},
        ]
        for _ in range(2):
            sid = random.choice(SPELL_POOL[min(1 + self.depth, len(SPELL_POOL) - 1):])
            self.shop.append({"kind": "spell", "name": SPELLS[sid]["name"], "value": sid,
                              "price": SPELLS[sid]["price"] + self.depth * 9})
        self.shop.append({"kind": "wand", "name": "Random wand", "value": self.random_wand(self.depth + 2),
                          "price": 80 + self.depth * 45})

    def update_shop(self):
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.shop_sel = (self.shop_sel - 1) % len(self.shop)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.shop_sel = (self.shop_sel + 1) % len(self.shop)
        if pyxel.btnp(pyxel.KEY_TAB):
            self.return_screen = "shop"
            self.edit_allowed = True
            self.edit_wand = min(self.active_wand, len(self.wands) - 1)
            self.edit_slot = min(self.edit_slot, len(self.wands[self.edit_wand].slots) - 1)
            self.screen = "wands"
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_Z):
            self.buy_selected()
        if pyxel.btnp(pyxel.KEY_E):
            self.start_biome(self.depth + 1)
            self.screen = "play"

    def buy_selected(self):
        item = self.shop[self.shop_sel]
        price = item["price"]
        if self.player.gold < price:
            self.say("Not enough gold.", 5)
            self.play(2)
            return
        self.player.gold -= price
        kind = item["kind"]
        if kind == "heal":
            self.player.hp = self.player.max_hp
            self.say("The mountain knits your heart.", 8)
        elif kind == "flask":
            self.flask_amt = 100
            self.flask_mat = WATER
            self.say("The flask is clean water again.", 12)
        elif kind == "spell":
            self.spell_bag.append(item["value"])
            self.say("Bought %s." % SPELLS[item["value"]]["name"], 13)
        elif kind == "wand":
            self.add_or_replace_wand(item["value"])
            self.say("Bought %s." % item["value"].name, 14)
        self.shop.pop(self.shop_sel)
        if not self.shop:
            self.prepare_shop()
        self.shop_sel %= len(self.shop)
        self.play(5)

    def update_wands_screen(self):
        if pyxel.btnp(pyxel.KEY_TAB) or pyxel.btnp(pyxel.KEY_ESCAPE):
            old = self.active_wand
            self.active_wand = min(self.edit_wand, len(self.wands) - 1)
            if self.return_screen == "play" and self.active_wand != old:
                self.say("Wand %d: %s" % (self.active_wand + 1, self.wands[self.active_wand].name), 13)
            self.screen = self.return_screen
            return
        for i, key in enumerate((pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3)):
            if pyxel.btnp(key) and i < len(self.wands):
                self.edit_wand = i
                self.active_wand = i
                self.edit_slot = min(self.edit_slot, len(self.wands[self.edit_wand].slots) - 1)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.edit_wand = (self.edit_wand - 1) % len(self.wands)
            self.edit_slot = min(self.edit_slot, len(self.wands[self.edit_wand].slots) - 1)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.edit_wand = (self.edit_wand + 1) % len(self.wands)
            self.edit_slot = min(self.edit_slot, len(self.wands[self.edit_wand].slots) - 1)
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
            self.edit_slot = (self.edit_slot - 1) % len(self.wands[self.edit_wand].slots)
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
            self.edit_slot = (self.edit_slot + 1) % len(self.wands[self.edit_wand].slots)
        if self.edit_allowed and (pyxel.btnp(pyxel.KEY_Z) or pyxel.btnp(pyxel.KEY_RETURN)):
            choices = [None] + sorted(set(self.spell_bag), key=lambda s: SPELLS[s]["name"])
            wand = self.wands[self.edit_wand]
            cur = wand.slots[self.edit_slot]
            ni = (choices.index(cur) + 1) % len(choices) if cur in choices else 0
            wand.slots[self.edit_slot] = choices[ni]
            self.play(3)
        if self.edit_allowed and pyxel.btnp(pyxel.KEY_X):
            self.wands[self.edit_wand].slots[self.edit_slot] = None
            self.play(3)

    # -- drawing --------------------------------------------------------
    def draw(self):
        if self.screen == "title":
            self.draw_title()
        elif self.screen == "shop":
            self.draw_shop()
        elif self.screen == "wands":
            self.draw_wand_lab()
        elif self.screen == "dead":
            self.draw_playfield()
            self.draw_end("YOU DIED", "R or Enter starts a new run", 8)
        elif self.screen == "win":
            self.win_t += 1
            self.draw_playfield()
            self.draw_end("THE WORK", "The Sampo shard warms the sky", 10)
        else:
            self.draw_playfield()

    def draw_playfield(self):
        ox = random.randint(-int(self.shake), int(self.shake)) if self.shake > 0.5 else 0
        oy = random.randint(-int(self.shake), int(self.shake)) if self.shake > 0.5 else 0
        pyxel.cls(0)
        self.draw_cave_background(ox, oy)
        self.draw_world(ox, oy)
        self.draw_portal(ox, oy)
        for it in self.pickups:
            self.draw_pickup(it, ox, oy)
        for s in self.shots:
            self.draw_shot(s, ox, oy)
        for e in self.enemies:
            self.draw_enemy(e, ox, oy)
        self.draw_player(ox, oy)
        for p in self.parts:
            sx = int(p[0] - self.camx + ox)
            sy = int(p[1] - self.camy + HUD_H + oy)
            if 0 <= sx < SW and HUD_H <= sy < SH - LOG_H:
                pyxel.pset(sx, sy, p[5])
        self.draw_hud()
        self.draw_log()
        if self.screen == "play":
            self.draw_prompt()

    def draw_cave_background(self, ox, oy):
        pyxel.rect(0, HUD_H, SW, VIEW_H, 0)
        for i in range(24):
            x = (i * 47 - self.camx // 4) % (SW + 40) - 20
            y = HUD_H + 12 + ((i * 29 - self.camy // 5) % (VIEW_H - 22))
            col = 1 if i % 2 else 5
            pyxel.pset(x + ox, y + oy, col)
        for y in range(0, VIEW_H, 18):
            col = 1 if y < VIEW_H // 2 else 0
            pyxel.line(0, HUD_H + y + oy, SW, HUD_H + y + oy, col)

    def draw_world(self, ox, oy):
        cx, cy = int(self.camx), int(self.camy)
        for sy in range(VIEW_H):
            wy = cy + sy
            if not (0 <= wy < WORLD_H):
                continue
            base = wy * WORLD_W
            screen_y = HUD_H + sy + oy
            if screen_y < HUD_H or screen_y >= SH - LOG_H:
                continue
            for sx in range(SW):
                wx = cx + sx
                if 0 <= wx < WORLD_W:
                    m = self.grid[base + wx]
                    if m:
                        pyxel.pset(sx + ox, screen_y, self.material_color(m, wx, wy))

    def draw_spell_icon(self, sid, x, y, s=10):
        col = SPELLS[sid]["color"]
        cx, cy = x + s // 2, y + s // 2
        if sid == "spark":
            pyxel.line(cx, y + 1, cx, y + s - 2, col)
            pyxel.line(x + 1, cy, x + s - 2, cy, col)
            pyxel.pset(cx - 2, cy - 2, 7)
            pyxel.pset(cx + 2, cy + 1, 12)
        elif sid == "arrow":
            pyxel.line(x + 1, y + s - 2, x + s - 3, y + 2, col)
            pyxel.tri(x + s - 2, y + 1, x + s - 2, y + 5, x + s - 6, y + 2, col)
            pyxel.pset(x + 2, y + s - 3, 7)
        elif sid == "digger":
            pyxel.line(x + 2, y + s - 2, x + s - 3, y + 2, 4)
            pyxel.line(x + s - 7, y + 2, x + s - 1, y + 4, col)
            pyxel.line(x + s - 6, y + 1, x + s - 2, y + 6, col)
        elif sid == "bubble":
            r = max(1, s // 4)
            pyxel.circb(cx - 2, cy + 1, r, col)
            pyxel.circb(cx + 3, y + 3, max(1, r - 1), 12)
            pyxel.pset(cx - 3, cy, 7)
        elif sid == "fire":
            pyxel.tri(cx, y + 1, x + 1, y + s - 1, x + s - 2, y + s - 1, 9)
            pyxel.tri(cx + 1, y + 3, cx - 2, y + s - 1, cx + 3, y + s - 1, 10)
            pyxel.pset(cx, cy, 8)
        elif sid == "toxic":
            r = max(2, s // 3)
            pyxel.circ(cx, cy, r, 11)
            pyxel.circb(cx, cy, r + 1, 15)
            pyxel.pset(cx - 1, cy - 1, 0)
            pyxel.pset(cx + 1, cy - 1, 0)
            pyxel.line(cx - 2, cy + 2, cx + 2, cy + 2, 0)
        elif sid == "bomb":
            r = max(2, s // 3)
            pyxel.circ(cx, cy + 1, r, 5)
            pyxel.pset(cx - 1, cy, 7)
            pyxel.line(cx + r - 1, cy - r + 1, x + s - 1, y + 1, 4)
            pyxel.pset(x + s - 1, y + 1, 10)
        elif sid == "rain":
            self.draw_material_icon(WATER, x, y, s)

    def draw_material_icon(self, mat, x, y, s=8):
        cx, cy = x + s // 2, y + s // 2
        if mat == WATER:
            pyxel.tri(cx, y + 1, x + 2, cy + 2, x + s - 3, cy + 2, 12)
            pyxel.circ(cx, cy + 2, max(2, s // 3), 12)
            pyxel.pset(cx - 1, cy, 7)
        elif mat == TOXIC:
            pyxel.circ(cx, cy + 1, max(2, s // 3), 11)
            pyxel.circb(cx, cy + 1, max(3, s // 3 + 1), 15)
            pyxel.pset(cx - 1, cy, 0)
            pyxel.pset(cx + 1, cy, 0)
            pyxel.pset(cx, cy + 2, 0)
        elif mat == LAVA:
            pyxel.tri(cx, y + 1, x + 1, y + s - 1, x + s - 2, y + s - 1, 9)
            pyxel.tri(cx + 1, y + 3, cx - 2, y + s - 1, cx + 3, y + s - 1, 10)
        elif mat == OIL:
            pyxel.circ(cx, cy + 1, max(2, s // 3), 1)
            pyxel.pset(cx - 1, cy - 1, 6)
            pyxel.pset(cx, cy, 5)
        else:
            pyxel.rect(x + 1, y + 1, max(1, s - 2), max(1, s - 2), self.material_color(mat, x, y))

    def draw_item_icon(self, kind, value, x, y, s=10):
        cx, cy = x + s // 2, y + s // 2
        if kind == "gold":
            pyxel.circ(cx, cy, max(2, s // 3), 10)
            pyxel.pset(cx - 1, cy, 9)
            pyxel.pset(cx + 1, cy + 1, 7)
        elif kind == "heal":
            pyxel.rect(cx - 2, cy - 1, 5, 4, 8)
            pyxel.pset(cx - 3, cy, 8)
            pyxel.pset(cx + 3, cy, 8)
            pyxel.pset(cx, cy + 3, 8)
            pyxel.pset(cx, cy - 2, 7)
        elif kind == "spell":
            pyxel.rectb(x, y, s, s, 5)
            self.draw_spell_icon(value, x + 1, y + 1, max(6, s - 2))
        elif kind == "wand":
            pyxel.line(x + 1, y + s - 2, x + s - 2, y + 2, 14)
            pyxel.pset(x + s - 1, y + 1, 12)
            pyxel.pset(x + s - 3, y + 2, 7)
        elif kind == "orb":
            pyxel.circ(cx, cy, max(3, s // 3), 10)
            pyxel.circb(cx, cy, max(4, s // 2), 14)
            pyxel.pset(cx - 1, cy - 1, 7)
        elif kind == "flask":
            pyxel.rectb(x + 2, y + 1, max(4, s - 4), max(5, s - 2), 6)
            self.draw_material_icon(value if value is not None else WATER, x + 1, y + 1, max(6, s - 2))

    def draw_hud(self):
        pyxel.rect(0, 0, SW, HUD_H, 0)
        p = self.player
        for i in range(p.max_hp):
            x = 5 + i * 8
            col = 8 if i < p.hp else 5
            pyxel.rect(x + 1, 4, 5, 4, col)
            pyxel.pset(x, 5, col)
            pyxel.pset(x + 6, 5, col)
        wx = 52
        for i, wand in enumerate(self.wands):
            x = wx + i * 23
            pyxel.rectb(x, 2, 18, 12, 10 if i == self.active_wand else 5)
            col = 12 if i == 0 else 11 if i == 1 else 14
            pyxel.line(x + 4, 9, x + 13, 5, col)
            pyxel.pset(x + 14, 4, 7)
        wand = self.wands[self.active_wand]
        pyxel.text(124, 3, "$%d" % p.gold, 10)
        pyxel.text(162, 3, "M%02d" % int(wand.mana), 13 if wand.mana > 5 else 8)
        self.draw_material_icon(self.flask_mat, 194, 3, 8)
        pyxel.text(205, 3, "%d/%d" % (self.flask_amt, 100), 12)
        pyxel.rect(234, 3, max(0, int(p.fuel / 6)), 3, 14)
        if p.wet:
            pyxel.text(5, 11, "WET", 12)
        if p.toxic:
            pyxel.text(30, 11, "SLUDGE", 11 if p.toxic < 28 else 8)
        if p.burn:
            pyxel.text(55, 11, "FIRE", 9)

    def draw_log(self):
        pyxel.rect(0, SH - LOG_H, SW, LOG_H, 0)
        if self.message:
            text, col, _ = self.message[-1]
            pyxel.text(4, SH - 14, text[:61], col)
        if self.screen == "play":
            pyxel.text(SW - 86, SH - 7, "Tab wands  E use", 5)

    def draw_prompt(self):
        p = self.player
        if dist2(p.x + 3, p.y + 5, self.portal_x, self.portal_y) < 330:
            self.float_text(self.portal_x - 20, self.portal_y - 22, "E: PORTAL", 10)
        for it in self.pickups:
            if it.kind in ("spell", "wand") and dist2(it.x, it.y, p.x, p.y) < 280:
                label = "E: %s" % ("WAND" if it.kind == "wand" else SPELLS[it.value]["name"].upper())
                self.float_text(it.x - 18, it.y - 14, label[:22], 13)
                break

    def float_text(self, wx, wy, text, col):
        x = int(wx - self.camx)
        y = int(wy - self.camy + HUD_H)
        if 0 <= x < SW and HUD_H <= y < SH - LOG_H:
            pyxel.text(x + 1, y + 1, text, 0)
            pyxel.text(x, y, text, col)

    def draw_portal(self, ox, oy):
        x = int(self.portal_x - self.camx + ox)
        y = int(self.portal_y - self.camy + HUD_H + oy)
        t = self.portal_t
        for r, col in ((12 + (t // 7) % 3, 13), (7 + (t // 5) % 2, 12), (3, 10)):
            pyxel.circb(x, y, r, col)
        pyxel.line(x, y - 10, x, y + 10, 14)
        pyxel.line(x - 7, y, x + 7, y, 14)

    def draw_pickup(self, it, ox, oy):
        x = int(it.x - self.camx + ox)
        y = int(it.y - self.camy + HUD_H + oy + math.sin((pyxel.frame_count + it.t) / 8) * 1.5)
        if not (-8 <= x < SW + 8 and HUD_H - 8 <= y < SH - LOG_H + 8):
            return
        if it.kind == "gold":
            self.draw_item_icon("gold", it.value, x - 4, y - 4, 8)
        elif it.kind == "heal":
            self.draw_item_icon("heal", it.value, x - 5, y - 5, 10)
        elif it.kind == "spell":
            self.draw_item_icon("spell", it.value, x - 5, y - 5, 10)
        elif it.kind == "wand":
            self.draw_item_icon("wand", it.value, x - 6, y - 5, 12)
        elif it.kind == "orb":
            self.draw_item_icon("orb", it.value, x - 6, y - 6, 12)
            pyxel.circb(x, y, 7 + (pyxel.frame_count // 5) % 2, 14)

    def draw_shot(self, s, ox, oy):
        x = int(s.x - self.camx + ox)
        y = int(s.y - self.camy + HUD_H + oy)
        if -8 <= x < SW + 8 and HUD_H - 8 <= y < SH - LOG_H + 8:
            self.draw_spell_icon(s.sid, x - 4, y - 4, 8)
            pyxel.pset(x - int(s.vx), y - int(s.vy), 7)

    def draw_enemy(self, e, ox, oy):
        x = int(e.x - self.camx + ox)
        y = int(e.y - self.camy + HUD_H + oy)
        if not (-14 <= x < SW + 14 and HUD_H - 14 <= y < SH - LOG_H + 14):
            return
        col = 8 if e.hurt_flash else {"slime": 11, "hiisi": 6, "stendari": 9, "fly": 14, "alchemist": 10}[e.kind]
        pyxel.elli(x - 1, y + e.h - 1, e.w + 2, 3, 1)
        if e.kind == "slime":
            pyxel.elli(x, y + 3, 8, 6, col)
            pyxel.pset(x + 2, y + 5, 0)
            pyxel.pset(x + 5, y + 5, 0)
        elif e.kind == "fly":
            flap = (pyxel.frame_count // 4) % 2
            pyxel.tri(x - 4, y + 2 + flap, x + 2, y + 4, x, y, 13)
            pyxel.tri(x + 10, y + 2 + flap, x + 5, y + 4, x + 7, y, 13)
            pyxel.rect(x + 2, y + 2, 5, 5, col)
        elif e.kind == "hiisi":
            pyxel.rect(x + 1, y + 2, 6, 7, col)
            pyxel.rect(x + 2, y, 5, 4, 5)
            pyxel.line(x + 4, y + 4, x + 4 + e.face * 7, y + 3, 6)
        elif e.kind == "stendari":
            pyxel.rect(x + 1, y + 2, 6, 7, col)
            pyxel.tri(x + 1, y + 2, x + 4, y - 4, x + 7, y + 2, 8)
            pyxel.pset(x + 4 + e.face * 4, y - 2, 10)
        else:
            pyxel.rect(x, y + 1, 10, 12, 5)
            pyxel.rect(x + 2, y - 3, 6, 4, col)
            pyxel.line(x + 5, y + 3, x + 5 + e.face * 11, y - 1, 14)
        if e.hp < e.max_hp:
            pyxel.rect(x, y - 6, e.w, 2, 1)
            pyxel.rect(x, y - 6, max(1, int(e.w * e.hp / e.max_hp)), 2, 8)

    def draw_player(self, ox, oy):
        p = self.player
        x = int(p.x - self.camx + ox)
        y = int(p.y - self.camy + HUD_H + oy)
        if p.invuln and (pyxel.frame_count // 3) % 2:
            return
        bob = 1 if not p.ground and p.vy < 0 else (pyxel.frame_count // 8) % 2 if abs(p.vx) > 0.2 and p.ground else 0
        pyxel.elli(x - 1, y + 9, 9, 3, 1)
        pyxel.rect(x + 1, y + 5 - bob, 5, 5, 14)
        pyxel.rect(x + 2, y + 2 - bob, 4, 4, 4)
        pyxel.tri(x - 1, y + 3 - bob, x + 4, y - 4 - bob, x + 8, y + 3 - bob, 14)
        pyxel.pset(x + (5 if p.face > 0 else 2), y + 3 - bob, 0)
        ang = self.aim_angle()
        wx = x + 3 + int(math.cos(ang) * 8)
        wy = y + 5 - bob + int(math.sin(ang) * 8)
        pyxel.line(x + 3, y + 5 - bob, wx, wy, 3)
        pyxel.pset(wx + int(math.cos(ang) * 2), wy + int(math.sin(ang) * 2), 12)

    def draw_title(self):
        pyxel.cls(0)
        t = pyxel.frame_count
        for i in range(58):
            x = (i * 53 + t * (1 + i % 3) // 4) % SW
            y = (i * 31 + t * (i % 2) // 3) % SH
            col = (1, 5, 11, 15)[i % 4]
            pyxel.pset(x, y, col)
        for x in range(0, SW, 8):
            h = 36 + int(math.sin((x + t) / 18) * 7)
            pyxel.rect(x, SH - h, 9, h, 2 if x % 16 else 3)
            if x % 24 == 0:
                pyxel.rect(x, SH - h - 3, 9, 3, 11)
        self.draw_big_word("NOITA", 45, 34, 5, 8, 9)
        pyxel.text(92, 78, "DEMAKE", 8 if (t // 12) % 2 else 14)
        pyxel.text(58, 96, "pixel caves, wands, liquids, gold", 7)
        items = ("NEW GAME", "WAND GUIDE", "REROLL TITLE CAVE")
        for i, item in enumerate(items):
            y = 118 + i * 13
            if i == self.menu:
                pyxel.text(68, y, ">", 10)
                col = 7
            else:
                col = 5
            pyxel.text(80, y, item, col)
        pyxel.text(35, SH - 18, "A/D move  W levitate  mouse aim  Z/Click cast", 6)
        pyxel.text(86, SH - 8, "pyxel arcade", 13)

    def draw_big_word(self, text, x, y, scale, c1, c2):
        font = {
            "N": ("#..#", "##.#", "#.##", "#..#", "#..#"),
            "O": (".##.", "#..#", "#..#", "#..#", ".##."),
            "I": ("####", ".##.", ".##.", ".##.", "####"),
            "T": ("####", ".##.", ".##.", ".##.", ".##."),
            "A": (".##.", "#..#", "####", "#..#", "#..#"),
        }
        for ch in text:
            glyph = font[ch]
            for yy, row in enumerate(glyph):
                for xx, bit in enumerate(row):
                    if bit == "#":
                        col = c1 if yy < 2 else c2
                        pyxel.rect(x + xx * scale, y + yy * scale, scale - 1, scale - 1, col)
            x += 5 * scale

    def draw_shop(self):
        pyxel.cls(0)
        for i in range(36):
            x = (i * 29 + pyxel.frame_count // 2) % SW
            y = 30 + (i * 17) % 92
            pyxel.pset(x, y, (5, 10, 9)[i % 3])
        pyxel.text(72, 20, "HOLY MOUNTAIN", 10)
        pyxel.text(41, 34, "Buy supplies, edit wands, then descend.", 5)
        pyxel.rectb(24, 49, 208, 82, 5)
        for i, item in enumerate(self.shop):
            y = 57 + i * 13
            if i == self.shop_sel:
                pyxel.rect(29, y - 2, 198, 10, 1)
                pyxel.text(33, y, ">", 10)
            icon_value = item.get("value", WATER if item["kind"] == "flask" else None)
            self.draw_item_icon(item["kind"], icon_value, 45, y - 2, 8)
            pyxel.text(57, y, item["name"][:19], 7)
            pyxel.text(181, y, "$%d" % item["price"], 10 if self.player.gold >= item["price"] else 8)
        pyxel.text(32, 142, "Enter buy    Tab edit wands    E continue", 13)
        pyxel.text(32, 154, "Gold: $%d    HP: %d/%d    Flask: %d%%" %
                   (self.player.gold, self.player.hp, self.player.max_hp, self.flask_amt), 7)
        self.draw_log()

    def draw_wand_lab(self):
        pyxel.cls(0)
        title = "WAND EDITING" if self.edit_allowed else "WANDS"
        pyxel.text(11, 9, title, 10)
        pyxel.text(148, 9, "Tab/Esc select", 13)
        pyxel.rectb(8, 22, 156, 136, 5)
        for wi, wand in enumerate(self.wands):
            y = 30 + wi * 42
            if wi == self.edit_wand:
                pyxel.rect(12, y - 4, 148, 38, 1)
                pyxel.rectb(12, y - 4, 148, 38, 10)
            pyxel.text(18, y, "%d %s" % (wi + 1, wand.name[:18]), 7)
            pyxel.text(18, y + 8, wand.short_stats(), 5)
            for si, sid in enumerate(wand.slots):
                x = 18 + si * 26
                sy = y + 19
                pyxel.rectb(x, sy, 20, 14, 10 if wi == self.edit_wand and si == self.edit_slot else 5)
                if sid:
                    self.draw_spell_icon(sid, x + 5, sy + 2, 10)
        pyxel.rectb(173, 22, 72, 136, 5)
        pyxel.text(179, 29, "SPELLS", 10)
        names = sorted(set(self.spell_bag), key=lambda s: SPELLS[s]["name"])
        for i, sid in enumerate(names[:12]):
            self.draw_spell_icon(sid, 180, 41 + i * 8, 7)
            pyxel.text(190, 42 + i * 8, SPELLS[sid]["name"][:9], 7)
        wand = self.wands[self.edit_wand]
        sid = wand.slots[self.edit_slot]
        pyxel.rectb(8, 164, 237, 22, 5)
        if sid:
            spec = SPELLS[sid]
            self.draw_spell_icon(sid, 15, 170, 8)
            pyxel.text(27, 170, "%s  dmg %.1f  mana %d" %
                       (spec["name"], spec["dmg"], spec["cost"]), 7)
        else:
            pyxel.text(15, 170, "EMPTY SLOT", 5)
        if self.edit_allowed:
            pyxel.text(15, 180, "Up/down wand  Left/right slot  Z cycles  X clears", 13)
        else:
            pyxel.text(15, 180, "Up/down wand  Left/right slot  Tab/Esc selects", 13)

    def draw_end(self, head, sub, col):
        pyxel.rect(30, 48, 196, 86, 0)
        pyxel.rectb(30, 48, 196, 86, col)
        pyxel.text(92, 62, head, col)
        pyxel.text(58, 80, sub, 7)
        pyxel.text(66, 98, "gold $%d   kills %d   depth %s" %
                   (self.player.gold, self.kills, self.biome["name"]), 10)
        pyxel.text(76, 116, "Press R or Enter", 13)

    def screenshot(self, filename):
        self.screen = "play"
        self.update_camera()
        self.draw()
        if not os.path.isabs(filename):
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filename = os.path.join(repo_root, filename)
        pyxel.screenshot(os.path.abspath(filename))


if __name__ == "__main__":
    app = App()
    if "--screenshot" in sys.argv:
        app.screenshot("demos/noita_demake.png")
    else:
        app.run()
