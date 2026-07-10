"""CI quality gate for the arcade. Fails loudly, exits non-zero on problems.

Checks:
  1. every demos/*.py imports only the stdlib + pyxel (the web launcher is
     Pyodide-based and has nothing else)
  2. demos/manifest.json is valid and each entry has its .py, .png and
     games/<slug>.html OG page on disk
  3. smoke test: every manifest game boots headlessly and survives 120
     update/draw ticks (pyxel.run patched out, one subprocess per game
     because pyxel.init is once-per-process)

Usage:
    python tools/check_demos.py            # everything
    python tools/check_demos.py --no-smoke # skip the (slower) smoke tests
    python tools/check_demos.py --smoke-one <slug>   # (internal)
"""
import ast
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEMOS = os.path.join(ROOT, "demos")

# "js" exists only in Pyodide (the web launcher); demos may import it inside
# a try/except for web-only features like the daily seed, never at top level.
ALLOWED_EXTRA = {"pyxel", "js"}
SMOKE_TICKS = 120

errors = []


def err(msg):
    errors.append(msg)
    print(f"FAIL: {msg}")


def check_imports():
    stdlib = set(sys.stdlib_module_names)
    for path in sorted(glob.glob(os.path.join(DEMOS, "*.py"))):
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=name)
            except SyntaxError as e:
                err(f"{name}: syntax error: {e}")
                continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for mod in mods:
                if mod not in stdlib and mod not in ALLOWED_EXTRA:
                    err(f"{name}: imports non-stdlib module '{mod}' "
                        f"(demos must be pure Python + pyxel)")
    print("import check done")


def check_manifest():
    path = os.path.join(DEMOS, "manifest.json")
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        err(f"manifest.json: {e}")
        return []

    games = manifest.get("games", [])
    if not games:
        err("manifest.json: no games listed")
    seen = set()
    for g in games:
        slug = g.get("slug", "?")
        if slug in seen:
            err(f"manifest: duplicate slug '{slug}'")
        seen.add(slug)
        for field in ("title", "description", "controls", "tags", "added"):
            if not g.get(field):
                err(f"manifest[{slug}]: missing or empty '{field}'")
        if not os.path.exists(os.path.join(DEMOS, slug + ".py")):
            err(f"manifest[{slug}]: demos/{slug}.py does not exist")
        if not os.path.exists(os.path.join(DEMOS, slug + ".png")):
            err(f"manifest[{slug}]: demos/{slug}.png thumbnail missing "
                f"(run: python tools/make_previews.py {slug})")
        if not os.path.exists(os.path.join(ROOT, "games", slug + ".html")):
            err(f"manifest[{slug}]: games/{slug}.html OG page missing "
                f"(run: python tools/make_og_pages.py)")
    feed_path = os.path.join(ROOT, "feed.json")
    if os.path.exists(feed_path):
        with open(feed_path, encoding="utf-8") as f:
            feed_ids = " ".join(i["id"] for i in json.load(f).get("items", []))
        for g in games:
            slug = g.get("slug", "?")
            if slug + ".html" not in feed_ids:
                err(f"feed.json is stale: '{slug}' missing "
                    f"(run: python tools/make_feed.py)")

    print(f"manifest check done ({len(games)} games)")
    return [g["slug"] for g in games if g.get("slug")]


def smoke_one(slug):
    import importlib.util

    import pyxel

    pyxel.run = lambda *a, **k: None
    spec = importlib.util.spec_from_file_location(slug, os.path.join(DEMOS, slug + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[slug] = mod
    spec.loader.exec_module(mod)
    app = mod.App()
    for _ in range(SMOKE_TICKS):
        app.update()
        app.draw()
    print(f"smoke ok: {slug} ({SMOKE_TICKS} ticks)")


def smoke_all(slugs):
    for slug in slugs:
        r = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--smoke-one", slug],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            err(f"smoke test crashed for '{slug}':\n{r.stderr[-1500:]}")


def main():
    args = sys.argv[1:]
    if args[:1] == ["--smoke-one"]:
        smoke_one(args[1])
        return

    check_imports()
    slugs = check_manifest()
    if "--no-smoke" not in args and not errors:
        smoke_all(slugs)

    if errors:
        sys.exit(f"\n{len(errors)} problem(s) found")
    print("\nall checks passed")


if __name__ == "__main__":
    main()
