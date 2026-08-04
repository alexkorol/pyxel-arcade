"""Vase Forge -- shape a printable vessel in a tiny wireframe workshop.

The preview and the STL use the same closed, hollow triangle mesh.  Only the
Python standard library is needed; browsers get a Blob download through the
Pyodide ``js`` bridge while desktop Pyxel writes beside the process.

Controls: Up/Down select, Left/Right adjust, Space spin, Q/E turn,
          X export STL, R reset.  The panel is also mouse/touch friendly.
"""
import math

import pyxel

W, H = 240, 180
TAU = math.pi * 2.0
SIDES = 32
RINGS = 25


PARAMS = [
    # label, attribute, minimum, maximum, step, display multiplier/suffix
    ("LOBES", "lobes", 2, 10, 1, ""),
    ("FORM", "form", 0.35, 3.0, 0.15, ""),
    ("TWIST", "twist", -1.25, 1.25, 0.05, " turn"),
    ("TAPER", "taper", -0.55, 0.55, 0.05, ""),
    ("RIPPLE", "ripple", 0.0, 0.28, 0.02, ""),
    ("HEIGHT", "height", 44, 82, 2, " mm"),
    ("WIDTH", "width", 22, 42, 2, " mm"),
]


def cross_radius(theta, lobes, form):
    """Gielis superformula with equal axes and paired exponents."""
    q = lobes * theta / 4.0
    v = abs(math.cos(q)) ** form + abs(math.sin(q)) ** form
    return v ** (-1.0 / form) if v > 1e-9 else 1.0


