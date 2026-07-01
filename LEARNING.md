# Pyxel Arcade — Learning Brief

Sixteen small Python programs. Ten are single-idea generative toys, each built around one technique worth stealing; five are larger games that combine those techniques into something you can lose an evening to; one (`mycelium_1.py`) is the rough prototype the others grew out of, kept for contrast. This brief tells you how to run them, what to look for inside each one, and graded exercises to make the code yours. The ten toys get a section apiece below; the five games get a shorter tour after them.

## Running the demos

```bash
pip install -U pyxel
python demos/koi_pond.py        # any demo runs directly
pyxel run demos/koi_pond.py     # equivalent, via the pyxel launcher
```

The arcade page (`index.html` + `script.js`) already lists every demo, linking each to the Pyxel Web Launcher, which runs the `.py` straight from this GitHub repo — so a pushed change is playable immediately, no separate publish step. If you'd rather host a self-contained copy, package locally with `pyxel package demos demos/koi_pond.py` then `pyxel app2html` for a single shareable HTML file, or paste a file into https://www.pyxelstudio.net. Either way, re-shoot the PNG thumbnails in `demos/` when a demo's look changes (`python demos/<name>.py --screenshot` where a demo supports it, e.g. `noita_demake`).

Every file ends with:

```python
if __name__ == "__main__":
    App().run()
```

`App.__init__` sets up state and calls `pyxel.init`; `App.run` calls `pyxel.run`. Splitting them means a test script can import the module, build an `App`, and call `update()`/`draw()` by hand without opening a window. That's how this whole set was smoke-tested.

## The Pyxel mental model

Pyxel is a fantasy console: a small screen (these demos use 128–160 px), a fixed 16-color palette, and one rule — you hand `pyxel.run` two functions and it calls them forever, 30 times a second:

- `update()` — change state. Read input here (`btn` = held, `btnp` = pressed this frame).
- `draw()` — paint state. No logic, just `cls`, `pset`, `line`, `circ`, `rect`, `text`, ...

Keep that separation strict and every program stays legible. The palette, by index:

| # | color | # | color | # | color | # | color |
|---|-------|---|-------|---|-------|---|-------|
| 0 | black | 4 | brown | 8 | red | 12 | cyan |
| 1 | navy | 5 | slate | 9 | orange | 13 | gray |
| 2 | purple | 6 | sky | 10 | yellow | 14 | pink |
| 3 | teal | 7 | white | 11 | lime | 15 | peach |

A useful habit when reading the demos: colors are always these bare numbers, so `pyxel.cls(1)` is "fill with deep navy water" and `circ(x, y, r, 11)` is "lime lily pad."

## House idioms (they repeat on purpose)

**Persistent canvas.** `color_mycelium` and `physarum` never call `cls` each frame. Each tip draws only a short `line` from where it was to where it is, and the screen itself becomes the data structure storing the whole picture. Erasing becomes its own effect: sprinkle random black `pset`s for a film-grain fade.

**The signed-angle steering trick.** To turn smoothly toward a target without spinning the long way around:

```python
diff = (target - angle + math.pi) % math.tau - math.pi   # always in (-pi, pi]
angle += diff * 0.06                                     # ease toward it
```

That one-liner appears in `mycelium_garden`, `physarum`, and `koi_pond`. Derive why it works once on paper and you own it forever.

**List-comprehension lifecycles.** Things that die get filtered, never `remove()`d mid-loop:

```python
self.ripples = [r for r in self.ripples if r.alive]
```

(`mycelium_1.py` is the prototype the rest grew from; its first draft `remove()`d tips *while iterating* the same list — a classic Python bug that silently skips elements. It now builds fresh `survivors`/`babies` lists each step instead, the same shape as the one-liner above. `git log -p demos/mycelium_1.py` shows the before/after if you want to see the bug in the wild.)

