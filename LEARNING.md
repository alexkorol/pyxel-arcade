# Pyxel Arcade — Learning Brief

Nine small Python programs, each built around one idea worth stealing. This brief tells you how to run them, what to look for inside each one, and graded exercises to make the code yours.

## Running the demos

```bash
pip install -U pyxel
python demos/koi_pond.py        # any demo runs directly
pyxel run demos/koi_pond.py     # equivalent, via the pyxel launcher
```

To publish on the web: paste a file into https://www.pyxelstudio.net and save, or package locally with `pyxel package demos demos/koi_pond.py` then `pyxel app2html` to get a single shareable HTML file. After you publish each demo, paste its pyxelstudio URL into `script.js` (the new entries ship with `demoUrl: '#'`) and re-shoot the PNG thumbnails referenced there.

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

(The original `mycelium_1.py` mutated a list while iterating it — a classic Python bug. Compare it with `mycelium_garden.py` to see the fix.)

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
Each cell is a byte in a flat grid. Fallers (sand, water) are scanned bottom-up so a grain falls once per frame; risers (fire, smoke) scan top-down for the same reason. Only cells that changed get redrawn (dirty-cell rendering).
1. Add `6 = oil`: floats on water (lighter), burns when touching fire.
2. Known flaw to fix: water can sidestep twice in one frame because sideways moves can re-enter the scan. Add a `moved` bitarray that marks cells already updated this frame and skip them.
3. Add `7 = seed`: falls like sand, but when resting on wet sand it converts to plant and grows upward one cell per second.

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

## Performance notes

Pyxel on the web runs through WASM and is roughly 2–4× slower than desktop. If a demo chugs on pyxelstudio: shrink the world first (`W = H = 96` rescues almost anything), then reduce population constants, then increase `STEP_EVERY`-style throttles. Per-pixel Python loops are the enemy — that's why `powder_box` only redraws dirty cells and `lava_lamp` samples a coarse grid. When you need raw grid speed, `bytearray` + manual indexing beats nested lists, and integer math (`(v * 15) >> 4`) beats float math.

## Particles: dataclass vs dict vs list — which to use?

You'll see three styles in this repo, deliberately. A `@dataclass` (in `mycelium_garden`) gives you named fields, defaults, and a free `__repr__` — best when a particle has behavior and you'll read the code later. A plain class with `__slots__` (the `physarum` agents) trades flexibility for memory and speed when you have hundreds of instances. A raw structure — list-of-lists for koi spines, a flat `bytearray` for powder — wins when the data *is* the math and objects would just be ceremony. The honest rule: start with a dataclass; drop to `__slots__` when profiling says so; drop to arrays when the inner loop runs thousands of times a frame.

## Roadmap (when you're ready)

Sound: `pyxel.sounds[0].set(...)` + `pyxel.play` — give the terrarium chirps and the powder box a fire crackle. Sprites: draw pips in the built-in editor (`pyxel edit`) and blit with `blt` instead of circles. Shipping: `pyxel app2html` produces one self-contained file you can host on GitHub Pages right next to `script.js`. After publishing, fill the `#` demoUrls and replace the thumbnails — the arcade page is already wired for all nine.