class App:
    def __init__(self):
        pyxel.init(W, H, title="Vase Forge", fps=30)
        pyxel.mouse(True)
        self.angle = 0.45
        self.spin = True
        self.selected = 0
        self.notice = "CLOSED MESH / 0.8 MM WALL"
        self.notice_t = 0
        self.reset()
        pyxel.run(self.update, self.draw)

    def reset(self):
        self.lobes = 5
        self.form = 1.25
        self.twist = 0.28
        self.taper = 0.12
        self.ripple = 0.10
        self.height = 64
        self.width = 32

    def adjust(self, direction):
        _, attr, lo, hi, step, _ = PARAMS[self.selected]
        value = getattr(self, attr) + direction * step
        value = max(lo, min(hi, value))
        if isinstance(lo, int) and isinstance(step, int):
            value = int(value)
        else:
            value = round(value, 3)
        setattr(self, attr, value)
        self.notice = "MESH UPDATED"
        self.notice_t = 24

    def update(self):
        if self.spin:
            self.angle = (self.angle + 0.012) % TAU
        if pyxel.btn(pyxel.KEY_Q):
            self.angle -= 0.035
        if pyxel.btn(pyxel.KEY_E):
            self.angle += 0.035
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.selected = (self.selected - 1) % len(PARAMS)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.selected = (self.selected + 1) % len(PARAMS)
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A):
            self.adjust(-1)
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D):
            self.adjust(1)
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.spin = not self.spin
        if pyxel.btnp(pyxel.KEY_R):
            self.reset()
            self.notice = "DEFAULT FORM RESTORED"
            self.notice_t = 45
        if pyxel.btnp(pyxel.KEY_X):
            self.export_stl()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            if 5 <= mx <= 79 and 32 <= my < 32 + len(PARAMS) * 15:
                self.selected = min(len(PARAMS) - 1, (my - 32) // 15)
                self.adjust(1 if mx >= 61 else -1 if mx < 21 else 0)
            elif 7 <= mx <= 77 and 143 <= my <= 157:
                self.export_stl()
            elif 7 <= mx <= 77 and 160 <= my <= 174:
                self.spin = not self.spin
        if self.notice_t > 0:
            self.notice_t -= 1

    def shape_radius(self, theta, t):
        base = self.width * 0.5
        profile = 0.80 + self.taper * (t - 0.5) * 1.3
        # A soft foot and lip make the silhouette vessel-like and printable.
        foot = 0.10 * math.exp(-((t - 0.04) / 0.08) ** 2)
        lip = 0.11 * math.exp(-((t - 0.95) / 0.08) ** 2)
        ripple = 1.0 + self.ripple * math.sin(t * TAU * 3.0)
        a = theta + t * self.twist * TAU
        sf = cross_radius(a, self.lobes, self.form)
        # Blend the raw superformula to keep every preset printable.
        return base * (profile + foot + lip) * ripple * (0.55 + 0.45 * sf)

    def mesh(self):
        """Return vertices and consistently wound faces for a sealed vase."""
        wall = 0.8
        bottom = 1.6
        verts = []
        # Outer rings include z=0. Inner rings begin above the solid base.
        for inner in (False, True):
            for j in range(RINGS):
                t = j / (RINGS - 1)
                z = bottom + t * (self.height - bottom) if inner else t * self.height
                outer_t = z / self.height
                for i in range(SIDES):
                    a = i * TAU / SIDES
                    radius = self.shape_radius(a, outer_t) - (wall if inner else 0.0)
                    radius = max(2.0, radius)
                    verts.append((radius * math.cos(a), radius * math.sin(a), z))
        faces = []
        outer = 0
        inner = RINGS * SIDES
        for j in range(RINGS - 1):
            for i in range(SIDES):
                n = (i + 1) % SIDES
                a, b = outer + j * SIDES + i, outer + j * SIDES + n
                c, d = a + SIDES, b + SIDES
                faces.extend(((a, b, d), (a, d, c)))
                a, b = inner + j * SIDES + i, inner + j * SIDES + n
                c, d = a + SIDES, b + SIDES
                faces.extend(((a, d, b), (a, c, d)))
        # Solid underside and cavity floor seal the base; the top annulus
        # joins both walls into a rim.
        outer_center = len(verts)
        verts.append((0.0, 0.0, 0.0))
        inner_center = len(verts)
        verts.append((0.0, 0.0, bottom))
        for i in range(SIDES):
            n = (i + 1) % SIDES
            ob, on = outer + i, outer + n
            ib, inn = inner + i, inner + n
            faces.extend(((outer_center, on, ob), (inner_center, ib, inn)))
            ot = outer + (RINGS - 1) * SIDES + i
            otn = outer + (RINGS - 1) * SIDES + n
            it = inner + (RINGS - 1) * SIDES + i
            itn = inner + (RINGS - 1) * SIDES + n
            faces.extend(((ot, otn, itn), (ot, itn, it)))
        return verts, faces

    @staticmethod
    def normal(a, b, c):
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        return nx / length, ny / length, nz / length

    def stl_text(self):
        verts, faces = self.mesh()
        out = ["solid vase_forge"]
        for ia, ib, ic in faces:
            a, b, c = verts[ia], verts[ib], verts[ic]
            n = self.normal(a, b, c)
            out.append("  facet normal %.6g %.6g %.6g" % n)
            out.append("    outer loop")
            for v in (a, b, c):
                out.append("      vertex %.6g %.6g %.6g" % v)
            out.extend(("    endloop", "  endfacet"))
        out.append("endsolid vase_forge")
        return "\n".join(out) + "\n"

    def export_stl(self):
        text = self.stl_text()
        try:
            from js import Blob, URL, document
            blob = Blob.new([text], {"type": "model/stl"})
            link = document.createElement("a")
            link.href = URL.createObjectURL(blob)
            link.download = "vase_forge.stl"
            link.click()
            URL.revokeObjectURL(link.href)
            self.notice = "STL DOWNLOADED"
        except ImportError:
            try:
                with open("vase_forge.stl", "w", encoding="ascii") as handle:
                    handle.write(text)
                self.notice = "WROTE VASE_FORGE.STL"
            except OSError:
                self.notice = "EXPORT FAILED"
        except Exception:
            self.notice = "BROWSER EXPORT FAILED"
        self.notice_t = 90

    def project(self, v):
        # Model z is vertical. Rotate around it, tip toward the viewer, then
        # use perspective projection into the workshop viewport.
        x, y, z = v
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        x, y = x * ca - y * sa, x * sa + y * ca
        tilt = -0.28
        ct, st = math.cos(tilt), math.sin(tilt)
        y, z = y * ct - z * st, y * st + z * ct
        depth = 115.0 + y
        scale = 165.0 / max(45.0, depth)
        return 157 + x * scale, 143 - (z - self.height * 0.48) * scale, depth

    def draw_mesh(self):
        verts, _ = self.mesh()
        pts = [self.project(v) for v in verts]
        # Outer horizontal rings, with stronger foot/lip accents.
        for j in range(RINGS):
            if j % 2 and j not in (RINGS - 1,):
                continue
            col = 12 if j in (0, RINGS - 1) else 5
            for i in range(SIDES):
                a, b = pts[j * SIDES + i], pts[j * SIDES + (i + 1) % SIDES]
                pyxel.line(a[0], a[1], b[0], b[1], col if (a[2] + b[2]) < 230 else 1)
        # Sparse meridians preserve the lathe feel without overdrawing.
        for i in range(0, SIDES, 4):
            for j in range(RINGS - 1):
                a, b = pts[j * SIDES + i], pts[(j + 1) * SIDES + i]
                pyxel.line(a[0], a[1], b[0], b[1], 11 if (a[2] + b[2]) < 230 else 1)
        # Show the inner top ring so the hollow printable wall is legible.
        start = (RINGS * 2 - 1) * SIDES
        for i in range(SIDES):
            a, b = pts[start + i], pts[start + (i + 1) % SIDES]
            pyxel.line(a[0], a[1], b[0], b[1], 6)

    @staticmethod
    def fmt(value):
        return str(value) if isinstance(value, int) else ("%.2f" % value).rstrip("0").rstrip(".")

    def draw(self):
        pyxel.cls(0)
        # Workshop grid and a faint turntable.
        for x in range(91, W, 12):
            pyxel.line(x, 25, x, 174, 1)
        for y in range(30, 175, 12):
            pyxel.line(86, y, 238, y, 1)
        pyxel.elli(117, 156, 82, 15, 1)
        pyxel.ellib(117, 156, 82, 15, 5)
        self.draw_mesh()

        pyxel.rect(0, 0, 84, H, 1)
        pyxel.rect(0, 0, W, 22, 2)
        pyxel.text(7, 7, "VASE", 12)
        pyxel.text(28, 7, "FORGE", 7)
        pyxel.text(92, 7, "SUPERFORMULA LATHE", 5)
        pyxel.text(6, 25, "PARAMETERS", 6)
        for row, (label, attr, _, _, _, suffix) in enumerate(PARAMS):
            y = 34 + row * 15
            if row == self.selected:
                pyxel.rect(4, y - 3, 76, 11, 5)
                col = 0
            else:
                col = 7
            value = self.fmt(getattr(self, attr)) + suffix
            pyxel.text(8, y, label, col)
            pyxel.text(47, y, value, col)
            pyxel.text(68, y, "<>" if row == self.selected else "", col)
        pyxel.rect(7, 143, 70, 15, 3)
        pyxel.text(19, 148, "X  EXPORT STL", 0)
        pyxel.rect(7, 160, 70, 15, 13 if self.spin else 5)
        pyxel.text(15, 165, "SPACE  " + ("SPIN" if self.spin else "HOLD"), 0)
        status = self.notice if self.notice_t or self.notice else "READY"
        pyxel.rect(85, 166, 155, 14, 2)
        pyxel.text(91, 170, status, 10 if self.notice_t else 6)


if __name__ == "__main__":
    App()
