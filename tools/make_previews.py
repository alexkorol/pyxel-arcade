"""Generate animated .webp previews (and .png posters) for every demo.

Each demo is driven headlessly: pyxel.run is patched to a no-op so App()
returns after pyxel.init, then update/draw are called by hand and frames are
read back from pyxel.screen. pyxel.init only works once per process, so the
script re-invokes itself in a subprocess per demo.

Usage:
    python tools/make_previews.py            # all demos in the manifest
    python tools/make_previews.py koi_pond   # just one
    python tools/make_previews.py --one koi_pond   # (internal) in-process
"""
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEMOS = os.path.join(ROOT, "demos")

WARMUP_FRAMES = 90        # let title screens settle / sims get going
CAPTURE_FRAMES = 40       # frames in the loop
CAPTURE_EVERY = 3         # game frames per captured frame
FRAME_MS = 100            # webp frame duration (10 fps)
MAX_SIDE = 480            # upscale small screens (nearest) up to this

# Per-demo capture tweaks: scripted key taps to get past title screens and
# into real gameplay, or a shorter warmup so a one-shot sim is caught growing.
SCRIPT = {
    "vase_forge": {
        # Select twist and exaggerate it while the lathe continues spinning.
        "press": [(16, "KEY_DOWN"), (28, "KEY_DOWN")] + [
            (40 + i * 8, "KEY_RIGHT") for i in range(5)
        ],
    },
    "noita_demake": {"press": [(20, "KEY_RETURN")]},
    "undervault": {
        # enter the dungeon, then wander so the capture shows bump-combat
        "press": [(20, "KEY_RETURN"), (50, "KEY_RETURN")] + [
            (95 + i * 12, key)
            for i, key in enumerate(
                ["KEY_RIGHT", "KEY_RIGHT", "KEY_UP", "KEY_RIGHT", "KEY_DOWN",
                 "KEY_RIGHT", "KEY_UP", "KEY_LEFT", "KEY_RIGHT", "KEY_RIGHT"]
            )
        ],
    },
    "starlance": {"press": [(20, "KEY_RETURN"), (45, "KEY_RETURN"), (70, "KEY_RETURN")]},
    "hill_fort": {"press": [(20, "KEY_RETURN")]},
    "stone_ledger": {"press": [(20, "KEY_RETURN"), (150, "KEY_TAB"), (200, "KEY_TAB")]},
    "shell_lab": {"warmup": 6},
}


def capture_one(slug):
    import pyxel
    from PIL import Image

    pyxel.run = lambda *a, **k: None  # App.__init__ ends with pyxel.run(...)

    script = SCRIPT.get(slug, {})
    warmup = script.get("warmup", WARMUP_FRAMES)
    presses = {frame: getattr(pyxel, key) for frame, key in script.get("press", [])}

    # patch btnp so scripted frames report a pressed key
    state = {"frame": 0}
    real_btnp = pyxel.btnp

    def fake_btnp(key, *a, **k):
        if presses.get(state["frame"]) == key:
            return True
        return real_btnp(key, *a, **k)

    pyxel.btnp = fake_btnp

    path = os.path.join(DEMOS, slug + ".py")
    spec = importlib.util.spec_from_file_location(slug, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[slug] = mod  # dataclass field resolution needs the module registered
    spec.loader.exec_module(mod)
    app = mod.App()

    def tick():
        app.update()
        app.draw()
        state["frame"] += 1

    for _ in range(warmup):
        tick()

    w, h = pyxel.width, pyxel.height
    palette = list(pyxel.colors)
    frames = []
    for _ in range(CAPTURE_FRAMES):
        for _ in range(CAPTURE_EVERY):
            tick()
        img = Image.new("RGB", (w, h))
        px = img.load()
        screen = pyxel.screen
        for y in range(h):
            for x in range(w):
                rgb = palette[screen.pget(x, y)]
                px[x, y] = ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
        frames.append(img)

    scale = max(1, MAX_SIDE // max(w, h))
    if scale > 1:
        frames = [f.resize((w * scale, h * scale), Image.NEAREST) for f in frames]

    out = os.path.join(DEMOS, slug + ".webp")
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        quality=70,
        method=4,
    )
    # write a static poster only if the demo doesn't already have one
    poster = os.path.join(DEMOS, slug + ".png")
    if not os.path.exists(poster):
        frames[0].save(poster)
    print(f"{slug}: {len(frames)} frames {frames[0].size} -> {os.path.getsize(out) // 1024} KB")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--one":
        capture_one(args[1])
        return

    with open(os.path.join(DEMOS, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    slugs = args or [g["slug"] for g in manifest["games"]]

    failed = []
    for slug in slugs:
        r = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--one", slug],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            failed.append(slug)
            sys.stderr.write(f"{slug} FAILED:\n{r.stderr[-2000:]}\n")
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
