"""
AgroAI Stake v1 — parametric 3D model of the self-contained stake (solar + LoRa + vibration),
shaped after the reference image: white body, green roof with solar panel, green LED strip,
green collar, dark stake in the ground.

Requirements:  pip install manifold3d numpy matplotlib
Run:           python agroai_stake.py
Outputs:       ../stl/*.stl (printable), ../stl/stake_assembly.obj/.mtl (colours, Windows "3D Viewer"),
               ../render/*.png, ../render/print_stats.txt

Units: mm, Z up, ground at z = 0. Parts marked REF are bought, modelled only for the preview with
nominal sizes: MEASURE your parts and change the parameters.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np
from manifold3d import Manifold, OpType, set_circular_segments

set_circular_segments(40)
HERE = Path(__file__).resolve().parent
STL_DIR, RENDER_DIR = HERE.parent / "stl", HERE.parent / "render"

# ----------------------------------------------------------------- parameters
BODY = (120.0, 110.0, 120.0)   # W, D, H of the white body (like the image)
BODY_R = 14.0                  # corner radius
WALL = 2.6
ROOF = (128.0, 118.0, 16.0)    # green roof/lid; a 3 W panel needs a bigger roof (e.g. 200 x 170)
PANEL = (110.0, 100.0, 3.0)    # REF solar panel that fits this roof (~1-1.5 W class, measure yours)
TUBE = 25.0                    # REF square aluminium/steel tube, 25 x 25 x 2 mm
STAKE_TOP = 230.0              # top of the metal tube (z)
STAKE_DEPTH = 300.0            # length in the ground
COLLAR_H = 50.0
BODY_Z = STAKE_TOP + 5.0       # bottom of the body
LED_SLOT = (52.0, 6.0)
PCB = (70.0, 55.0, 1.6)        # planned custom PCB (KiCad), vertical on the rear wall
CELL = (18.5, 65.0)            # 18650
PETG_DENSITY = 1.27


# ----------------------------------------------------------------- helpers
def box(x, y, z, center=False):
    return Manifold.cube((x, y, z), center)


def cyl(h, r, r2=None, center=False):
    return Manifold.cylinder(h, r, r if r2 is None else r2, 0, center)


def rbox(w, d, h, r):
    """Rounded-corner box, base on z=0, centred in x/y."""
    r = min(r, w / 2 - 0.01, d / 2 - 0.01)
    cs = [cyl(h, r).translate((sx * (w / 2 - r), sy * (d / 2 - r), 0)) for sx in (-1, 1) for sy in (-1, 1)]
    return Manifold.batch_hull(cs)


def square_ring(w, h, t):
    return box(w, w, h, True) - box(w - 2 * t, w - 2 * t, h + 2, True)


# ----------------------------------------------------------------- printable parts
def body() -> Manifold:
    """White ASA body: open top, floor with motor-wire hole, LED slot, 4 screw bosses, ON mark."""
    w, d, h = BODY
    b = rbox(w, d, h, BODY_R) - rbox(w - 2 * WALL, d - 2 * WALL, h, BODY_R - WALL).translate((0, 0, 3))
    b = b - cyl(10, 3.2).translate((0, 0, -1))                                  # sealed cable pass to motor
    b = b - box(LED_SLOT[0], 10, LED_SLOT[1], True).translate((0, -d / 2, 24))   # light-pipe slot (front)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 - 9), sy * (d / 2 - 9)
            b = b + (cyl(h - 3, 5.0) - cyl(20, 1.25).translate((0, 0, h - 23))).translate((x, y, 3))
            b = b - cyl(20, 1.25).translate((x, y, h - 20))
    b = b - cyl(1.2, 9).rotate((0, 90, 0)).translate((w / 2 - 0.8, 0, 40))          # "ON" magnet spot
    for sx in (-1, 1):                                                           # PCB rails (rear wall)
        rail = box(5, 6, 70) - box(2.2, 2, 72).translate((1.4, -0.5, -1))
        b = b + rail.translate((sx * (PCB[0] / 2 + 1) - 2.5, d / 2 - WALL - 6, 18))
    # 18650 cradle on the floor (front)
    cr = box(CELL[1] + 8, CELL[0] + 6, 12, True).translate((0, 0, 6)) - cyl(
        CELL[1] + 10, CELL[0] / 2 + 0.3, center=True).rotate((0, 90, 0)).translate((0, 0, 12.5))
    cr = cr - box(6, CELL[0] + 8, 3, True).translate((0, 0, 1.5))                 # strap slot
    return b + cr.translate((0, -d / 2 + 22, 3))


def roof() -> Manifold:
    """Green ASA roof/lid: panel recess on top, inner lip with gasket groove, 4 screw holes."""
    w, d, h = ROOF
    r = rbox(w, d, h, BODY_R + 3)
    r = r - box(PANEL[0] + 1, PANEL[1] + 1, PANEL[2] + 1, True).translate((0, 0, h - PANEL[2] / 2))
    r = r - rbox(w - 14, d - 14, h - 5, BODY_R - 3)                              # hollow underside
    lip = rbox(BODY[0] - 2 * WALL - 0.6, BODY[1] - 2 * WALL - 0.6, 8, BODY_R - WALL)
    lip = lip - rbox(BODY[0] - 2 * WALL - 4.6, BODY[1] - 2 * WALL - 4.6, 10, BODY_R - WALL - 2).translate((0, 0, -1))
    lip = lip - (rbox(BODY[0] - 2 * WALL + 1, BODY[1] - 2 * WALL + 1, 2, BODY_R) -
                 rbox(BODY[0] - 2 * WALL - 2.6, BODY[1] - 2 * WALL - 2.6, 2, BODY_R - 2)).translate((0, 0, 3))  # O-ring groove
    r = r + lip.translate((0, 0, -8))
    for sx in (-1, 1):
        for sy in (-1, 1):
            r = r - cyl(40, 1.7).translate((sx * (BODY[0] / 2 - 9), sy * (BODY[1] / 2 - 9), -10))
            r = r + (cyl(h - 5, 4.5) - cyl(40, 1.7).translate((0, 0, -1))).translate(
                (sx * (BODY[0] / 2 - 9), sy * (BODY[1] / 2 - 9), 0))
    r = r - box(6, 4, 6, True).translate((0, d / 2 - 10, h - 6))                 # panel wire pass
    return r


def collar() -> Manifold:
    """Green ASA collar: tapers from the body to the stake, hollow for the motor clamp."""
    top, bot = 74.0, 36.0
    outer = Manifold.batch_hull([rbox(top, top, 1, 10).translate((0, 0, COLLAR_H - 1)), rbox(bot, bot, 1, 6)])
    inner = Manifold.batch_hull([rbox(top - 6, top - 6, 1, 8).translate((0, 0, COLLAR_H)),
                                 rbox(bot - 6, bot - 6, 1, 4).translate((0, 0, 12))])
    c = outer - inner - box(TUBE + 0.6, TUBE + 0.6, 40, True)
    for a in (0, 90, 180, 270):                                                   # 4x M4 into the body floor
        c = c - cyl(20, 1.7).translate((24, 0, COLLAR_H - 12)).rotate((0, 0, a))
        c = c + (cyl(10, 4) - cyl(12, 1.7).translate((0, 0, -1))).translate((24, 0, COLLAR_H - 10)).rotate((0, 0, a))
    return c


def tip() -> Manifold:
    """Dark ASA/PETG pointed tip pushed into the bottom of the metal tube."""
    point = Manifold.batch_hull([box(TUBE, TUBE, 1, True), cyl(1, 1.5).translate((0, 0, -55))])
    plug = box(TUBE - 4.4, TUBE - 4.4, 25, True).translate((0, 0, 12.5))
    return point + plug


def light_pipe() -> Manifold:
    """Clear PETG light pipe: carries the PCB LED to the green strip on the front."""
    return box(LED_SLOT[0] - 0.4, 14, LED_SLOT[1] - 0.4, True)


PRINTABLE = {"body": (body, 1, "ASA bianco"), "roof": (roof, 1, "ASA verde"), "collar": (collar, 1, "ASA verde"),
             "tip": (tip, 1, "ASA/PETG nero"), "light_pipe": (light_pipe, 1, "PETG trasparente")}


# ----------------------------------------------------------------- assembly
WHITE, GREEN, DARK = (0.94, 0.94, 0.92), (0.30, 0.62, 0.20), (0.22, 0.23, 0.25)


def assembly(explode: float = 0.0, cut: bool = False):
    w, d, h = BODY
    e = explode
    parts = []
    tube = (box(TUBE, TUBE, STAKE_TOP + STAKE_DEPTH) - box(TUBE - 4, TUBE - 4, STAKE_TOP + STAKE_DEPTH + 2).translate(
        (0, 0, -1))).translate((-TUBE / 2, -TUBE / 2, -STAKE_DEPTH))
    parts.append(("stake_tube_REF", tube, (0.33, 0.34, 0.36)))
    parts.append(("tip", tip().translate((0, 0, -STAKE_DEPTH - 0.5 * e)), DARK))
    parts.append(("collar", collar().translate((0, 0, STAKE_TOP + 5 - COLLAR_H + 0.3 * e)), GREEN))
    # motor clamp + ERM motor on the tube top (inside the collar): vibration goes into the metal
    clamp = (box(TUBE + 12, TUBE + 12, 22, True) - box(TUBE, TUBE, 24, True)).translate((0, 0, STAKE_TOP - 14))
    parts.append(("motor_clamp_REF", clamp, (0.72, 0.72, 0.75)))
    motor = cyl(16, 6).translate((TUBE / 2 + 6.5, 0, STAKE_TOP - 12))  # vertical, inside the collar
    parts.append(("erm_motor_REF", motor, (0.80, 0.55, 0.20)))
    zb = BODY_Z + 0.6 * e
    parts.append(("body", body().translate((0, 0, zb)), WHITE))
    parts.append(("light_pipe", light_pipe().translate((0, -d / 2 + 6 - 0.4 * e, zb + 24)), (0.55, 1.0, 0.55)))
    # electronics (REF)
    yp = d / 2 - WALL - 4
    parts.append(("pcb_REF", box(PCB[0], PCB[2], PCB[1], True).translate((0, yp, zb + 18 + PCB[1] / 2 + 5)),
                  (0.10, 0.45, 0.22)))
    parts.append(("esp32s3_module_REF", box(18, 3.2, 25.5, True).translate((-14, yp - 2.4, zb + 60)), (0.75, 0.75, 0.78)))
    parts.append(("sx1262_module_REF", box(16, 2.5, 16, True).translate((14, yp - 2.1, zb + 62)), (0.75, 0.75, 0.78)))
    parts.append(("charger_ldo_driver_REF", box(30, 2, 10, True).translate((0, yp - 1.8, zb + 34)), (0.1, 0.1, 0.1)))
    parts.append(("cell_18650_REF", cyl(CELL[1], CELL[0] / 2, center=True).rotate((0, 90, 0)).translate(
        (0, -d / 2 + 22, zb + 3 + 12.5)), (0.15, 0.35, 0.75)))
    parts.append(("antenna_868_REF", cyl(28, 3.2).translate((w / 2 - 22, -d / 2 + 22, zb + h - 34)), (0.85, 0.65, 0.2)))
    parts.append(("reed_switch_REF", cyl(14, 1.5, center=True).rotate((90, 0, 0)).translate((w / 2 - WALL - 3, 0, zb + 40)),
                  (0.8, 0.8, 0.5)))
    zr = zb + h + 1.2 * e
    parts.append(("roof", roof().translate((0, 0, zr)), GREEN))
    pz = zr + ROOF[2] - PANEL[2] + 1.0 * e
    parts.append(("solar_panel_REF", box(PANEL[0], PANEL[1], PANEL[2], True).translate((0, 0, pz + PANEL[2] / 2)),
                  (0.08, 0.13, 0.32)))
    for i in range(1, 4):  # cell grid lines, just for the look
        parts.append((f"panel_line_x{i}", box(0.8, PANEL[1] - 4, 0.3, True).translate(
            (-PANEL[0] / 2 + i * PANEL[0] / 4, 0, pz + PANEL[2] + 0.1)), (0.6, 0.65, 0.75)))
    for i in range(1, 3):
        parts.append((f"panel_line_y{i}", box(PANEL[0] - 4, 0.8, 0.3, True).translate(
            (0, -PANEL[1] / 2 + i * PANEL[1] / 3, pz + PANEL[2] + 0.1)), (0.6, 0.65, 0.75)))
    if cut:  # remove the front-right quarter of the shells to show the inside
        cutter = box(400, 400, 2000).translate((0, -400, -1000))
        shells = {"body", "roof", "collar", "light_pipe", "solar_panel_REF"}
        parts = [(n, (m - cutter) if n in shells or n.startswith("panel_line") else m, c) for n, m, c in parts]
    return parts


# ----------------------------------------------------------------- export + render
def mesh_arrays(m):
    mesh = m.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3].astype(float), np.asarray(mesh.tri_verts).astype(int)


def write_stl(path, m, name):
    v, f = mesh_arrays(m)
    t = v[f]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    with open(path, "wb") as fh:
        fh.write(name.encode()[:80].ljust(80, b" "))
        fh.write(struct.pack("<I", len(f)))
        for k in range(len(f)):
            fh.write(struct.pack("<12fH", *n[k], *t[k, 0], *t[k, 1], *t[k, 2], 0))


def write_obj(path, parts):
    with open(path.with_suffix(".mtl"), "w") as fm:
        for name, _, c in parts:
            fm.write(f"newmtl {name}\nKd {c[0]:.3f} {c[1]:.3f} {c[2]:.3f}\n\n")
    with open(path, "w") as fo:
        fo.write(f"mtllib {path.with_suffix('.mtl').name}\n")
        base = 1
        for name, m, _ in parts:
            v, f = mesh_arrays(m)
            fo.write(f"o {name}\nusemtl {name}\n")
            fo.writelines(f"v {p[0]:.3f} {p[1]:.3f} {p[2]:.3f}\n" for p in v)
            fo.writelines(f"f {a + base} {b + base} {c + base}\n" for a, b, c in f)
            base += len(v)


def render(parts, path, title, elev=20, azim=-55, zoom=None, size=9):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(size, size), dpi=120)
    ax = fig.add_subplot(111, projection="3d")
    light = np.array([0.35, -0.7, 0.65]); light /= np.linalg.norm(light)
    allv = []
    for _, m, rgb in parts:
        if m.is_empty():
            continue
        v, f = mesh_arrays(m)
        t = v[f]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
        shade = 0.5 + 0.5 * np.clip(n @ light, 0, 1)
        ax.add_collection3d(Poly3DCollection(t, facecolors=np.clip(np.outer(shade, rgb), 0, 1), edgecolors="none"))
        allv.append(v)
    allv = np.vstack(allv)
    lo, hi = (np.asarray(zoom[0], float), np.asarray(zoom[1], float)) if zoom else (allv.min(0), allv.max(0))
    c, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
    ax.set_title(title, fontsize=12)
    fig.tight_layout(); fig.savefig(path, facecolor="white"); plt.close(fig)


def main():
    STL_DIR.mkdir(parents=True, exist_ok=True); RENDER_DIR.mkdir(parents=True, exist_ok=True)
    stats = ["part, material, volume_cm3, est_g (100% infill upper bound)"]
    tot = 0.0
    for name, (fn, qty, mat) in PRINTABLE.items():
        m = fn()
        assert m.status().name == "NoError", (name, m.status())
        write_stl(STL_DIR / f"{name}.stl", m, name)
        g = m.volume() / 1000 * PETG_DENSITY * qty
        tot += g
        stats.append(f"{name}, {mat}, {m.volume() / 1000:.1f}, {g:.0f}")
    stats.append(f"TOTAL, , , {tot:.0f}")
    (RENDER_DIR / "print_stats.txt").write_text("\n".join(stats) + "\n", encoding="utf-8")
    print("\n".join(stats))

    parts = assembly()
    write_obj(STL_DIR / "stake_assembly.obj", parts)
    ground = box(500, 500, 1).translate((-250, -250, -1))
    above = ((-110, -110, 150), (110, 110, 420))
    render(parts, RENDER_DIR / "stake_view.png", "AgroAI Stake v1 - vista", zoom=above)
    render(parts + [("ground", ground, (0.45, 0.33, 0.22))], RENDER_DIR / "stake_full.png",
           "AgroAI Stake v1 - intero (30 cm nel terreno)", elev=12, azim=-50,
           zoom=((-250, -250, -360), (250, 250, 420)))
    render(assembly(explode=60), RENDER_DIR / "stake_exploded.png", "Vista esplosa", elev=14, azim=-50,
           zoom=((-160, -160, 120), (160, 160, 640)))
    render(assembly(cut=True), RENDER_DIR / "stake_cutaway.png", "Sezione: PCB, batteria, motore sul picchetto",
           elev=18, azim=-60, zoom=above)
    print("written:", STL_DIR, RENDER_DIR)


if __name__ == "__main__":
    main()