**Flat bytearray grids.** `powder_box` and `physarum` store the world as one `bytearray(W * H)` indexed by `x + y * W` instead of a list of lists. It's faster, cache-friendly, and copying is one call. The trade: you must do the index math yourself.

**Population caps.** Every spawning system has a hard ceiling (`POP_CAP`, `MAX_TIPS`, blob counts). Unbounded growth is the #1 way a cute sim becomes a slideshow.

**Draw order is depth.** No z-buffer exists. `koi_pond` draws fish, then ripples, then lily pads — so koi visibly glide *under* the pads. Reordering the draw calls reorders the world.

## Demo by demo

### color_mycelium.py — persistent canvas, polar motion
Tips move by angle + speed (`cos`/`sin`), wobble their curvature, and branch with mirrored curl so growth stays balanced. Four palette ramps give the threads moods; the fade toggle shows off the random-`pset` erase trick.
1. Add a `K` key that doubles `prob_split` while held — watch density explode.
2. Make branches inherit a *slightly hue-shifted* color (move ±1 along the current ramp) instead of a random one.
3. Give each tip a `width` that shrinks with depth-of-branching, drawn as a 2px line for trunk generations.

### mycelium_garden.py — steering, energy economy, dataclasses
Tips smell the nearest nutrient and ease toward it with the signed-angle trick. Eating raises `energy`; branching *splits* energy between parent and child; rich, old tips fruit into mushrooms that puff spores which germinate. A full lifecycle from four rules.
1. Tune one constant at a time (`BRANCH_COST`, `SMELL_RADIUS`) and write down what changes — this is the actual skill of sim design.
2. Add a poison nutrient (color 2) that *drains* energy; watch the network learn to route around it by dying there.
3. Make spores drift on a slight global "wind" vector that slowly rotates.

### powder_box.py — cellular automata, two-pass scanning
Each cell is a byte in a flat grid. Fallers (sand, water, oil) are scanned bottom-up so a grain falls once per frame; risers (fire, smoke, oil) scan top-down for the same reason. Oil is the demo's showpiece of the two-pass idea: it falls through air, refuses to sink through water, and *floats up* through it — three behaviors that only stay consistent because each pass moves a cell at most once. Only cells that changed get redrawn (dirty-cell rendering).
1. Oil (key `6`) is built in — read `flow`, `float_up`, and `burn` together and explain why the upward step lives in the riser pass, not the faller pass. Then add `7 = seed`: falls like sand, but when it rests on wet sand it turns to plant and grows upward one cell per second.
2. Known flaw to fix: water can sidestep twice in one frame because sideways moves can re-enter the scan. Add a `moved` bitarray that marks cells already updated this frame and skip them.
3. Give oil a slow evaporation-into-smoke chance when it sits next to fire but never catches, so a slick doesn't pool forever.

### terrarium.py — state machines, day/night, layered scenes
Each pip runs a tiny state machine (`roam → seek → eat → lay egg`), with species-specific movement (trot / hop / float). A 1800-frame clock drives dusk, sleep, and firefly glow. Read `draw()` top to bottom and notice it's literally back-to-front scene layers.
1. Add a fourth species with a movement style of your invention (burrower? wall-climber?).
2. Make overfed pips (3+ berries) grow one pixel larger and move slower.
3. Add a moth that spawns only at night and despawns at dawn; blue pips chase it.

### physarum.py — agent sense/act loops, emergence
320 agents each sample the trail map at three sensor points ahead, turn toward the strongest smell, move, and deposit. The trail decays each frame (`(v * 15) >> 4` — integer fade with no floats). Networks, mazes, and webs emerge from *nothing but that*.
1. Make presets 1/2/3 also change deposit amount; find a setting that yields tight dots.
2. Add a second species with its own trail channel that *avoids* the first species' trail.
3. Hold right-click to stamp a repellent (negative scent) and herd the mold.

