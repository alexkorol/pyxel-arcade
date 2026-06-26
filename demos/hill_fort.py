"""Hill Fort -- a tiny fortress roguelite in 8x8 tiles.

Dig into a hill, mark jobs, let dwarves choose their own work, build a
few useful rooms, and survive the first ugly weeks of fort life.

Controls:  arrows move cursor           Q/E switch z-level
           D designate dig/chop          B build mode
           1-7 pick building             Enter place building
           I inspect                     J job list
           Esc closes menus              X cancel designation/job
           S/L save/load JSON
           R new fort                    H help

Study: compact colony-sim state, 32x32x3 maps, shared job queues,
small-grid BFS pathing, tile-adjacent mining/building, simple needs,
and event pressure without trying to become full Dwarf Fortress.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import random

import pyxel


W = H = 256
TILE = 8
MW = MH = 32
LEVELS = 3
VIEW_ROWS = 24
HUD_Y = VIEW_ROWS * TILE
DAY_FRAMES = 600
SAVE_FILE = "hill_fort_save.json"

PALETTE = [
    0x07080B, 0x15171D, 0x272A30, 0x44484E,
    0x747A80, 0xB8C0C2, 0xF4E7C2, 0xF6C344,
    0x9B5A2E, 0x6E3F22, 0x4A852D, 0x7CC74C,
    0x2255A4, 0x43A0F2, 0xD94B3D, 0xC26AD6,
]

LEVEL_NAMES = ("surface", "workshops", "deep river")
DWARF_NAMES = ("Urist", "Mosus", "Domas", "Rakust", "Iden", "Mistem", "Kogan", "Lolor")

BUILDINGS = [
    {
        "key": "stockpile",
        "name": "Stockpile",
        "cost": {"wood": 1},
        "passable": True,
        "note": "keeps food, stone, and arguments in one place",
    },
    {
        "key": "bed",
        "name": "Bed",
        "cost": {"wood": 2},
        "passable": True,
        "note": "tired dwarves recover mood here",
    },
    {
        "key": "door",
        "name": "Door",
        "cost": {"wood": 1},
        "passable": True,
        "note": "slows raiders and improves room dignity",
    },
    {
        "key": "wall",
        "name": "Wall",
        "cost": {"stone": 2},
        "passable": False,
        "note": "blocks paths until somebody knocks it down",
    },
    {
        "key": "carpenter",
        "name": "Carpenter",
        "cost": {"wood": 4},
        "passable": True,
        "note": "turns spare logs into comfort over time",
    },
    {
        "key": "mason",
        "name": "Mason",
        "cost": {"stone": 4},
        "passable": True,
        "note": "makes stonework and walls less shameful",
    },
    {
        "key": "stairs",
        "name": "Stairs",
        "cost": {"stone": 3},
        "passable": True,
        "note": "punches a compact up/down shaft",
    },
]

BUILD_BY_KEY = {b["key"]: b for b in BUILDINGS}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def trim(text, chars):
    return text if len(text) <= chars else text[:max(0, chars - 1)] + "."


def manhattan(a, b):
    return abs(a[1] - b[1]) + abs(a[2] - b[2]) + abs(a[0] - b[0]) * 9


@dataclass
class Tile:
    kind: str = "stone"
    build: str = ""
    designated: str = ""
    damage: int = 0

    def save(self):
        return [self.kind, self.build, self.designated, self.damage]

    @classmethod
    def load(cls, data):
        return cls(data[0], data[1], data[2], data[3])


@dataclass
class Job:
    id: int
    kind: str
    z: int
    x: int
    y: int
    build: str = ""
    claimed: int = -1
    work: int = 0

    def save(self):
        return self.__dict__.copy()

    @classmethod
    def load(cls, data):
        return cls(**data)


@dataclass
class Dwarf:
    id: int
    name: str
    z: int
    x: int
    y: int
    hp: int = 6
    hunger: float = 10.0
    thirst: float = 10.0
    tired: float = 12.0
    mood: float = 75.0
    task: str = "idle"
    job_id: int = -1
    target: int = -1
    path: list = field(default_factory=list)
    step_cd: int = 0
    work: int = 0

    def save(self):
        data = self.__dict__.copy()
        data["path"] = [list(p) for p in self.path]
        return data

    @classmethod
    def load(cls, data):
        data = data.copy()
        data["path"] = [tuple(p) for p in data.get("path", [])]
        return cls(**data)


@dataclass
class Enemy:
    id: int
    kind: str
    z: int
    x: int
    y: int
    hp: int = 3
    path: list = field(default_factory=list)
    step_cd: int = 0

    def save(self):
        data = self.__dict__.copy()
        data["path"] = [list(p) for p in self.path]
        return data

    @classmethod
    def load(cls, data):
        data = data.copy()
        data["path"] = [tuple(p) for p in data.get("path", [])]
        return cls(**data)


class App:
    def __init__(self):
        pyxel.init(W, H, title="hill fort", fps=30, quit_key=pyxel.KEY_NONE)
        pyxel.mouse(False)
        pyxel.colors[:] = PALETTE
        self.seed = random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.state = "title"
        self.messages = []
        self.new_fort()

    def run(self):
        pyxel.run(self.update, self.draw)

    # -- fort setup -----------------------------------------------------
    def new_fort(self):
        self.rng = random.Random(self.seed)
        self.tiles = [[[Tile() for _ in range(MH)] for _ in range(MW)]
                      for _ in range(LEVELS)]
        self.jobs = []
        self.dwarves = []
        self.enemies = []
        self.next_job = 1
        self.next_enemy = 1
        self.z = 0
        self.cx, self.cy = 16, 22
        self.cam_y = 5
        self.mode = "mine"
        self.build_i = 0
        self.day = 1
        self.clock = 0
        self.threat = 0
        self.comfort = 0
        self.stock_cap = 99
        self.game_over = False
        self.end_text = ""
        self.resources = {
            "wood": 12,
            "stone": 0,
            "food": 49,
            "drink": 42,
            "ore": 0,
            "tools": 6,
        }
        self.messages = []
        self.make_map()
        self.make_dwarves()
        self.say("Seven dwarves, zero rooms, one optimistic hill.")
        self.say("Start outside. Dig in before anyone gets poetic.")

    def make_map(self):
        # Surface: grass with one diggable hill, trees, rocks, pond, and a path.
        for y in range(MH):
            for x in range(MW):
                self.t(0, x, y).kind = "grass"
        for y in range(MH):
            for x in range(MW):
                dx = (x - 16) / 10.5
                dy = (y - 15) / 8.0
                if dx * dx + dy * dy < 1.0:
                    self.t(0, x, y).kind = "hill"
        for y in range(23, 32):
            self.t(0, 16, y).kind = "dirt"
            if y % 2 == 0 and 17 < MW:
                self.t(0, 17, y).kind = "dirt"
        for _ in range(38):
            x, y = self.rng.randrange(MW), self.rng.randrange(MH)
            if self.t(0, x, y).kind == "grass" and not (12 < x < 20 and y > 18):
                self.t(0, x, y).kind = "tree"
        for _ in range(28):
            x, y = self.rng.randrange(MW), self.rng.randrange(MH)
            if self.t(0, x, y).kind == "grass":
                self.t(0, x, y).kind = "rock"
        for y in range(3, 8):
            for x in range(3, 8):
                if (x - 5) ** 2 + (y - 5) ** 2 < 8:
                    self.t(0, x, y).kind = "river"

        # Middle layer: sealed stone. The player must build stairs into it.
        for x in range(MW):
            for y in range(MH):
                self.t(1, x, y).kind = "stone"
        for x in range(10, 23):
            for y in range(8, 25):
                if self.rng.random() < 0.08:
                    self.t(1, x, y).kind = "ore" if self.rng.random() < 0.35 else "stone"

        # Deep layer: sealed river and better ore, but events get meaner here.
        for x in range(MW):
            for y in range(MH):
                self.t(2, x, y).kind = "stone"
        for y in range(MH):
            rx = 21 + (y // 5) % 3
            for dx in (-1, 0, 1):
                if 0 <= rx + dx < MW:
                    self.t(2, rx + dx, y).kind = "river"
        for _ in range(65):
            x, y = self.rng.randrange(4, 28), self.rng.randrange(3, 30)
            if self.t(2, x, y).kind == "stone":
                self.t(2, x, y).kind = "ore"

    def make_dwarves(self):
        starts = [(16, 25), (15, 25), (17, 25), (16, 26),
                  (15, 26), (17, 26), (16, 27)]
        for i, (x, y) in enumerate(starts):
            self.dwarves.append(Dwarf(i, DWARF_NAMES[i], 0, x, y))

    def t(self, z, x, y):
        return self.tiles[z][x][y]

    def in_bounds(self, x, y):
        return 0 <= x < MW and 0 <= y < MH

    def say(self, text):
        self.messages.append(text)
        del self.messages[:-8]

    # -- persistence ----------------------------------------------------
    def save_game(self):
        data = {
            "seed": self.seed,
            "resources": self.resources,
            "day": self.day,
            "clock": self.clock,
            "threat": self.threat,
            "comfort": self.comfort,
            "stock_cap": self.stock_cap,
            "cursor": [self.z, self.cx, self.cy, self.cam_y],
            "tiles": [[[self.tiles[z][x][y].save() for y in range(MH)]
                       for x in range(MW)] for z in range(LEVELS)],
            "jobs": [j.save() for j in self.jobs],
            "dwarves": [d.save() for d in self.dwarves],
            "enemies": [e.save() for e in self.enemies],
            "next_job": self.next_job,
            "next_enemy": self.next_enemy,
            "messages": self.messages,
        }
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            self.say("Saved a very small mountain of paperwork.")
        except OSError:
            self.say("The save clerk dropped the slate.")

    def load_game(self):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            self.say("No save ledger found.")
            return
        self.seed = data["seed"]
        self.resources = data["resources"]
        self.day = data["day"]
        self.clock = data["clock"]
        self.threat = data["threat"]
        self.comfort = data.get("comfort", 0)
        self.stock_cap = data.get("stock_cap", 99)
        self.z, self.cx, self.cy, self.cam_y = data["cursor"]
        self.tiles = [[[Tile.load(data["tiles"][z][x][y]) for y in range(MH)]
                       for x in range(MW)] for z in range(LEVELS)]
        self.jobs = [Job.load(j) for j in data["jobs"]]
        self.dwarves = [Dwarf.load(d) for d in data["dwarves"]]
        self.enemies = [Enemy.load(e) for e in data["enemies"]]
        self.next_job = data["next_job"]
        self.next_enemy = data["next_enemy"]
        self.messages = data.get("messages", [])
        self.game_over = False
        self.state = "play"
        self.say("Loaded. Nobody admits whose fault this is.")

    # -- input ----------------------------------------------------------
    def update(self):
        if self.state == "title":
            if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
                self.seed = random.randrange(1 << 30)
                self.new_fort()
                self.state = "play"
            return
        if pyxel.btnp(pyxel.KEY_R):
            self.seed = random.randrange(1 << 30)
            self.new_fort()
            self.state = "play"
        if self.game_over:
            return

        self.update_input()
        self.update_sim()

    def update_input(self):
        if pyxel.btnp(pyxel.KEY_ESCAPE) and self.mode != "mine":
            self.mode = "mine"
            return
        moved = False
        if pyxel.btnp(pyxel.KEY_LEFT, 10, 3):
            self.cx = max(0, self.cx - 1)
            moved = True
        if pyxel.btnp(pyxel.KEY_RIGHT, 10, 3):
            self.cx = min(MW - 1, self.cx + 1)
            moved = True
        if pyxel.btnp(pyxel.KEY_UP, 10, 3):
            self.cy = max(0, self.cy - 1)
            moved = True
        if pyxel.btnp(pyxel.KEY_DOWN, 10, 3):
            self.cy = min(MH - 1, self.cy + 1)
            moved = True
        if moved:
            self.keep_cursor_visible()
        if pyxel.btnp(pyxel.KEY_Q):
            self.z = max(0, self.z - 1)
            self.keep_cursor_visible()
        if pyxel.btnp(pyxel.KEY_E):
            self.z = min(LEVELS - 1, self.z + 1)
            self.keep_cursor_visible()
        if pyxel.btnp(pyxel.KEY_TAB):
            self.mode = {"mine": "build", "build": "inspect",
                         "inspect": "jobs", "jobs": "mine"}.get(self.mode, "mine")
        if pyxel.btnp(pyxel.KEY_B):
            self.mode = "build"
        if pyxel.btnp(pyxel.KEY_I):
            self.mode = "inspect"
        if pyxel.btnp(pyxel.KEY_J):
            self.mode = "jobs"
        if pyxel.btnp(pyxel.KEY_H):
            self.mode = "help"
        if self.mode == "help" and pyxel.btnp(pyxel.KEY_H):
            self.mode = "mine"
        if pyxel.btnp(pyxel.KEY_D):
            self.designate()
        if pyxel.btnp(pyxel.KEY_X):
            self.cancel_at_cursor()
        for i, key in enumerate((pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3,
                                 pyxel.KEY_4, pyxel.KEY_5, pyxel.KEY_6,
                                 pyxel.KEY_7)):
            if pyxel.btnp(key):
                self.build_i = i
                self.mode = "build"
        if self.mode == "build" and pyxel.btnp(pyxel.KEY_RETURN):
            self.place_build_job()
        if pyxel.btnp(pyxel.KEY_S):
            self.save_game()
        if pyxel.btnp(pyxel.KEY_L):
            self.load_game()

    def keep_cursor_visible(self):
        if self.cy < self.cam_y + 2:
            self.cam_y = max(0, self.cy - 2)
        if self.cy >= self.cam_y + VIEW_ROWS - 2:
            self.cam_y = min(MH - VIEW_ROWS, self.cy - VIEW_ROWS + 3)

    # -- jobs and map editing ------------------------------------------
    def passable(self, z, x, y):
        if not self.in_bounds(x, y):
            return False
        tile = self.t(z, x, y)
        if tile.kind in ("stone", "ore", "hill", "tree", "rock", "river"):
            return False
        if tile.build and not BUILD_BY_KEY.get(tile.build, {}).get("passable", True):
            return False
        return True

    def diggable(self, z, x, y):
        return self.t(z, x, y).kind in ("stone", "ore", "hill", "rock")

    def designate(self):
        tile = self.t(self.z, self.cx, self.cy)
        if tile.kind == "tree":
            if tile.designated != "chop":
                tile.designated = "chop"
                self.add_job("chop", self.z, self.cx, self.cy)
                self.say("Chop marked. The tree looks nervous.")
            return
        if self.diggable(self.z, self.cx, self.cy):
            if tile.designated != "dig":
                tile.designated = "dig"
                self.add_job("dig", self.z, self.cx, self.cy)
                self.say("Dig marked. Surely nothing is below it.")
            return
        self.say("Nothing useful to designate there.")

    def cancel_at_cursor(self):
        tile = self.t(self.z, self.cx, self.cy)
        tile.designated = ""
        before = len(self.jobs)
        self.jobs = [j for j in self.jobs
                     if not (j.z == self.z and j.x == self.cx and j.y == self.cy)]
        if len(self.jobs) != before:
            self.say("Canceled the job before it became tradition.")

    def add_job(self, kind, z, x, y, build=""):
        for job in self.jobs:
            if (job.kind, job.z, job.x, job.y, job.build) == (kind, z, x, y, build):
                return job
        job = Job(self.next_job, kind, z, x, y, build)
        self.next_job += 1
        self.jobs.append(job)
        return job

    def can_pay(self, build):
        for res, n in BUILD_BY_KEY[build]["cost"].items():
            if self.resources.get(res, 0) < n:
                return False
        return True

    def pay(self, build):
        for res, n in BUILD_BY_KEY[build]["cost"].items():
            self.resources[res] -= n

    def place_build_job(self):
        build = BUILDINGS[self.build_i]["key"]
        tile = self.t(self.z, self.cx, self.cy)
        if not self.passable(self.z, self.cx, self.cy):
            self.say("Build on open floor, not inside ambition.")
            return
        if tile.build:
            self.say("That tile is already occupied.")
            return
        if not self.can_pay(build):
            self.say("Need %s." % self.cost_text(build))
            return
        self.pay(build)
        self.add_job("build", self.z, self.cx, self.cy, build)
        self.say("Ordered %s. Someone will get to it." % BUILD_BY_KEY[build]["name"])

    def place_stairs(self, x, y, z):
        self.t(z, x, y).kind = "floor"
        self.t(z, x, y).build = "stairs"
        if z + 1 < LEVELS:
            self.t(z + 1, x, y).kind = "floor"
            self.t(z + 1, x, y).build = "stairs"

    def cost_text(self, build):
        cost = BUILD_BY_KEY[build]["cost"]
        return " ".join("%s%d" % (k[0].upper(), v) for k, v in cost.items()) or "free"

    # -- simulation -----------------------------------------------------
    def update_sim(self):
        self.clock += 1
        if self.clock >= DAY_FRAMES:
            self.clock = 0
            self.new_day()
        if pyxel.frame_count % 90 == 0:
            self.workshops_tick()
        for dwarf in list(self.dwarves):
            self.update_dwarf(dwarf)
        for enemy in list(self.enemies):
            self.update_enemy(enemy)
        self.check_end()

    def new_day(self):
        self.day += 1
        eaten = 0
        drunk = 0
        for d in self.alive_dwarves():
            d.hunger = clamp(d.hunger + 17, 0, 130)
            d.thirst = clamp(d.thirst + 20, 0, 130)
            d.tired = clamp(d.tired + 6, 0, 120)
            if d.hunger > 35 and self.resources["food"] > 0:
                self.resources["food"] -= 1
                eaten += 1
                d.hunger = max(4, d.hunger - 38)
                d.mood = min(100, d.mood + 2)
            if d.thirst > 35 and self.resources["drink"] > 0:
                self.resources["drink"] -= 1
                drunk += 1
                d.thirst = max(4, d.thirst - 42)
                d.mood = min(100, d.mood + 2)
            if d.hunger > 95 or d.thirst > 95:
                d.mood -= 8
                d.hp -= 1 if self.day % 2 == 0 else 0
        self.say("Day %d: %d meals, %d mugs." % (self.day, eaten, drunk))
        self.daily_event()

    def daily_event(self):
        if self.day == 2:
            self.say("Vermin nibble a sack. The sack protests silently.")
            self.resources["food"] = max(0, self.resources["food"] - 4)
        elif self.day == 3:
            self.say("Smoke from the hill is visible in the valley.")
        elif self.day == 4:
            self.spawn_enemy_wave("scout", 2)
            self.say("Raid scouts arrive early and underdressed.")
        elif self.day == 6:
            self.spawn_enemy_wave("raider", 3 + self.threat // 3)
            self.say("A small siege forms. It has opinions.")
        elif self.day % 4 == 0:
            score = self.fort_score()
            need = 8 + max(0, len(self.alive_dwarves()) - 7) * 2
            if score >= need and not self.enemies:
                self.add_migrant()
            else:
                self.say("Migrants inspect the hill and keep walking.")
        elif self.day % 3 == 0:
            self.say(self.rng.choice((
                "Cave noise below: clink, splash, bad idea.",
                "A dwarf writes 'needs more doors' in dust.",
                "The river rises and then pretends it did not.",
                "A barrel is missing. Everyone suspects the barrel.",
            )))
            self.threat += 1

    def workshops_tick(self):
        if self.has_building("carpenter") and self.resources["wood"] > 0:
            self.resources["wood"] -= 1
            self.comfort += 1
            if self.comfort % 3 == 0:
                self.say("The carpenter makes the fort slightly less awful.")
        if self.has_building("mason") and self.resources["stone"] > 0:
            self.resources["stone"] -= 1
            self.resources["tools"] = min(12, self.resources["tools"] + 1)
        if self.has_building("stockpile"):
            self.stock_cap = 140

    def has_building(self, key):
        for z in range(LEVELS):
            for x in range(MW):
                for y in range(MH):
                    if self.t(z, x, y).build == key:
                        return True
        return False

    def count_building(self, key):
        n = 0
        for z in range(LEVELS):
            for x in range(MW):
                for y in range(MH):
                    if self.t(z, x, y).build == key:
                        n += 1
        return n

    def fort_score(self):
        beds = self.count_building("bed")
        stock = self.count_building("stockpile")
        workshops = self.count_building("carpenter") + self.count_building("mason")
        doors = self.count_building("door")
        walls = self.count_building("wall")
        dug = 0
        for z in range(LEVELS):
            for x in range(MW):
                for y in range(MH):
                    if self.t(z, x, y).kind == "floor":
                        dug += 1
        return beds * 2 + stock * 2 + workshops * 3 + doors + walls // 3 + min(4, dug // 10)

    def add_migrant(self):
        if len(self.alive_dwarves()) >= 11:
            return
        idx = len(self.dwarves)
        d = Dwarf(idx, DWARF_NAMES[idx % len(DWARF_NAMES)] + str(idx // len(DWARF_NAMES) + 1),
                  0, 16, 31, mood=70)
        self.dwarves.append(d)
        self.resources["food"] += 4
        self.say("%s migrates in, carrying optimism and one biscuit." % d.name)

    def spawn_enemy_wave(self, kind, count):
        for _ in range(count):
            side = self.rng.choice(("top", "left", "right"))
            if side == "top":
                x, y = self.rng.randrange(2, MW - 2), 0
            elif side == "left":
                x, y = 0, self.rng.randrange(2, MH - 2)
            else:
                x, y = MW - 1, self.rng.randrange(2, MH - 2)
            if not self.passable(0, x, y):
                self.t(0, x, y).kind = "grass"
            hp = 2 if kind == "scout" else 4
            self.enemies.append(Enemy(self.next_enemy, kind, 0, x, y, hp))
            self.next_enemy += 1

    def alive_dwarves(self):
        return [d for d in self.dwarves if d.hp > 0]

    def update_dwarf(self, d):
        if d.hp <= 0:
            return
        d.hunger = clamp(d.hunger + 0.010, 0, 140)
        d.thirst = clamp(d.thirst + 0.014, 0, 140)
        d.tired = clamp(d.tired + (0.018 if d.task != "rest" else -0.14), 0, 130)
        if d.hunger > 105 or d.thirst > 105 or d.tired > 110:
            d.mood = clamp(d.mood - 0.02, 0, 100)

        enemy = self.adjacent_enemy(d.z, d.x, d.y)
        if enemy:
            self.attack_enemy(d, enemy)
            return

        if d.task == "rest":
            self.update_rest(d)
            return
        if d.task == "fight":
            self.update_fight(d)
            return
        if d.job_id >= 0:
            self.update_job_work(d)
            return

        if d.tired > 86 and self.try_rest(d):
            return
        if self.try_fight(d):
            return
        if self.try_take_job(d):
            return
        self.idle_wander(d)

    def update_rest(self, d):
        if d.path:
            self.follow_path(d)
            return
        if self.t(d.z, d.x, d.y).build == "bed":
            d.tired = max(0, d.tired - 0.55)
            d.mood = min(100, d.mood + 0.05 + self.comfort * 0.003)
            if d.tired < 35:
                d.task = "idle"
        else:
            d.task = "idle"

    def try_rest(self, d):
        beds = self.find_buildings("bed")
        for pos in sorted(beds, key=lambda p: manhattan((d.z, d.x, d.y), p)):
            path = self.find_path((d.z, d.x, d.y), {pos})
            if path is not None:
                d.task = "rest"
                d.path = path
                return True
        return False

    def try_fight(self, d):
        if not self.enemies:
            return False
        options = []
        for e in self.enemies:
            if e.hp <= 0:
                continue
            goals = set(self.adjacent_passable(e.z, e.x, e.y))
            path = self.find_path((d.z, d.x, d.y), goals)
            if path is not None and len(path) <= 16:
                options.append((len(path), e.id, path))
        if not options:
            return False
        _, eid, path = min(options)
        d.task = "fight"
        d.target = eid
        d.path = path
        return True

    def update_fight(self, d):
        enemy = self.enemy_by_id(d.target)
        if not enemy:
            d.task = "idle"
            return
        if abs(enemy.x - d.x) + abs(enemy.y - d.y) + abs(enemy.z - d.z) <= 1:
            self.attack_enemy(d, enemy)
            return
        if d.path:
            self.follow_path(d)
        else:
            d.task = "idle"

    def attack_enemy(self, d, enemy):
        if pyxel.frame_count % 14 != d.id % 14:
            return
        dmg = 1 + (1 if self.resources["tools"] > 0 and self.rng.random() < 0.35 else 0)
        enemy.hp -= dmg
        d.tired = clamp(d.tired + 1.8, 0, 130)
        if enemy.hp <= 0:
            self.say("%s solves a %s problem." % (d.name, enemy.kind))
            self.enemies.remove(enemy)
            d.task = "idle"
            d.target = -1

    def try_take_job(self, d):
        candidates = []
        for job in self.jobs:
            if job.claimed >= 0:
                continue
            goals = self.job_goals(job)
            if not goals:
                continue
            path = self.find_path((d.z, d.x, d.y), set(goals))
            if path is not None:
                priority = {"dig": 0, "chop": 1, "build": 2}.get(job.kind, 5)
                candidates.append((priority, len(path), job.id, path))
        if not candidates:
            return False
        _, _, jid, path = min(candidates)
        job = self.job_by_id(jid)
        if not job:
            return False
        job.claimed = d.id
        d.job_id = job.id
        d.task = job.kind
        d.path = path
        d.work = 0
        return True

    def update_job_work(self, d):
        job = self.job_by_id(d.job_id)
        if not job:
            d.job_id = -1
            d.task = "idle"
            return
        if d.path:
            self.follow_path(d)
            return
        if not self.can_work_job(d, job):
            job.claimed = -1
            d.job_id = -1
            d.task = "idle"
            return
        job.work += 1
        d.tired = clamp(d.tired + 0.035, 0, 130)
        need = 42 if job.kind == "build" else 32 if job.kind == "dig" else 28
        if job.work >= need:
            self.complete_job(d, job)

    def complete_job(self, d, job):
        tile = self.t(job.z, job.x, job.y)
        if job.kind == "dig":
            was = tile.kind
            tile.kind = "floor"
            tile.designated = ""
            gain = 2 if was == "ore" else 1
            self.resources["stone"] = min(self.stock_cap, self.resources["stone"] + gain)
            if was == "ore":
                self.resources["ore"] = min(self.stock_cap, self.resources["ore"] + 1)
                self.threat += 1 + job.z
                self.say("%s finds ore. The deep notices." % d.name)
            else:
                self.say("%s mines stone." % d.name)
        elif job.kind == "chop":
            tile.kind = "grass"
            tile.designated = ""
            self.resources["wood"] = min(self.stock_cap, self.resources["wood"] + 3)
            self.say("%s converts tree into future furniture." % d.name)
        elif job.kind == "build":
            if job.build == "stairs":
                self.place_stairs(job.x, job.y, min(job.z, LEVELS - 2))
            else:
                tile.build = job.build
            self.say("%s builds %s." % (d.name, BUILD_BY_KEY[job.build]["name"]))
        self.jobs.remove(job)
        d.job_id = -1
        d.task = "idle"
        d.work = 0

    def can_work_job(self, d, job):
        if job.kind in ("dig", "chop"):
            return abs(d.x - job.x) + abs(d.y - job.y) == 1 and d.z == job.z
        return (d.z, d.x, d.y) == (job.z, job.x, job.y)

    def job_goals(self, job):
        if job.kind in ("dig", "chop"):
            return self.adjacent_passable(job.z, job.x, job.y)
        if job.kind == "build" and self.passable(job.z, job.x, job.y):
            return [(job.z, job.x, job.y)]
        return []

    def adjacent_passable(self, z, x, y):
        out = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self.passable(z, nx, ny):
                out.append((z, nx, ny))
        return out

    def job_by_id(self, jid):
        for job in self.jobs:
            if job.id == jid:
                return job
        return None

    def enemy_by_id(self, eid):
        for enemy in self.enemies:
            if enemy.id == eid:
                return enemy
        return None

    def find_buildings(self, key):
        out = []
        for z in range(LEVELS):
            for x in range(MW):
                for y in range(MH):
                    if self.t(z, x, y).build == key:
                        out.append((z, x, y))
        return out

    def idle_wander(self, d):
        if pyxel.frame_count % (55 + d.id * 7) != 0:
            return
        opts = []
        for nz, nx, ny in self.neighbors((d.z, d.x, d.y)):
            if self.occupied_by_dwarf(nz, nx, ny):
                continue
            opts.append((nz, nx, ny))
        if opts:
            d.path = [self.rng.choice(opts)]
            d.task = "idle"
            self.follow_path(d)

    def occupied_by_dwarf(self, z, x, y):
        return any(d.hp > 0 and (d.z, d.x, d.y) == (z, x, y) for d in self.dwarves)

    def update_enemy(self, e):
        target = self.nearest_dwarf(e)
        if target and abs(target.x - e.x) + abs(target.y - e.y) + abs(target.z - e.z) <= 1:
            if pyxel.frame_count % 22 == e.id % 22:
                target.hp -= 1
                target.mood -= 7
                self.say("%s is bitten by a %s." % (target.name, e.kind))
            return
        if e.step_cd > 0:
            e.step_cd -= 1
            return
        if not e.path:
            goals = set()
            if target:
                goals.update(self.adjacent_passable(target.z, target.x, target.y))
            goals.update(self.find_buildings("stockpile"))
            e.path = self.find_path((e.z, e.x, e.y), goals, enemy=True) or []
        if e.path:
            nz, nx, ny = e.path.pop(0)
            if self.passable(nz, nx, ny):
                e.z, e.x, e.y = nz, nx, ny
                e.step_cd = 13 if e.kind == "raider" else 16

    def nearest_dwarf(self, e):
        alive = self.alive_dwarves()
        return min(alive, key=lambda d: manhattan((e.z, e.x, e.y), (d.z, d.x, d.y))) if alive else None

    def adjacent_enemy(self, z, x, y):
        for e in self.enemies:
            if e.hp > 0 and abs(e.x - x) + abs(e.y - y) + abs(e.z - z) <= 1:
                return e
        return None

    def check_end(self):
        if not self.alive_dwarves():
            self.game_over = True
            self.end_text = "The hill wins by unanimous silence."
        if self.day >= 14 and not self.game_over:
            self.game_over = True
            self.end_text = "The fort survives long enough to need a tax office."

    # -- pathfinding ----------------------------------------------------
    def neighbors(self, pos):
        z, x, y = pos
        out = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self.passable(z, nx, ny):
                out.append((z, nx, ny))
        if self.t(z, x, y).build == "stairs":
            for nz in (z - 1, z + 1):
                if 0 <= nz < LEVELS and self.passable(nz, x, y) and \
                        self.t(nz, x, y).build == "stairs":
                    out.append((nz, x, y))
        return out

    def find_path(self, start, goals, enemy=False):
        if not goals:
            return None
        if start in goals:
            return []
        q = [start]
        came = {start: None}
        head = 0
        limit = 640 if enemy else 1200
        while head < len(q) and len(came) < limit:
            cur = q[head]
            head += 1
            for nxt in self.neighbors(cur):
                if nxt in came:
                    continue
                came[nxt] = cur
                if nxt in goals:
                    path = [nxt]
                    while came[path[-1]] is not None:
                        path.append(came[path[-1]])
                    path.reverse()
                    return path[1:] if path and path[0] == start else path
                q.append(nxt)
        return None

    def follow_path(self, d):
        if d.step_cd > 0:
            d.step_cd -= 1
            return
        if not d.path:
            return
        nz, nx, ny = d.path.pop(0)
        if self.passable(nz, nx, ny):
            d.z, d.x, d.y = nz, nx, ny
            d.step_cd = 7 if d.mood > 30 else 10

    # -- drawing --------------------------------------------------------
    def draw(self):
        if self.state == "title":
            self.draw_title()
            return
        self.draw_map()
        self.draw_hud()
        if self.mode == "build":
            self.draw_build_menu()
        elif self.mode == "inspect":
            self.draw_inspect()
        elif self.mode == "jobs":
            self.draw_jobs()
        elif self.mode == "help":
            self.draw_help()
        if self.game_over:
            self.draw_end()

    def draw_title(self):
        pyxel.cls(0)
        for y in range(0, H, TILE):
            for x in range(0, W, TILE):
                col = 10 if y < 150 else 2
                pyxel.rect(x, y, TILE, TILE, col)
                if (x * 3 + y * 5) % 37 == 0:
                    pyxel.pset(x + 3, y + 4, 11 if y < 150 else 3)
        pyxel.rect(34, 62, 188, 86, 0)
        pyxel.rectb(34, 62, 188, 86, 8)
        self.big_text("HILL FORT", 57, 76, 2, 7)
        pyxel.text(67, 103, "a tiny fortress roguelite", 6)
        pyxel.text(58, 119, "ENTER starts a new expedition", 5)
        pyxel.text(58, 132, "D dig  B build  Q/E depth", 4)
        pyxel.text(5, 248, "pyxel arcade", 4)

    def big_text(self, text, x, y, scale, col):
        font = {
            "H": ("#..#", "#..#", "####", "#..#", "#..#"),
            "I": ("###", ".#.", ".#.", ".#.", "###"),
            "L": ("#...", "#...", "#...", "#...", "####"),
            "F": ("####", "#...", "###.", "#...", "#..."),
            "O": (".##.", "#..#", "#..#", "#..#", ".##."),
            "R": ("###.", "#..#", "###.", "#.#.", "#..#"),
            "T": ("####", ".##.", ".##.", ".##.", ".##."),
        }
        for ch in text:
            if ch == " ":
                x += 5 * scale
                continue
            glyph = font.get(ch, ("",))
            for gy, row in enumerate(glyph):
                for gx, c in enumerate(row):
                    if c == "#":
                        pyxel.rect(x + gx * scale, y + gy * scale, scale, scale, col)
            x += (len(glyph[0]) + 1) * scale

    def draw_map(self):
        self.cam_y = max(0, min(MH - VIEW_ROWS, self.cam_y))
        pyxel.cls(0)
        for sy in range(VIEW_ROWS):
            y = sy + self.cam_y
            for x in range(MW):
                self.draw_tile(x * TILE, sy * TILE, self.z, x, y)
        for job in self.jobs:
            if job.z == self.z and self.cam_y <= job.y < self.cam_y + VIEW_ROWS:
                px, py = job.x * TILE, (job.y - self.cam_y) * TILE
                pyxel.pset(px + 3, py + 3, 7)
                pyxel.pset(px + 4, py + 4, 7)
        for e in self.enemies:
            if e.z == self.z and self.cam_y <= e.y < self.cam_y + VIEW_ROWS:
                self.draw_enemy(e.x * TILE, (e.y - self.cam_y) * TILE, e.kind)
        for d in self.dwarves:
            if d.hp > 0 and d.z == self.z and self.cam_y <= d.y < self.cam_y + VIEW_ROWS:
                self.draw_dwarf(d.x * TILE, (d.y - self.cam_y) * TILE, d)
        if self.cam_y <= self.cy < self.cam_y + VIEW_ROWS:
            pyxel.rectb(self.cx * TILE, (self.cy - self.cam_y) * TILE, TILE, TILE, 6)
            pyxel.rectb(self.cx * TILE + 1, (self.cy - self.cam_y) * TILE + 1,
                        TILE - 2, TILE - 2, 0 if pyxel.frame_count % 16 < 8 else 7)

    def draw_tile(self, px, py, z, x, y):
        tile = self.t(z, x, y)
        k = tile.kind
        if k == "grass":
            pyxel.rect(px, py, TILE, TILE, 10)
            if (x * 7 + y * 11) % 5 == 0:
                pyxel.pset(px + 2, py + 5, 11)
        elif k == "dirt":
            pyxel.rect(px, py, TILE, TILE, 8)
            pyxel.pset(px + 1, py + 6, 9)
            pyxel.pset(px + 5, py + 3, 9)
        elif k == "hill":
            pyxel.rect(px, py, TILE, TILE, 9)
            pyxel.rect(px, py, TILE, 2, 10)
            pyxel.pset(px + 5, py + 5, 8)
        elif k == "floor":
            col = 8 if z == 0 else 3
            pyxel.rect(px, py, TILE, TILE, col)
            pyxel.pset(px + 1, py + 1, 4 if z else 9)
            pyxel.pset(px + 6, py + 5, 2)
        elif k == "stone":
            pyxel.rect(px, py, TILE, TILE, 1 if z else 2)
            pyxel.rect(px + 1, py + 1, 6, 6, 2)
            if (x + y) % 3 == 0:
                pyxel.pset(px + 5, py + 3, 4)
        elif k == "ore":
            pyxel.rect(px, py, TILE, TILE, 1)
            pyxel.rect(px + 1, py + 1, 6, 6, 2)
            pyxel.pset(px + 2, py + 5, 7)
            pyxel.pset(px + 5, py + 2, 7)
        elif k == "river":
            pyxel.rect(px, py, TILE, TILE, 12)
            pyxel.pset(px + (pyxel.frame_count // 8 + x) % 8, py + 3, 13)
        elif k == "tree":
            pyxel.rect(px, py, TILE, TILE, 10)
            pyxel.rect(px + 3, py + 4, 2, 4, 9)
            pyxel.rect(px + 1, py + 1, 6, 4, 11)
            pyxel.rect(px + 2, py, 4, 2, 10)
        elif k == "rock":
            pyxel.rect(px, py, TILE, TILE, 10)
            pyxel.rect(px + 2, py + 3, 4, 3, 4)
            pyxel.pset(px + 3, py + 2, 5)
        if tile.designated:
            col = 7 if tile.designated == "dig" else 14
            pyxel.line(px + 1, py + 1, px + 6, py + 6, col)
            pyxel.line(px + 6, py + 1, px + 1, py + 6, col)
        if tile.build:
            self.draw_building(px, py, tile.build)

    def draw_building(self, px, py, build):
        if build == "stockpile":
            pyxel.rect(px + 1, py + 4, 6, 3, 8)
            pyxel.rectb(px + 1, py + 4, 6, 3, 9)
            pyxel.pset(px + 3, py + 3, 7)
        elif build == "bed":
            pyxel.rect(px + 1, py + 3, 6, 4, 8)
            pyxel.rect(px + 1, py + 3, 2, 2, 6)
            pyxel.rect(px + 3, py + 3, 4, 3, 5)
        elif build == "door":
            pyxel.rect(px + 2, py + 1, 4, 7, 8)
            pyxel.rectb(px + 2, py + 1, 4, 7, 9)
            pyxel.pset(px + 5, py + 4, 7)
        elif build == "wall":
            pyxel.rect(px, py, TILE, TILE, 4)
            pyxel.rectb(px, py, TILE, TILE, 5)
            pyxel.line(px, py + 4, px + 7, py + 4, 3)
        elif build == "carpenter":
            pyxel.rect(px + 1, py + 5, 6, 2, 8)
            pyxel.line(px + 2, py + 4, px + 6, py + 2, 6)
            pyxel.pset(px + 5, py + 3, 5)
        elif build == "mason":
            pyxel.rect(px + 1, py + 5, 6, 2, 4)
            pyxel.rect(px + 2, py + 2, 4, 3, 5)
            pyxel.pset(px + 6, py + 2, 7)
        elif build == "stairs":
            pyxel.rect(px + 1, py + 1, 6, 6, 3)
            for i in range(3):
                pyxel.line(px + 2, py + 2 + i * 2, px + 6, py + 2 + i * 2, 5)

    def draw_dwarf(self, px, py, d):
        pyxel.rect(px + 2, py + 1, 4, 2, 6)
        pyxel.rect(px + 2, py + 3, 4, 3, 8)
        pyxel.rect(px + 1, py + 5, 6, 2, 9)
        pyxel.pset(px + 3, py + 2, 0)
        pyxel.pset(px + 5, py + 2, 0)
        if d.mood < 35:
            pyxel.pset(px + 4, py, 14)

    def draw_enemy(self, px, py, kind):
        col = 14 if kind == "raider" else 15
        pyxel.rect(px + 2, py + 2, 4, 5, col)
        pyxel.rect(px + 1, py + 1, 6, 2, 2)
        pyxel.pset(px + 3, py + 3, 0)
        pyxel.pset(px + 5, py + 3, 0)

    def draw_hud(self):
        pyxel.rect(0, HUD_Y, W, H - HUD_Y, 0)
        pyxel.rectb(0, HUD_Y, W, H - HUD_Y, 3)
        alive = len(self.alive_dwarves())
        res = self.resources
        pyxel.text(4, HUD_Y + 4, "HILL FORT  z%d %s  day %d" %
                   (self.z, LEVEL_NAMES[self.z], self.day), 7)
        pyxel.text(4, HUD_Y + 13, "D%d/%d W%d S%d F%d A%d O%d T%d" %
                   (alive, len(self.dwarves), res["wood"], res["stone"],
                    res["food"], res["drink"], res["ore"], res["tools"]), 6)
        pyxel.text(4, HUD_Y + 22, "mode %-7s  jobs %d  threat %d" %
                   (self.mode, len(self.jobs), self.threat), 5)
        pyxel.text(4, HUD_Y + 31, self.tile_info(), 13)
        if self.messages:
            pyxel.text(4, HUD_Y + 42, trim(self.messages[-1], 61), 6)
        pyxel.text(4, HUD_Y + 52, "D dig/chop  B build  Esc back  Q/E z  S save", 4)

    def tile_info(self):
        tile = self.t(self.z, self.cx, self.cy)
        here = [d for d in self.dwarves if d.hp > 0 and (d.z, d.x, d.y) == (self.z, self.cx, self.cy)]
        if here:
            d = here[0]
            return "%s hp%d mood%d task %s" % (d.name, d.hp, int(d.mood), d.task)
        text = "%02d,%02d %s" % (self.cx, self.cy, tile.kind)
        if tile.build:
            text += " " + BUILD_BY_KEY[tile.build]["name"]
        if tile.designated:
            text += " [%s]" % tile.designated
        return trim(text, 58)

    def draw_build_menu(self):
        x, y, w, h = 132, 8, 120, 176
        self.panel(x, y, w, h, "BUILD")
        for i, b in enumerate(BUILDINGS):
            yy = y + 16 + i * 14
            if i == self.build_i:
                pyxel.rect(x + 4, yy - 2, w - 8, 11, 7)
            col = 0 if i == self.build_i else 6
            pyxel.text(x + 8, yy, "%d %s" % (i + 1, b["name"]), col)
            pyxel.text(x + 78, yy, self.cost_text(b["key"]), 0 if i == self.build_i else 4)
        b = BUILDINGS[self.build_i]
        note_y = y + 119
        for j, line in enumerate(self.wrap_note(b["note"], 25, 3)):
            pyxel.text(x + 8, note_y + j * 8, line, 5)
        pyxel.text(x + 8, y + h - 13, "ENTER place", 7 if self.can_pay(b["key"]) else 14)

    def wrap_note(self, text, chars, max_lines):
        words = text.split()
        lines = []
        line = ""
        for word in words:
            if len(line) + len(word) + (1 if line else 0) > chars:
                if line:
                    lines.append(line)
                line = word
                if len(lines) >= max_lines:
                    break
            else:
                line = (line + " " + word).strip()
        if line and len(lines) < max_lines:
            lines.append(line)
        return lines

    def draw_inspect(self):
        x, y, w, h = 8, 14, 120, 118
        self.panel(x, y, w, h, "INSPECT")
        tile = self.t(self.z, self.cx, self.cy)
        lines = [
            "pos %d,%d z%d" % (self.cx, self.cy, self.z),
            "tile " + tile.kind,
            "build " + (tile.build or "-"),
            "mark " + (tile.designated or "-"),
        ]
        here_d = [d for d in self.dwarves if d.hp > 0 and (d.z, d.x, d.y) == (self.z, self.cx, self.cy)]
        if here_d:
            d = here_d[0]
            lines += [
                "%s hp %d" % (d.name, d.hp),
                "hunger %d thirst %d" % (d.hunger, d.thirst),
                "tired %d mood %d" % (d.tired, d.mood),
                "task " + d.task,
            ]
        else:
            lines += ["no dwarf here"]
        for i, line in enumerate(lines[:11]):
            pyxel.text(x + 7, y + 16 + i * 9, trim(str(line), 26), 6)

    def draw_jobs(self):
        x, y, w, h = 8, 14, 134, 140
        self.panel(x, y, w, h, "JOBS")
        for i, job in enumerate(self.jobs[:12]):
            name = job.kind if job.kind != "build" else BUILD_BY_KEY[job.build]["name"]
            who = "-" if job.claimed < 0 else self.dwarves[job.claimed].name[:5]
            pyxel.text(x + 7, y + 16 + i * 9,
                       "%02d %-9s z%d %02d,%02d %s" %
                       (job.id, name[:9], job.z, job.x, job.y, who), 6)
        if not self.jobs:
            pyxel.text(x + 7, y + 24, "No jobs. This worries them.", 5)

    def draw_help(self):
        x, y, w, h = 18, 24, 220, 138
        self.panel(x, y, w, h, "FIELD MANUAL")
        rows = (
            "D marks stone/hill to mine or trees to chop.",
            "B opens build mode. 1-7 choose objects.",
            "Dwarves pick jobs from the shared queue.",
            "Beds reduce tiredness. Workshops add comfort/tools.",
            "Q/E changes z-level; stairs connect levels.",
            "Ore and deep digging raise threat.",
            "Raiders path toward food and nearby dwarves.",
            "R restarts. S/L writes/reads hill_fort_save.json.",
            "Esc closes menus. H also closes this manual.",
        )
        for i, row in enumerate(rows):
            pyxel.text(x + 8, y + 18 + i * 11, row, 6)

    def draw_end(self):
        x, y, w, h = 24, 72, 208, 74
        pyxel.rect(x, y, w, h, 0)
        pyxel.rectb(x, y, w, h, 14 if not self.alive_dwarves() else 7)
        pyxel.text(x + 10, y + 10, "FORT REPORT", 7)
        pyxel.text(x + 10, y + 25, trim(self.end_text, 44), 6)
        pyxel.text(x + 10, y + 39, "days %d  dwarves %d  threat %d" %
                   (self.day, len(self.alive_dwarves()), self.threat), 5)
        pyxel.text(x + 10, y + 56, "R starts another questionable hill", 7)

    def panel(self, x, y, w, h, title):
        pyxel.rect(x, y, w, h, 0)
        pyxel.rectb(x, y, w, h, 4)
        pyxel.rectb(x + 1, y + 1, w - 2, h - 2, 2)
        pyxel.text(x + 6, y + 5, title, 7)
        pyxel.line(x + 5, y + 13, x + w - 6, y + 13, 3)


if __name__ == "__main__":
    App().run()
