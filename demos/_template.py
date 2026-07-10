"""Template for a new arcade cartridge.

Copy to demos/<your_slug>.py, keep it a single file, and use only the
Python standard library + pyxel -- the web launcher runs demos in Pyodide,
which has nothing else installed (no numpy!).

Checklist for your PR (see CONTRIBUTING.md):
  1. demos/<your_slug>.py           (this file, renamed)
  2. an entry in demos/manifest.json
  3. python tools/make_previews.py <your_slug>   -> .webp + .png preview
  4. python tools/make_og_pages.py               -> games/<your_slug>.html
  5. python tools/check_demos.py                 -> must pass
"""
import random

import pyxel

W, H = 192, 192


class App:
    def __init__(self):
        pyxel.init(W, H, title="My Cartridge")
        pyxel.mouse(True)
        self.sparks = []
        # pyxel.run must be the last line of __init__ (the smoke test and
        # preview recorder patch it out and drive update/draw directly)
        pyxel.run(self.update, self.draw)

    def update(self):
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            for _ in range(12):
                self.sparks.append([
                    pyxel.mouse_x, pyxel.mouse_y,
                    random.uniform(-1.5, 1.5), random.uniform(-2.5, -0.5),
                    random.randint(20, 50),
                ])
        for s in self.sparks:
            s[0] += s[2]
            s[1] += s[3]
            s[3] += 0.08
            s[4] -= 1
        self.sparks = [s for s in self.sparks if s[4] > 0]

    def draw(self):
        pyxel.cls(1)
        pyxel.text(58, 88, "click anywhere", 7)
        for x, y, _, _, life in self.sparks:
            pyxel.pset(int(x), int(y), 8 + life % 6)


if __name__ == "__main__":
    App()