### hex_bloom.py — hex coordinates, sparse dict grids
Axial coordinates `(q, r)` address hexagons; pixel→hex conversion uses cube rounding (the Red Blob Games method, worth reading start to finish). The grid is a dict, so only living cells cost memory. Ulam-Warburton rule: an empty hex is born if it touches exactly one living hex — on hexes this grows real-looking snowflakes.
1. Change `STEP_EVERY` to 1 and to 12; describe how rhythm changes the *feel* of growth.
2. Add rule `{1, 3}` as a third toggle and name what it grows.
3. Color cells by *which seed* they grew from instead of by generation (flood the seed id through births).

### shell_lab.py — elementary CA, 1-D signal shaded into a 3-D body
The whole simulation is one `bytearray` row, stepped in place by the one
line that *is* an elementary automaton: `out[i] = (rule >> nbhd) & 1`,
where `nbhd` packs the three neighbours into a 0–7 index. Generations are
never stored; each is painted as a single vertical column onto a canvas
that's never cleared, so the picture *is* the memory (the `color_mycelium`
trick again). The depth illusion is pure shading: each column squeezes the
full circumference into its height, then colours every pixel by its `rim`
distance from the spine — highlight, mid, shadow, contour — which curves a
flat 1-D pattern away like a real shell. Palettes swap whole specimens via
`pyxel.colors[:]`, the same idiom `undervault` uses.
1. Add a specimen: pick a rule, draw it as a thumbnail first (`ca_triangle`),
   then hand-tune a seven-colour ramp until it reads as a real shell.
2. Default seed mode is `SINGLE` (one iconic Wolfram cone). Switch to
   `RANDOM` and explain why the tents now cover the *whole* shell.
3. Colour pigment cells by the generation they were born in (a slow ramp
   down the shell) instead of by rim — growth rings.

### oculus_garden.py — kinematic chains, clamped vectors, shyness
Each stalk is a chain of segments whose angles stack; sway is a phase-shifted sine down the chain, lean is mouse-driven. The iris is the cursor direction *clamped* to a max radius inside the eyeball; the pupil dilates with proximity. Blinking and getting shy when stared at are 4-line state machines.
1. Make stalk height vary with where you plant it (shorter near edges, like real light competition).
2. Add a rare "wink" — one eye blinks alone every few hundred frames.
3. When the cursor moves fast, make every iris lag behind it (store a smoothed cursor and track that).

### lava_lamp.py — scalar fields, metaballs, feedback
Every blob radiates `r² / d²` influence; sample the summed field on a coarse grid of 4px blocks and paint by threshold bands. Two thresholds = goo with a highlight rim. Buoyancy is a feedback loop: heat rises where blobs aren't, blobs drift toward heat, overshoot, cool, sink.
1. Lower `CELL` to 2. Watch the frame rate; now raise the thresholds' count to 4 bands and pick prettier colors.
2. Give each blob a tiny color identity and blend bands by the *dominant* contributor.
3. Make `SPACE` reverse gravity for 3 seconds instead of reheating.

### koi_pond.py — segment chains, draw-order depth
Each koi is 9 spine joints; the head steers (signed-angle trick again), every other joint just moves toward the joint ahead when stretched past `GAP`. That constraint alone makes the body flex like a fish. Ripples expand as `circb`s and only *fresh* ones attract koi.
1. Make koi subtly avoid each other (if two heads are close, steer apart) — instant schooling feel.
2. Add a food pellet (right-click) that koi race to; first one there eats it and grows a segment.
3. Spawn a fry (3-segment koi) when two koi heads touch while both are near a fresh ripple.

## The five games

These are bigger — hundreds of lines, multiple screens, a title and an end state — but every one is the toy techniques above wearing a coat. Read a toy first, then find the same trick load-bearing inside a game.

