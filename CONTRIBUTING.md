# Contributing a cartridge

Pyxel Arcade showcases tiny games and toys built with
[Pyxel](https://github.com/kitao/pyxel). Every cartridge runs in the browser
via the Pyxel Web Launcher, straight from this repo — so adding a game is one
pull request.

## Ground rules

- **One file.** Your whole game lives in `demos/<slug>.py`.
- **Stdlib only.** The web launcher runs demos in Pyodide with nothing
  installed beyond Pyxel — `import numpy` (or any third-party package) will
  break in the browser. CI rejects it.
- **`pyxel.run(self.update, self.draw)` at the end of `App.__init__`.**
  CI's smoke test and the preview recorder patch `pyxel.run` out and call
  your `update`/`draw` directly, so the `App` class shape matters.
- **Slug format:** lowercase letters, digits, underscores (`koi_pond`).

## Steps

1. Copy [`demos/_template.py`](demos/_template.py) to `demos/<slug>.py` and
   build your thing. Test locally with `python demos/<slug>.py`
   (`pip install pyxel`).
2. Add an entry to [`demos/manifest.json`](demos/manifest.json): slug, title,
   description, a `controls` list of `[key, action]` pairs, tags, today's
   date, difficulty (`chill` / `normal` / `tricky`), and `touch` (true if
   it's playable with just a mouse/finger).
3. Generate the preview assets (needs `pip install pillow`):

   ```bash
   python tools/make_previews.py <slug>   # demos/<slug>.webp + .png
   python tools/make_og_pages.py          # games/<slug>.html share page
   ```

   If your game has a title screen, add a scripted keypress in the `SCRIPT`
   dict at the top of `tools/make_previews.py` so the preview shows real
   gameplay.
4. Run the same checks CI will run:

   ```bash
   python tools/check_demos.py
   ```

5. Open a PR. CI verifies imports, the manifest, and that your game survives
   120 headless frames without crashing.

## Testing in the web launcher

Anything merged to `master` is playable immediately at
`https://kitao.github.io/pyxel/web/launcher/?run=alexkorol/pyxel-arcade/master/demos/<slug>`
— the launcher pulls the file straight from GitHub. To test your fork before
the PR merges, swap in your own username and branch.
