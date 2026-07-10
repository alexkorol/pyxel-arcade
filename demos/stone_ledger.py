"""Stone Ledger -- a pocket world forge and legends viewer.

Generate an island world, watch civilizations claim it, then browse the
resulting people, sites, artifacts, regions, and event history through a
tiny retro UI.

Controls:  forge: up/down selects a parameter, left/right edits it
           Enter = build/view world      R = reroll seed
           viewer: Tab changes view      arrows navigate
           Q/E cycle regions on the map  Enter follows selected records
           1/2/3 = map/legends/history   M returns to the map

Study: value-noise terrain, downhill river tracing, biome and polity
overlays, site/road placement, deterministic name generation, and a
compressed legends browser for a generated history graph.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random

import pyxel


W, H = 240, 180
MW, MH = 58, 46
SEA = 0.42
MAP_X, MAP_Y, MAP_SCALE = 9, 38, 2
MAP_W, MAP_H = MW * MAP_SCALE, MH * MAP_SCALE

STAGES = ("height", "rivers", "biomes", "regions", "sites", "history")
AGE_VALUES = (250, 550, 900, 1500, 2500)

PALETTE = [
    0x05060A, 0x12131B, 0x271628, 0x4A223F,
    0xB32E65, 0xE05284, 0x2A2F4F, 0x7A7F94,
    0x6AB04A, 0xB7D66B, 0x2F77C7, 0x55B6E8,
    0xF7C74A, 0xF06B31, 0x8D765D, 0xF0E6C8,
]

BIOME_COL = {
    "ocean": 10,
    "coast": 11,
    "river": 11,
    "desert": 12,
    "plains": 8,
    "forest": 8,
    "jungle": 9,
    "swamp": 6,
    "tundra": 7,
    "mountain": 14,
    "snowpeak": 15,
    "volcano": 13,
    "ash": 4,
    "waste": 3,
}

BIOME_DESC = {
    "ocean": "open salt water",
    "coast": "shoals and pale sand",
    "desert": "dry dunes and scrub",
    "plains": "grassland and farms",
    "forest": "deep green woods",
    "jungle": "hot rain forest",
    "swamp": "wet fen and reeds",
    "tundra": "cold moss and stone",
    "mountain": "bare high stone",
    "snowpeak": "ice above the clouds",
    "volcano": "new basalt and fire",
    "ash": "cursed ashfall",
    "waste": "blighted badland",
}

KINDS = {
    "hold": ("HOLD", 12),
    "city": ("CITY", 15),
    "fort": ("FORT", 12),
    "town": ("TOWN", 15),
    "grove": ("GROVE", 9),
    "camp": ("CAMP", 13),
    "tower": ("TOWER", 5),
    "port": ("PORT", 11),
    "ruin": ("RUIN", 7),
    "mine": ("MINE", 14),
}

PEOPLE = (
    ("Dwarven", "dwarf", 12, ("mountain", "snowpeak", "volcano")),
    ("Lowland", "human", 15, ("plains", "coast", "forest")),
    ("Verdant", "elf", 9, ("forest", "jungle", "swamp")),
    ("Ashen", "orc", 13, ("ash", "waste", "desert", "volcano")),
    ("Veiled", "mystic", 5, ("tundra", "mountain", "waste")),
    ("Salt", "mariner", 11, ("coast", "plains", "desert")),
)

PREFIX = (
    "Ash", "Bar", "Bel", "Bron", "Cind", "Dun", "Eld", "Frost",
    "Glim", "Har", "Iron", "Kel", "Low", "Mor", "Nim", "Oak",
    "Red", "Salt", "Silver", "Stone", "Sun", "Thorn", "Umber",
    "Ver", "Wolf", "Zug",
)
SUFFIX = (
    "bar", "deep", "dell", "fall", "ford", "gate", "glen", "hall",
    "hame", "mere", "moor", "peak", "ridge", "run", "spire", "vale",
    "wash", "watch", "wick", "wood",
)
GIVEN = (
    "Adil", "Asmel", "Bera", "Cattan", "Domas", "Dumat", "Eral",
    "Fath", "Goden", "Iden", "Kadol", "Kol", "Lolor", "Mafol",
    "Mistem", "Nomal", "Olin", "Rigoth", "Sodel", "Thikut", "Udib",
    "Vucar", "Zasit", "Zon",
)
EPITHETS = (
    "Stonefist", "Cinderhand", "Deepbrow", "Frostmantle", "Goldvein",
    "Ashspeaker", "Riverward", "Nightfound", "Tinmask", "Oathcarver",
    "Mossblade", "Saltmantle",
)
ARTIFACT_NOUNS = (
    "Axe", "Crown", "Lantern", "Cup", "Mace", "Gate-Key", "Mask",
    "Horn", "Book", "Ring", "Hammer", "Bell",
)
ARTIFACT_OF = (
    "Falls", "The First Fire", "Drowned Roads", "Stone Sleep",
    "The Seventh Accord", "Moss and Iron", "Ashen Dawn", "Lost Salt",
    "The Deep Door", "Blue Winter",
)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    return t * t * (3 - 2 * t)


def hash_unit(seed, x, y, layer):
    n = (seed * 1103515245 + x * 374761393 + y * 668265263 +
         layer * 2147483647) & 0xFFFFFFFF
    n ^= n >> 13
    n = (n * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFF) / 65535.0


def value_noise(seed, x, y, scale, layer):
    fx = x / scale
    fy = y / scale
    x0 = math.floor(fx)
    y0 = math.floor(fy)
    tx = smooth(fx - x0)
    ty = smooth(fy - y0)
    a = hash_unit(seed, x0, y0, layer)
    b = hash_unit(seed, x0 + 1, y0, layer)
    c = hash_unit(seed, x0, y0 + 1, layer)
    d = hash_unit(seed, x0 + 1, y0 + 1, layer)
    return lerp(lerp(a, b, tx), lerp(c, d, tx), ty)


def fbm(seed, x, y, layer, scale=24.0, octaves=4):
    amp = 1.0
    total = 0.0
    norm = 0.0
    for i in range(octaves):
        total += value_noise(seed, x, y, max(2.0, scale), layer + i * 19) * amp
        norm += amp
        amp *= 0.55
        scale *= 0.52
    return total / norm


def dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def trim(text, chars):
    return text if len(text) <= chars else text[:max(0, chars - 1)] + "."


def wrap(text, chars, max_lines=5):
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


@dataclass
class Tile:
    h: float = 0.0
    rain: float = 0.0
    temp: float = 0.0
    volc: float = 0.0
    evil: float = 0.0
    biome: str = "ocean"
    river: bool = False
    road: bool = False
    region: int = -1
    civ: int = -1
    site: int = -1


@dataclass
class Region:
    id: int
    name: str
    biome: str
    tiles: list
    center: tuple
    pop: int = 0
    danger: int = 0


@dataclass
class Civ:
    id: int
    name: str
    people: str
    color: int
    capital: int = -1
    sites: list = None
    pop: int = 0
    military: str = "weak"
    motto: str = ""


@dataclass
class Site:
    id: int
    name: str
    kind: str
    civ: int
    x: int
    y: int
    founded: int
    pop: int
    status: str = "living"


@dataclass
class Figure:
    id: int
    name: str
    race: str
    role: str
    civ: int
    site: int
    born: int
    died: int
    kills: int = 0
    deeds: int = 0
    quote: str = ""


@dataclass
class Artifact:
    id: int
    name: str
    kind: str
    maker: int
    site: int
    year: int
    bearer: int
    fame: int


@dataclass
class Event:
    year: int
    icon: str
    text: str
    color: int
    loc: tuple | None = None
    kind: str = "event"
    refs: tuple = ()


class World:
    def __init__(self, seed, age, rain_bias, temp_bias, civ_count, evil_on):
        self.seed = seed
        self.age = age
        self.rain_bias = rain_bias
        self.temp_bias = temp_bias
        self.civ_count = civ_count
        self.evil_on = evil_on
        self.rng = random.Random(seed)
        self.tiles = [[Tile() for _ in range(MH)] for _ in range(MW)]
        self.regions = []
        self.civs = []
        self.sites = []
        self.figures = []
        self.artifacts = []
        self.events = []
        self.roads = []

    def generate(self):
        self.make_height()
        self.carve_rivers()
        self.assign_regions()
        self.place_civs()
        self.write_history()
        self.update_region_stats()

    def tile(self, x, y):
        return self.tiles[x][y]

    def in_bounds(self, x, y):
        return 0 <= x < MW and 0 <= y < MH

    def land(self, x, y):
        return self.tile(x, y).biome not in ("ocean",)

    def make_height(self):
        cx, cy = (MW - 1) * 0.5, (MH - 1) * 0.5
        for y in range(MH):
            latitude = abs(y / (MH - 1) * 2 - 1)
            for x in range(MW):
                nx = (x - cx) / cx
                ny = (y - cy) / cy
                edge = math.sqrt(nx * nx + ny * ny)
                island = clamp(1.12 - edge * 0.92)
                base = fbm(self.seed, x, y, 3, 25)
                ridges = abs(fbm(self.seed, x, y, 41, 13) - 0.5) * 2
                h = 0.18 + island * 0.62 + (base - 0.5) * 0.34 + ridges * 0.17
                h -= max(0.0, edge - 0.82) * 1.1
                h = clamp(h)
                temp = clamp(1.0 - latitude * 1.05 +
                             (fbm(self.seed, x, y, 70, 22) - 0.5) * 0.24 +
                             (self.temp_bias - 3) * 0.105 - h * 0.12)
                rain = clamp(fbm(self.seed, x, y, 95, 18) +
                             (self.rain_bias - 3) * 0.10 -
                             max(0.0, temp - 0.65) * 0.07)
                volc = fbm(self.seed, x, y, 130, 10)
                evil = fbm(self.seed, x, y, 180, 16)
                if not self.evil_on:
                    evil *= 0.35
                t = self.tile(x, y)
                t.h, t.temp, t.rain, t.volc, t.evil = h, temp, rain, volc, evil
                t.biome = self.classify(t)

    def classify(self, t):
        if t.h < SEA:
            return "ocean"
        if t.h < SEA + 0.035:
            return "coast"
        if t.volc > 0.82 and t.h > 0.56:
            return "volcano"
        if t.evil > 0.79 and t.h > SEA + 0.04:
            return "ash" if t.rain < 0.52 else "waste"
        if t.h > 0.82:
            return "snowpeak" if t.temp < 0.55 else "mountain"
        if t.h > 0.69:
            return "mountain"
        if t.temp < 0.25:
            return "tundra"
        if t.rain < 0.26 and t.temp > 0.40:
            return "desert"
        if t.rain > 0.76 and t.h < 0.58:
            return "swamp"
        if t.rain > 0.65 and t.temp > 0.62:
            return "jungle"
        if t.rain > 0.50:
            return "forest"
        return "plains"

    def carve_rivers(self):
        candidates = []
        for y in range(2, MH - 2):
            for x in range(2, MW - 2):
                t = self.tile(x, y)
                if t.h > 0.66 and t.biome not in ("ocean", "coast"):
                    candidates.append((t.h + t.rain * 0.35, x, y))
        candidates.sort(reverse=True)
        self.rng.shuffle(candidates[:20])
        river_count = 5 + self.rain_bias + (1 if self.age > 1000 else 0)
        used = set()
        for _, sx, sy in candidates[:river_count * 3]:
            if len(used) >= river_count:
                break
            if any(abs(sx - x) + abs(sy - y) < 7 for x, y in used):
                continue
            path = self.trace_river(sx, sy)
            if len(path) > 9:
                used.add((sx, sy))
                for x, y in path:
                    self.tile(x, y).river = True

    def trace_river(self, sx, sy):
        x, y = sx, sy
        path = []
        seen = set()
        for _ in range(110):
            if (x, y) in seen:
                break
            seen.add((x, y))
            path.append((x, y))
            if self.tile(x, y).h < SEA + 0.02 or self.tile(x, y).biome == "ocean":
                break
            opts = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not self.in_bounds(nx, ny):
                        continue
                    n = self.tile(nx, ny)
                    edge_pull = min(nx, MW - 1 - nx, ny, MH - 1 - ny) * 0.002
                    opts.append((n.h + edge_pull + self.rng.random() * 0.012,
                                 nx, ny))
            opts.sort()
            _, x, y = opts[0]
        return path

    def family(self, biome):
        if biome in ("ocean", "coast"):
            return "sea"
        if biome in ("mountain", "snowpeak", "volcano"):
            return "mountain"
        if biome in ("ash", "waste"):
            return "badland"
        return biome

    def region_name(self, biome):
        pre = self.rng.choice(PREFIX)
        if biome in ("ocean", "coast"):
            tail = self.rng.choice(("Sea", "Deep", "Bight", "Reach"))
        elif biome in ("mountain", "snowpeak", "volcano"):
            tail = self.rng.choice(("Peaks", "Spire", "Crags", "Crown"))
        elif biome in ("forest", "jungle"):
            tail = self.rng.choice(("Wood", "Canopy", "Thicket", "Grove"))
        elif biome in ("ash", "waste"):
            tail = self.rng.choice(("Wastes", "Ashlands", "Scar", "Cinders"))
        elif biome == "swamp":
            tail = self.rng.choice(("Mire", "Fen", "Wash", "Bog"))
        elif biome == "desert":
            tail = self.rng.choice(("Sands", "Dunes", "Drylands", "Waste"))
        elif biome == "tundra":
            tail = self.rng.choice(("Frost", "Tundra", "Whitefield", "Moor"))
        else:
            tail = self.rng.choice(("Vale", "Fields", "Downs", "March"))
        return pre + tail

    def assign_regions(self):
        seen = set()
        groups = []
        for y in range(MH):
            for x in range(MW):
                if (x, y) in seen:
                    continue
                fam = self.family(self.tile(x, y).biome)
                stack = [(x, y)]
                seen.add((x, y))
                pts = []
                biome_votes = {}
                while stack:
                    px, py = stack.pop()
                    pts.append((px, py))
                    b = self.tile(px, py).biome
                    biome_votes[b] = biome_votes.get(b, 0) + 1
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = px + dx, py + dy
                        if not self.in_bounds(nx, ny) or (nx, ny) in seen:
                            continue
                        if self.family(self.tile(nx, ny).biome) == fam:
                            seen.add((nx, ny))
                            stack.append((nx, ny))
                biome = max(biome_votes, key=biome_votes.get)
                groups.append((len(pts), biome, pts))
        groups.sort(reverse=True, key=lambda g: g[0])
        for size, biome, pts in groups:
            if size < 8:
                continue
            rid = len(self.regions)
            cx = int(sum(p[0] for p in pts) / size)
            cy = int(sum(p[1] for p in pts) / size)
            region = Region(rid, self.region_name(biome), biome, pts, (cx, cy))
            self.regions.append(region)
            for x, y in pts:
                self.tile(x, y).region = rid

    def site_name(self):
        return self.rng.choice(PREFIX) + self.rng.choice(SUFFIX)

    def civ_name(self, people):
        noun = self.rng.choice(("Oath", "League", "Clans", "Holdfast",
                                "Accord", "Crown", "Compact", "Banner"))
        return "%s %s" % (self.rng.choice(PREFIX), noun)

    def open_site_tiles(self, pref, near=None, radius=999):
        out = []
        for y in range(1, MH - 1):
            for x in range(1, MW - 1):
                t = self.tile(x, y)
                if t.site >= 0 or t.biome == "ocean":
                    continue
                if near and dist2((x, y), near) > radius * radius:
                    continue
                if any(dist2((x, y), (s.x, s.y)) < 16 for s in self.sites):
                    continue
                score = 0.0
                if t.biome in pref:
                    score += 5.0
                if t.river:
                    score += 1.7
                if t.biome == "coast":
                    score += 1.0
                score += t.h * 0.8 + t.rain * 0.5
                score += self.rng.random()
                if score > 1.0:
                    out.append((score, x, y))
        out.sort(reverse=True)
        return out

    def make_site(self, civ_id, x, y, kind, founded, pop):
        sid = len(self.sites)
        name = self.site_name()
        site = Site(sid, name, kind, civ_id, x, y, founded, pop)
        self.sites.append(site)
        t = self.tile(x, y)
        t.site = sid
        t.civ = civ_id
        civ = self.civs[civ_id]
        civ.sites.append(sid)
        civ.pop += pop
        if civ.capital < 0:
            civ.capital = sid
        return site

    def place_civs(self):
        count = min(self.civ_count, 10)
        for i in range(count):
            label, race, col, pref = PEOPLE[i % len(PEOPLE)]
            civ = Civ(i, self.civ_name(label), race, col, sites=[], motto="")
            civ.motto = '"%s."' % self.rng.choice((
                "We remember the first stone",
                "No road is lost while names remain",
                "The river keeps every oath",
                "Iron bends but the lineage does not",
                "Under ash, roots still drink",
            ))
            self.civs.append(civ)
            opts = self.open_site_tiles(pref)
            if not opts:
                continue
            _, x, y = opts[min(len(opts) - 1, self.rng.randrange(min(9, len(opts)))) ]
            kind = {
                "dwarf": "hold",
                "human": "city",
                "elf": "grove",
                "orc": "camp",
                "mystic": "tower",
                "mariner": "port",
            }.get(race, "town")
            founded = self.rng.randint(5, min(120, max(20, self.age // 3)))
            base_pop = self.rng.randint(7000, 28000)
            self.make_site(i, x, y, kind, founded, base_pop)
            extras = self.rng.randint(1, 3 if self.age < 1000 else 4)
            for _ in range(extras):
                opts = self.open_site_tiles(pref, near=(x, y), radius=15)
                if not opts:
                    opts = self.open_site_tiles(pref)
                if not opts:
                    break
                _, sx, sy = opts[min(len(opts) - 1, self.rng.randrange(min(7, len(opts)))) ]
                kind = self.rng.choice(("town", "fort", "mine") if race == "dwarf"
                                       else ("town", "fort", "port") if race in ("human", "mariner")
                                       else ("grove", "town") if race == "elf"
                                       else ("camp", "fort", "tower"))
                pop = self.rng.randint(1200, 11000)
                founded = self.rng.randint(40, max(41, min(self.age - 10, self.age // 2)))
                self.make_site(i, sx, sy, kind, founded, pop)

        for civ in self.civs:
            if len(civ.sites) > 1:
                cap = self.sites[civ.capital]
                for sid in civ.sites:
                    if sid != civ.capital:
                        self.make_road((cap.x, cap.y), (self.sites[sid].x, self.sites[sid].y))
            civ.military = ("weak", "steady", "strong", "legendary")[
                min(3, max(0, len(civ.sites) // 2 + civ.pop // 45000))]
        self.claim_tiles()

    def make_road(self, a, b):
        x, y = a
        tx, ty = b
        path = []
        guard = 0
        while (x, y) != (tx, ty) and guard < 180:
            guard += 1
            path.append((x, y))
            if self.rng.random() < 0.55:
                if x < tx:
                    x += 1
                elif x > tx:
                    x -= 1
                elif y < ty:
                    y += 1
                elif y > ty:
                    y -= 1
            else:
                if y < ty:
                    y += 1
                elif y > ty:
                    y -= 1
                elif x < tx:
                    x += 1
                elif x > tx:
                    x -= 1
            if self.in_bounds(x, y) and self.tile(x, y).biome != "ocean":
                self.tile(x, y).road = True
        self.roads.append(path)

    def claim_tiles(self):
        for y in range(MH):
            for x in range(MW):
                t = self.tile(x, y)
                if t.biome == "ocean":
                    continue
                best = None
                for s in self.sites:
                    d = dist2((x, y), (s.x, s.y))
                    if d < 190 and (best is None or d < best[0]):
                        best = (d, s.civ)
                if best:
                    t.civ = best[1]

    def figure_name(self):
        return "%s %s" % (self.rng.choice(GIVEN), self.rng.choice(EPITHETS))

    def add_event(self, year, icon, text, color, loc=None, kind="event", refs=()):
        self.events.append(Event(max(-1250, min(self.age, year)), icon, text,
                                 color, loc, kind, refs))

    def write_history(self):
        self.add_event(-1250, "*", "The world is born from sea, stone, and hidden fire.", 12)
        for civ in self.civs:
            if civ.capital < 0:
                continue
            cap = self.sites[civ.capital]
            founder = self.add_figure(civ.id, cap.id, "founder",
                                      max(0, cap.founded - self.rng.randint(18, 44)))
            self.add_event(cap.founded, "@",
                           "%s founds %s at %s." %
                           (founder.name, civ.name, cap.name),
                           civ.color, (cap.x, cap.y), "founding",
                           ("figure:%d" % founder.id, "site:%d" % cap.id,
                            "civ:%d" % civ.id))
            for sid in civ.sites:
                if sid == cap.id:
                    continue
                site = self.sites[sid]
                self.add_event(site.founded, "+",
                               "%s raises %s, a %s of %s." %
                               (civ.name, site.name, KINDS[site.kind][0].lower(),
                                PEOPLE[civ.id % len(PEOPLE)][0].lower()),
                               civ.color, (site.x, site.y), "site",
                               ("site:%d" % sid, "civ:%d" % civ.id))
            for _ in range(1 + self.age // 900):
                self.add_figure(civ.id, cap.id,
                                self.rng.choice(("ruler", "general", "scholar",
                                                 "prophet", "captain")),
                                self.rng.randint(0, max(1, self.age - 60)))

        art_count = min(14, 4 + self.age // 230 + len(self.civs) // 2)
        for _ in range(art_count):
            if not self.figures or not self.sites:
                break
            maker = self.rng.choice(self.figures)
            site = self.sites[maker.site]
            noun = self.rng.choice(ARTIFACT_NOUNS)
            art = Artifact(len(self.artifacts),
                           "%s of %s" % (noun, self.rng.choice(ARTIFACT_OF)),
                           noun.lower(), maker.id, site.id,
                           self.rng.randint(max(1, maker.born + 18), self.age),
                           maker.id, self.rng.randint(2, 20))
            self.artifacts.append(art)
            maker.deeds += 2
            self.add_event(art.year, "*",
                           "%s creates the %s in %s." %
                           (maker.name, art.name, site.name),
                           12, (site.x, site.y), "artifact",
                           ("figure:%d" % maker.id, "artifact:%d" % art.id,
                            "site:%d" % site.id))

        self.write_conflicts()
        self.write_disasters()
        self.write_late_ages()
        self.events.sort(key=lambda e: (e.year, e.text))
        del self.events[84:]

    def add_figure(self, civ_id, site_id, role, born):
        fid = len(self.figures)
        race = self.civs[civ_id].people if civ_id < len(self.civs) else "wanderer"
        died = -1
        if born + self.rng.randint(58, 96) < self.age and self.rng.random() < 0.72:
            died = born + self.rng.randint(39, 92)
        fig = Figure(fid, self.figure_name(), race, role, civ_id, site_id,
                     born, died, quote=self.rng.choice((
                         "We carve our home from stone and time",
                         "Every ruin is a door with its name worn off",
                         "A map without scars cannot be trusted",
                         "The dead keep count, so we must count better",
                     )))
        self.figures.append(fig)
        return fig

    def write_conflicts(self):
        if len(self.civs) < 2:
            return
        rounds = 6 + self.age // 140
        for _ in range(rounds):
            a, b = self.rng.sample(self.civs, 2)
            if a.capital < 0 or b.capital < 0:
                continue
            year = self.rng.randint(80, self.age)
            target = self.sites[self.rng.choice(b.sites)]
            attacker = self.rng.choice([f for f in self.figures if f.civ == a.id] or self.figures)
            losses = self.rng.randint(80, 8000)
            verb = self.rng.choice(("raids", "besieges", "burns the farms of",
                                    "breaks the outer gate of", "ambushes"))
            attacker.kills += losses // self.rng.randint(180, 800)
            attacker.deeds += 1
            target.pop = max(80, target.pop - losses // 4)
            self.add_event(year, "x",
                           "%s %s %s during the %s War." %
                           (a.name, verb, target.name, self.rng.choice(PREFIX)),
                           13, (target.x, target.y), "war",
                           ("figure:%d" % attacker.id, "site:%d" % target.id,
                            "civ:%d" % a.id, "civ:%d" % b.id))
            if losses > 5200 and target.status == "living" and self.rng.random() < 0.35:
                target.status = "ruin"
                target.kind = "ruin"
                self.add_event(year + self.rng.randint(1, 9), "!",
                               "%s is abandoned and enters the legends as a ruin." %
                               target.name, 7, (target.x, target.y), "ruin",
                               ("site:%d" % target.id,))

    def write_disasters(self):
        volcanoes = [(x, y) for y in range(MH) for x in range(MW)
                     if self.tile(x, y).biome == "volcano"]
        if volcanoes and self.sites:
            vx, vy = self.rng.choice(volcanoes)
            site = min(self.sites, key=lambda s: dist2((vx, vy), (s.x, s.y)))
            year = self.rng.randint(100, self.age)
            loss = self.rng.randint(2000, 120000)
            site.pop = max(40, site.pop - loss // 20)
            self.add_event(year, "^",
                           "The Ashen Eruption darkens %s and scatters its farms." %
                           self.region_at(vx, vy).name,
                           13, (vx, vy), "disaster", ("site:%d" % site.id,))
            if self.rng.random() < 0.45:
                self.add_event(year + 1, "!",
                               "%s records %d dead after the ashfall." %
                               (site.name, loss),
                               4, (site.x, site.y), "disaster", ("site:%d" % site.id,))
        for _ in range(max(2, self.age // 600)):
            if not self.sites:
                break
            site = self.rng.choice(self.sites)
            year = self.rng.randint(80, self.age)
            kind = self.rng.choice(("famine", "great migration", "silver fever",
                                    "winter of blue suns"))
            delta = self.rng.randint(400, 8000)
            if kind == "great migration":
                site.pop += delta
                col = 9
                text = "The Great Migration reaches %s; its streets overflow." % site.name
            else:
                site.pop = max(70, site.pop - delta)
                col = 5
                text = "%s suffers the %s." % (site.name, kind)
            self.add_event(year, "~", text, col, (site.x, site.y), "change",
                           ("site:%d" % site.id,))

    def write_late_ages(self):
        if self.age > 400:
            self.add_event(self.age // 3, "=", "The First Accord fixes the river borders.", 9)
        if self.age > 800:
            self.add_event(self.age // 2, "$", "Merchant roads bind the old capitals together.", 12)
        if self.age > 1200:
            self.add_event(self.age - 90, "@", "The Age of Ledgers begins; scribes count the dead.", 15)

    def region_at(self, x, y):
        rid = self.tile(x, y).region
        if 0 <= rid < len(self.regions):
            return self.regions[rid]
        return Region(-1, "Uncharted", "waste", [], (x, y))

    def update_region_stats(self):
        for region in self.regions:
            pop = 0
            danger = 0.0
            for x, y in region.tiles:
                t = self.tile(x, y)
                danger += t.evil + max(0, t.volc - 0.65)
                if t.site >= 0:
                    pop += self.sites[t.site].pop
            region.pop = pop
            region.danger = int(danger / max(1, len(region.tiles)) * 100)


def _url_seed():
    """Daily-challenge hook: the arcade appends &seed=<n> to the launcher
    URL so everyone forges the same world. `js` only exists in Pyodide;
    on desktop this quietly returns None."""
    try:
        from js import window
        import re
        m = re.search(r"[?&]seed=(\d+)", str(window.location.search))
        return int(m.group(1)) % 0x10000000 if m else None
    except Exception:
        return None


class App:
    def __init__(self):
        pyxel.init(W, H, title="stone ledger", fps=30, quit_key=pyxel.KEY_NONE)
        pyxel.mouse(True)
        pyxel.colors[:] = PALETTE
        seed = _url_seed()
        self.seed = seed if seed is not None else random.randrange(0x10000000)
        self.age_i = 2
        self.rain = 3
        self.temp = 3
        self.civs = 7
        self.evil = True
        self.param = 0
        self.mode = "forge"
        self.view = 0
        self.world = None
        self.gen_stage = 0
        self.gen_t = 0
        self.cx, self.cy = MW // 2, MH // 2
        self.region_i = 0
        self.leg_tab = 0
        self.leg_i = 0
        self.hist_i = 0
        self.notice = ""
        self.notice_t = 0
        self.rebuild_world()

    def run(self):
        pyxel.run(self.update, self.draw)

    def rebuild_world(self):
        self.world = World(self.seed, AGE_VALUES[self.age_i], self.rain,
                           self.temp, self.civs, self.evil)
        self.world.generate()
        self.center_on_first_capital()
        self.region_i = min(self.region_i, max(0, len(self.world.regions) - 1))
        self.hist_i = min(self.hist_i, max(0, len(self.world.events) - 1))

    def center_on_first_capital(self):
        for civ in self.world.civs:
            if civ.capital >= 0:
                s = self.world.sites[civ.capital]
                self.cx, self.cy = s.x, s.y
                return

    def say(self, text):
        self.notice = text
        self.notice_t = 90

    def update(self):
        if self.notice_t > 0:
            self.notice_t -= 1
        if pyxel.btnp(pyxel.KEY_R):
            self.seed = random.randrange(0x10000000)
            self.rebuild_world()
            self.mode = "forge"
            self.say("new seed forged")
            return
        if self.mode == "forge":
            self.update_forge()
        elif self.mode == "gen":
            self.update_gen()
        else:
            self.update_viewer()

    def update_forge(self):
        if pyxel.btnp(pyxel.KEY_UP, 12, 4) or pyxel.btnp(pyxel.KEY_W, 12, 4):
            self.param = (self.param - 1) % 5
        if pyxel.btnp(pyxel.KEY_DOWN, 12, 4) or pyxel.btnp(pyxel.KEY_S, 12, 4):
            self.param = (self.param + 1) % 5
        delta = 0
        if pyxel.btnp(pyxel.KEY_LEFT, 12, 4) or pyxel.btnp(pyxel.KEY_A, 12, 4):
            delta = -1
        if pyxel.btnp(pyxel.KEY_RIGHT, 12, 4) or pyxel.btnp(pyxel.KEY_D, 12, 4):
            delta = 1
        if delta:
            if self.param == 0:
                self.age_i = max(0, min(len(AGE_VALUES) - 1, self.age_i + delta))
            elif self.param == 1:
                self.rain = max(1, min(5, self.rain + delta))
            elif self.param == 2:
                self.temp = max(1, min(5, self.temp + delta))
            elif self.param == 3:
                self.civs = max(3, min(10, self.civs + delta))
            else:
                self.evil = not self.evil
            self.rebuild_world()
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            self.gen_stage = 0
            self.gen_t = 0
            self.mode = "gen"

    def update_gen(self):
        self.gen_t += 1
        if self.gen_t % 14 == 0:
            self.gen_stage += 1
        if self.gen_stage >= len(STAGES) and self.gen_t > 96:
            self.mode = "map"
            self.view = 0
            self.say("world opened in legends")

    def cycle_view(self):
        if self.mode == "map":
            if self.view < 2:
                self.view += 1
            else:
                self.mode = "legends"
                self.view = 0
        elif self.mode == "legends":
            self.mode = "history"
        else:
            self.mode = "map"
            self.view = 0

    def update_viewer(self):
        if pyxel.btnp(pyxel.KEY_TAB):
            self.cycle_view()
            return
        if pyxel.btnp(pyxel.KEY_1):
            self.mode = "map"
            self.view = 0
        if pyxel.btnp(pyxel.KEY_2):
            self.mode = "legends"
        if pyxel.btnp(pyxel.KEY_3):
            self.mode = "history"
        if pyxel.btnp(pyxel.KEY_M):
            self.mode = "map"
        if self.mode == "map":
            self.update_map()
        elif self.mode == "legends":
            self.update_legends()
        elif self.mode == "history":
            self.update_history()

    def update_map(self):
        moved = False
        if pyxel.btnp(pyxel.KEY_LEFT, 10, 3) or pyxel.btnp(pyxel.KEY_A, 10, 3):
            self.cx = max(0, self.cx - 1)
            moved = True
        if pyxel.btnp(pyxel.KEY_RIGHT, 10, 3) or pyxel.btnp(pyxel.KEY_D, 10, 3):
            self.cx = min(MW - 1, self.cx + 1)
            moved = True
        if pyxel.btnp(pyxel.KEY_UP, 10, 3) or pyxel.btnp(pyxel.KEY_W, 10, 3):
            self.cy = max(0, self.cy - 1)
            moved = True
        if pyxel.btnp(pyxel.KEY_DOWN, 10, 3) or pyxel.btnp(pyxel.KEY_S, 10, 3):
            self.cy = min(MH - 1, self.cy + 1)
            moved = True
        if moved:
            rid = self.world.tile(self.cx, self.cy).region
            if rid >= 0:
                self.region_i = rid
        if pyxel.btnp(pyxel.KEY_Q):
            self.pick_region(-1)
        if pyxel.btnp(pyxel.KEY_E):
            self.pick_region(1)
        if pyxel.btnp(pyxel.KEY_RETURN):
            tile = self.world.tile(self.cx, self.cy)
            if tile.site >= 0:
                self.mode = "legends"
                self.leg_tab = 1
                self.leg_i = tile.site
            else:
                self.say("no site at cursor")

    def pick_region(self, delta):
        if not self.world.regions:
            return
        self.region_i = (self.region_i + delta) % len(self.world.regions)
        reg = self.world.regions[self.region_i]
        self.cx, self.cy = reg.center

    def current_leg_list(self):
        if self.leg_tab == 0:
            return self.world.figures
        if self.leg_tab == 1:
            return self.world.sites
        if self.leg_tab == 2:
            return self.world.artifacts
        return self.world.civs

    def update_legends(self):
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
            self.leg_tab = (self.leg_tab - 1) % 4
            self.leg_i = 0
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
            self.leg_tab = (self.leg_tab + 1) % 4
            self.leg_i = 0
        items = self.current_leg_list()
        if pyxel.btnp(pyxel.KEY_UP, 10, 4) or pyxel.btnp(pyxel.KEY_W, 10, 4):
            self.leg_i = max(0, self.leg_i - 1)
        if pyxel.btnp(pyxel.KEY_DOWN, 10, 4) or pyxel.btnp(pyxel.KEY_S, 10, 4):
            self.leg_i = min(max(0, len(items) - 1), self.leg_i + 1)
        if pyxel.btnp(pyxel.KEY_RETURN) and items:
            item = items[self.leg_i]
            loc = None
            if self.leg_tab == 0:
                site = self.world.sites[item.site]
                loc = (site.x, site.y)
            elif self.leg_tab == 1:
                loc = (item.x, item.y)
            elif self.leg_tab == 2:
                site = self.world.sites[item.site]
                loc = (site.x, site.y)
            elif item.capital >= 0:
                site = self.world.sites[item.capital]
                loc = (site.x, site.y)
            if loc:
                self.cx, self.cy = loc
                self.mode = "map"

    def update_history(self):
        if pyxel.btnp(pyxel.KEY_UP, 10, 4) or pyxel.btnp(pyxel.KEY_W, 10, 4):
            self.hist_i = max(0, self.hist_i - 1)
        if pyxel.btnp(pyxel.KEY_DOWN, 10, 4) or pyxel.btnp(pyxel.KEY_S, 10, 4):
            self.hist_i = min(max(0, len(self.world.events) - 1), self.hist_i + 1)
        if pyxel.btnp(pyxel.KEY_PAGEUP):
            self.hist_i = max(0, self.hist_i - 8)
        if pyxel.btnp(pyxel.KEY_PAGEDOWN):
            self.hist_i = min(max(0, len(self.world.events) - 1), self.hist_i + 8)
        if pyxel.btnp(pyxel.KEY_RETURN) and self.world.events:
            loc = self.world.events[self.hist_i].loc
            if loc:
                self.cx, self.cy = loc
                self.mode = "map"

    def draw(self):
        if self.mode == "forge" or self.mode == "gen":
            self.draw_forge()
        elif self.mode == "map":
            self.draw_map_screen()
        elif self.mode == "legends":
            self.draw_legends()
        else:
            self.draw_history()
        if self.notice_t > 0:
            pyxel.rect(4, H - 13, W - 8, 10, 0)
            pyxel.text(8, H - 10, trim(self.notice, 54), 15)

    def frame(self, title):
        pyxel.cls(0)
        pyxel.rectb(2, 2, W - 4, H - 4, 3)
        pyxel.rectb(4, 4, W - 8, H - 8, 4)
        pyxel.text(11, 9, title, 12)

    def panel(self, x, y, w, h, title=None):
        pyxel.rect(x, y, w, h, 0)
        pyxel.rectb(x, y, w, h, 3)
        pyxel.rectb(x + 1, y + 1, w - 2, h - 2, 1)
        if title:
            pyxel.text(x + 5, y + 5, title, 12)
            pyxel.line(x + 4, y + 13, x + w - 5, y + 13, 3)

    def bar(self, x, y, value, col):
        for i in range(5):
            pyxel.rect(x + i * 7, y, 5, 5, col if i < value else 14)

    def draw_forge(self):
        self.frame("STONE LEDGER  WORLD FORGE")
        self.panel(10, 25, 78, 126, "PARAMS")
        rows = (
            ("seed", "%07X" % self.seed),
            ("age", "%d yrs" % AGE_VALUES[self.age_i]),
            ("rain", str(self.rain)),
            ("temp", str(self.temp)),
            ("civs", str(self.civs)),
            ("evil", "on" if self.evil else "off"),
        )
        y = 43
        for i, (k, v) in enumerate(rows):
            col = 5 if i - 1 == self.param else 15
            if i == 0:
                col = 15
            pyxel.text(18, y, k.upper(), col)
            if k in ("rain", "temp"):
                self.bar(49, y, int(v), 11 if k == "rain" else 13)
            else:
                pyxel.text(50, y, v, 9 if k != "evil" or self.evil else 7)
            y += 12
        pyxel.rect(18, 111, 58, 12, 5)
        pyxel.text(29, 115, "ENTER", 0)
        pyxel.text(18, 128, "R reroll", 7)

        self.panel(96, 25, 134, 106, "PREVIEW")
        self.draw_world_map(104, 38, 2, 0, cursor=False)
        self.panel(96, 133, 134, 34, "GENERATING" if self.mode == "gen" else "WORLD NOTES")
        if self.mode == "gen":
            pct = min(100, int((self.gen_stage + (self.gen_t % 14) / 14) /
                               len(STAGES) * 100))
            pyxel.text(178, 138, "%3d%%" % pct, 11)
            for i, stage in enumerate(STAGES[:3]):
                mark = "x" if i < self.gen_stage else "." if i == self.gen_stage else " "
                pyxel.text(104, 150 + i * 6, "[%s] %s" % (mark, stage), 9 if mark == "x" else 15)
            for i, stage in enumerate(STAGES[3:]):
                idx = i + 3
                mark = "x" if idx < self.gen_stage else "." if idx == self.gen_stage else " "
                pyxel.text(164, 150 + i * 6, "[%s] %s" % (mark, stage), 9 if mark == "x" else 15)
        else:
            land = sum(1 for y0 in range(MH) for x0 in range(MW)
                       if self.world.tile(x0, y0).biome != "ocean")
            pyxel.text(104, 147, "regions %d  sites %d" %
                       (len(self.world.regions), len(self.world.sites)), 9)
            pyxel.text(104, 155, "events %d   land %d%%" %
                       (len(self.world.events), int(land * 100 / (MW * MH))), 11)
        pyxel.text(10, 169, "UP/DOWN PARAM  LEFT/RIGHT VALUE  ENTER VIEW", 7)

    def draw_tabs(self):
        tabs = (("MAP", self.mode == "map" and self.view == 0),
                ("BIOME", self.mode == "map" and self.view == 1),
                ("CIV", self.mode == "map" and self.view == 2),
                ("LEGENDS", self.mode == "legends"),
                ("HISTORY", self.mode == "history"))
        x = 58
        for label, on in tabs:
            w = len(label) * 4 + 12
            pyxel.rect(x, 20, w, 12, 5 if on else 0)
            pyxel.rectb(x, 20, w, 12, 3)
            pyxel.text(x + 5, 24, label, 0 if on else 15)
            x += w + 3

    def draw_world_map(self, x0, y0, scale, mode, cursor=True, mini_loc=None):
        for y in range(MH):
            for x in range(MW):
                t = self.world.tile(x, y)
                if mode == 2:
                    col = self.world.civs[t.civ].color if t.civ >= 0 else BIOME_COL[t.biome]
                    if t.civ < 0:
                        col = 1 if t.biome != "ocean" else 10
                elif mode == 1:
                    if t.biome == "ocean":
                        col = 10
                    elif t.evil > 0.78:
                        col = 4
                    elif t.volc > 0.82:
                        col = 13
                    elif t.temp < 0.28:
                        col = 7
                    elif t.rain > 0.66:
                        col = 9
                    elif t.rain < 0.28:
                        col = 12
                    else:
                        col = 8
                else:
                    col = BIOME_COL[t.biome]
                pyxel.rect(x0 + x * scale, y0 + y * scale, scale, scale, col)
        if scale >= 2:
            for y in range(MH):
                for x in range(MW):
                    t = self.world.tile(x, y)
                    px, py = x0 + x * scale, y0 + y * scale
                    if t.road:
                        pyxel.pset(px, py + 1, 12)
                    if t.river:
                        pyxel.pset(px + 1, py, 11)
                    if t.site >= 0:
                        site = self.world.sites[t.site]
                        pyxel.rect(px - 1, py - 1, 4, 4, KINDS[site.kind][1])
                        pyxel.pset(px, py, 0)
        if mini_loc:
            mx, my = mini_loc
            pyxel.rectb(x0 + mx * scale - 1, y0 + my * scale - 1, 5, 5, 5)
        if cursor:
            pyxel.rectb(x0 + self.cx * scale - 2, y0 + self.cy * scale - 2,
                        scale + 4, scale + 4, 15)

    def draw_map_screen(self):
        title = ("WORLD MAP", "BIOME LAYERS", "CIVILIZATION MAP")[self.view]
        self.frame(title)
        self.draw_tabs()
        self.panel(6, 35, 124, 103)
        self.draw_world_map(MAP_X, MAP_Y, MAP_SCALE, self.view)
        self.panel(135, 35, 96, 103, "REGIONS")
        self.draw_region_panel()
        self.panel(6, 143, 225, 22)
        t = self.world.tile(self.cx, self.cy)
        r = self.world.region_at(self.cx, self.cy)
        site = self.world.sites[t.site].name if t.site >= 0 else "-"
        civ = self.world.civs[t.civ].name if t.civ >= 0 else "wild"
        pyxel.text(12, 149, "%s / %s" % (trim(r.name, 18), t.biome), 15)
        pyxel.text(12, 157, "site %s" % trim(site, 24), 7)
        pyxel.text(142, 149, "h%02d r%02d t%02d v%02d e%02d" %
                   (t.h * 99, t.rain * 99, t.temp * 99, t.volc * 99, t.evil * 99), 11)
        pyxel.text(142, 157, "TAB view  Q/E reg", 7)

    def draw_region_panel(self):
        if not self.world.regions:
            return
        start = max(0, min(self.region_i - 2, len(self.world.regions) - 6))
        pyxel.text(188, 42, "%d/%d" % (self.region_i + 1, len(self.world.regions)), 7)
        for row, reg in enumerate(self.world.regions[start:start + 6]):
            y = 52 + row * 9
            on = reg.id == self.region_i
            if on:
                pyxel.rect(140, y - 1, 84, 8, 8)
            pyxel.text(144, y, trim(reg.name.upper(), 15), 0 if on else BIOME_COL[reg.biome])
        reg = self.world.regions[self.region_i]
        pyxel.line(141, 105, 224, 105, 3)
        pyxel.text(142, 111, trim(reg.name.upper(), 18), 9)
        pyxel.text(142, 120, trim(BIOME_DESC.get(reg.biome, reg.biome), 20), 15)
        pyxel.text(142, 129, "pop %d" % reg.pop, 7)
        pyxel.text(184, 129, "danger %d" % reg.danger, 5 if reg.danger > 70 else 7)

    def draw_legends(self):
        self.frame("LEGENDS")
        self.draw_tabs()
        labels = ("PEOPLE", "SITES", "ARTIFACTS", "CIVS")
        x = 10
        for i, label in enumerate(labels):
            w = 48 if i != 2 else 64
            on = i == self.leg_tab
            pyxel.rect(x, 35, w, 13, 5 if on else 0)
            pyxel.rectb(x, 35, w, 13, 3)
            pyxel.text(x + 6, 39, label, 0 if on else 15)
            x += w + 4
        self.panel(8, 52, 104, 93)
        self.panel(119, 52, 112, 93)
        self.draw_leg_list()
        self.draw_leg_detail()
        self.panel(8, 150, 223, 15)
        pyxel.text(14, 155, "L/R category  UP/DOWN choose  ENTER map  TAB", 7)

    def draw_leg_list(self):
        items = self.current_leg_list()
        start = max(0, min(self.leg_i - 4, max(0, len(items) - 10)))
        pyxel.text(14, 57, "%d/%d" % (min(self.leg_i + 1, len(items)), len(items)), 7)
        for row, item in enumerate(items[start:start + 9]):
            idx = start + row
            y = 67 + row * 8
            if idx == self.leg_i:
                pyxel.rect(12, y - 1, 96, 8, 5)
            if self.leg_tab == 0:
                name = item.name
                sub = item.role
                col = self.world.civs[item.civ].color if item.civ >= 0 else 15
            elif self.leg_tab == 1:
                name = item.name
                sub = KINDS[item.kind][0]
                col = KINDS[item.kind][1]
            elif self.leg_tab == 2:
                name = item.name
                sub = str(item.year)
                col = 12
            else:
                name = item.name
                sub = item.people
                col = item.color
            pyxel.text(16, y, trim(name.upper(), 14), 0 if idx == self.leg_i else col)
            pyxel.text(82, y, trim(str(sub).upper(), 6), 0 if idx == self.leg_i else 7)

    def draw_leg_detail(self):
        items = self.current_leg_list()
        if not items:
            return
        item = items[min(self.leg_i, len(items) - 1)]
        x, y = 126, 59
        if self.leg_tab == 0:
            civ = self.world.civs[item.civ]
            site = self.world.sites[item.site]
            pyxel.text(x, y, trim(item.name.upper(), 20), 12)
            pyxel.text(x, y + 9, "%s %s" % (item.race, item.role), civ.color)
            pyxel.text(x, y + 21, "born %d" % item.born, 9)
            pyxel.text(x + 48, y + 21, "died %s" % ("-" if item.died < 0 else item.died), 7)
            pyxel.text(x, y + 32, "kills %d" % item.kills, 5 if item.kills else 7)
            pyxel.text(x + 48, y + 32, "deeds %d" % item.deeds, 11)
            pyxel.text(x, y + 43, trim(site.name, 18), 15)
            yy = y + 56
            for line in wrap(item.quote, 22, 3):
                pyxel.text(x, yy, line, 11)
                yy += 8
        elif self.leg_tab == 1:
            civ = self.world.civs[item.civ]
            reg = self.world.region_at(item.x, item.y)
            pyxel.text(x, y, trim(item.name.upper(), 20), 12)
            pyxel.text(x, y + 10, "%s of %s" % (KINDS[item.kind][0], trim(civ.name, 13)), civ.color)
            pyxel.text(x, y + 22, "founded %d" % item.founded, 9)
            pyxel.text(x, y + 32, "pop %d" % item.pop, 15)
            pyxel.text(x, y + 42, "status %s" % item.status, 5 if item.status == "ruin" else 8)
            pyxel.text(x, y + 52, trim(reg.name, 22), 11)
            self.draw_mini_map(174, 113, (item.x, item.y))
        elif self.leg_tab == 2:
            maker = self.world.figures[item.maker]
            site = self.world.sites[item.site]
            pyxel.text(x, y, trim(item.name.upper(), 20), 12)
            pyxel.text(x, y + 11, item.kind.upper(), 15)
            pyxel.text(x, y + 23, "made %d" % item.year, 9)
            pyxel.text(x, y + 34, trim("by " + maker.name, 22), 7)
            pyxel.text(x, y + 45, trim("at " + site.name, 22), 11)
            pyxel.text(x, y + 56, "fame %d" % item.fame, 12)
        else:
            cap = self.world.sites[item.capital] if item.capital >= 0 else None
            pyxel.text(x, y, trim(item.name.upper(), 20), 12)
            pyxel.text(x, y + 11, "%s civilization" % item.people, item.color)
            pyxel.text(x, y + 23, "pop %d" % item.pop, 15)
            pyxel.text(x, y + 34, "sites %d" % len(item.sites), 11)
            pyxel.text(x, y + 45, "mil %s" % item.military, 8 if item.military != "weak" else 7)
            if cap:
                pyxel.text(x, y + 56, trim("capital " + cap.name, 22), 9)
            yy = y + 68
            for line in wrap(item.motto, 22, 2):
                pyxel.text(x, yy, line, 11)
                yy += 8

    def draw_mini_map(self, x, y, loc):
        pyxel.rectb(x - 2, y - 2, 52, 34, 3)
        sx = 48 / MW
        sy = 30 / MH
        for yy in range(0, MH, 2):
            for xx in range(0, MW, 2):
                t = self.world.tile(xx, yy)
                pyxel.pset(x + int(xx * sx), y + int(yy * sy), BIOME_COL[t.biome])
        pyxel.rect(x + int(loc[0] * sx) - 1, y + int(loc[1] * sy) - 1, 3, 3, 5)

    def draw_history(self):
        self.frame("HISTORY")
        self.draw_tabs()
        self.panel(8, 35, 132, 104, "EVENT LOG")
        self.panel(146, 35, 86, 104, "DETAIL")
        self.draw_event_log()
        self.draw_event_detail()
        self.panel(8, 145, 224, 20)
        self.draw_timeline(14, 154, 211)
        pyxel.text(10, 169, "UP/DOWN scroll  ENTER map  PGUP/PGDN jump", 7)

    def draw_event_log(self):
        events = self.world.events
        start = max(0, min(self.hist_i - 5, max(0, len(events) - 11)))
        for row, ev in enumerate(events[start:start + 11]):
            idx = start + row
            y = 52 + row * 8
            if idx == self.hist_i:
                pyxel.rect(12, y - 1, 124, 8, 5)
            col = 0 if idx == self.hist_i else ev.color
            pyxel.text(14, y, "%4d" % ev.year, col)
            pyxel.text(38, y, ev.icon, col)
            pyxel.text(48, y, trim(ev.text, 22), col if idx == self.hist_i else 15)

    def draw_event_detail(self):
        if not self.world.events:
            return
        ev = self.world.events[self.hist_i]
        x, y = 153, 51
        pyxel.text(x, y, "%d  %s" % (ev.year, ev.kind.upper()), ev.color)
        yy = y + 12
        for line in wrap(ev.text, 18, 4):
            pyxel.text(x, yy, line, 15)
            yy += 8
        if ev.loc:
            reg = self.world.region_at(*ev.loc)
            pyxel.text(x, 96, trim(reg.name, 18), 11)
            self.draw_mini_map(165, 105, ev.loc)
        else:
            pyxel.text(x, 116, "worldwide record", 7)

    def draw_timeline(self, x, y, w):
        events = self.world.events
        pyxel.line(x, y, x + w, y, 8)
        pyxel.text(x, y - 9, str(min(e.year for e in events)), 7)
        pyxel.text(x + w - 22, y - 9, str(max(e.year for e in events)), 7)
        lo = min(e.year for e in events)
        hi = max(e.year for e in events)
        span = max(1, hi - lo)
        for i, ev in enumerate(events):
            px = x + int((ev.year - lo) / span * w)
            h = 5 if i == self.hist_i else 3
            pyxel.line(px, y - h, px, y + h, 15 if i == self.hist_i else ev.color)


if __name__ == "__main__":
    App().run()