### hill_fort.py — a fortress colony sim
A 48×40×3 tile world, a shared job queue, and dwarves that path to work they choose themselves. The reusable parts: a compact grid-BFS (`find_path`) that takes a *set* of goal tiles so "reach any tile next to this tree" is one call; a job-revision counter (`job_rev`) so idle dwarves don't re-scan the queue every frame; and needs/mood as plain floats nudged each tick. It also carries a JSON save/load and a live perf readout in the HUD. Exercise: add a "haul" job so mined stone has to be carried to a stockpile before it counts.

### noita_demake.py — a wand-and-powder cave crawl
The `powder_box` falling-sand idea scaled to a 560×176 world with water, oil, lava, toxic sludge, fire, and smoke that all interact (lava + water → rock + steam), plus a platformer character, spell projectiles that dig terrain, enemies, and a shop. The lesson worth stealing: the sim only updates cells inside a margin around the camera (see `update_materials`), which is the only reason a world that big runs at all. Exercise: add a new liquid — acid that eats dirt and rock but not brick.

### stone_ledger.py — a world forge and legends browser
Value-noise heightmaps (the `fbm` stack), downhill river tracing, flood-filled biome regions, then civilizations, wars, artifacts, and a browseable event timeline generated on top. It's a master class in *deterministic* generation: everything hangs off one seed through a `random.Random(seed)`, so the same seed always forges the same world. Exercise: add a "plague" event type that culls a site's population and shows on the timeline.

### starlance.py — a wireframe space dogfighter
A from-scratch 3D pipeline in ~50 lines (`cam` translates and rotates, `project` does the perspective divide), models stored as vert/edge lists, and an FTL-style run of jumps, shops, and a boss. Debris is made by exploding the dead ship's own edges into drifting line segments. Exercise: add a wingman ship that flies the same pipeline and shoots the enemy nearest *it*.

### undervault.py — a lane-based dungeon crawler
Pseudo-3D from three floor "lanes" of converging width, `pyxel.pal()` swaps for torch-lit light banding, a turn scheduler, and modal UI screens (inventory, log, character) drawn over a paused world. The trick to study: the whole scene is painted back-to-front by lane, so a monster in a near lane correctly overlaps one behind it with no z-buffer — the same "draw order is depth" idea as `koi_pond`, in a grid. Exercise: add a thrown-torch item that lights a tile a few squares away.

## Performance notes

Pyxel on the web runs through WASM and is roughly 2–4× slower than desktop. If a demo chugs on pyxelstudio: shrink the world first (`W = H = 96` rescues almost anything), then reduce population constants, then increase `STEP_EVERY`-style throttles. Per-pixel Python loops are the enemy — that's why `powder_box` only redraws dirty cells and `lava_lamp` samples a coarse grid. When you need raw grid speed, `bytearray` + manual indexing beats nested lists, and integer math (`(v * 15) >> 4`) beats float math.

## Particles: dataclass vs dict vs list — which to use?

You'll see three styles in this repo, deliberately. A `@dataclass` (in `mycelium_garden`) gives you named fields, defaults, and a free `__repr__` — best when a particle has behavior and you'll read the code later. A plain class with `__slots__` (the `physarum` agents) trades flexibility for memory and speed when you have hundreds of instances. A raw structure — list-of-lists for koi spines, a flat `bytearray` for powder — wins when the data *is* the math and objects would just be ceremony. The honest rule: start with a dataclass; drop to `__slots__` when profiling says so; drop to arrays when the inner loop runs thousands of times a frame.

## Roadmap (when you're ready)

Sound: `pyxel.sounds[0].set(...)` + `pyxel.play` — give the terrarium chirps and the powder box a fire crackle (the games already score themselves this way; see `make_sounds` in `starlance` or `undervault`). Sprites: draw pips in the built-in editor (`pyxel edit`) and blit with `blt` instead of circles. Shipping: the arcade page already runs every demo straight from the repo through the Pyxel Web Launcher, so pushing is publishing; `pyxel app2html` is there if you want a standalone file too. When a demo's look changes, re-shoot its thumbnail so the card in `script.js` matches.
