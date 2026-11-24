"""
AgroAI Node v1 — parametric 3D model (printable parts + reference assembly).

Requirements:  pip install manifold3d numpy matplotlib
Run:           python agroai_node.py
Outputs (next to this folder):
  ../stl/*.stl            printable parts (PETG or ASA, NOT PLA: UV + heat)
  ../stl/assembly.obj/.mtl full assembly with colours (opens in Windows "3D Viewer")
  ../render/*.png         preview images
  ../render/print_stats.txt  volume / estimated filament per part

Units: millimetres. Z is up, ground level is z = 0.
Parts marked REF are bought, not printed: they are modelled only for the preview,
with nominal sizes. MEASURE your real parts and change the parameters below.
"""
from __future__ import annotations

import math
import os
import struct
from pathlib import Path

import numpy as np
from manifold3d import Manifold, set_circular_segments

set_circular_segments(48)

HERE = Path(__file__).resolve().parent
STL_DIR = HERE.parent / "stl"
RENDER_DIR = HERE.parent / "render"

# ----------------------------------------------------------------- parameters
POLE_D = 25.0            # PVC conduit pole, outer diameter
POLE_FIT = 0.6           # clearance for printed parts sliding on the pole
POLE_LEN = 2000.0
POLE_IN_GROUND = 400.0

BOX = (158.0, 90.0, 60.0)  # REF: commercial IP65 ABS box (L, W, H) - buy, do not print
BOX_Z = 700.0              # height of box bottom above ground

PANEL = (136.0, 110.0, 3.0)  # REF: 6 V solar panel - measure yours!
PANEL_TILT = 35.0            # deg; ~latitude in Italy (36-47 deg N) for year-round

SHIELD_R = 55.0          # radiation shield outer radius
SHIELD_PLATES = 4        # louvred plates (+1 top cap)
SHIELD_Z = 1250.0   # WMO: air T/RH at 1.25-2 m above ground

PLATE = (140.0, 74.0, 3.0)   # internal mounting plate (must fit inside BOX)
GRID = 10.0                  # M3 hole grid pitch on the mounting plate
CELL_18650 = (18.6, 70.0)    # diameter, length (with margin)

PETG_DENSITY = 1.27      # g/cm3


# ----------------------------------------------------------------- helpers
def box(x, y, z, center=False):
    return Manifold.cube((x, y, z), center)


def cyl(h, r, r2=None, center=False):
    return Manifold.cylinder(h, r, r if r2 is None else r2, 0, center)


def ring(h, r_out, r_in):
    return cyl(h, r_out) - cyl(h + 2, r_in).translate((0, 0, -1))


# ----------------------------------------------------------------- printable parts
def mount_plate() -> Manifold:
    """Internal plate: M3 hole grid for any module + saddle for one 18650 holder."""
    px, py, pz = PLATE
    p = box(px, py, pz)
    holes = []
    nx, ny = int((px - 10) // GRID), int((py - 10) // GRID)
    ox, oy = (px - (nx - 1) * GRID) / 2, (py - (ny - 1) * GRID) / 2
    for i in range(nx):
        for j in range(ny):
            holes.append(cyl(pz + 2, 1.65).translate((ox + i * GRID, oy + j * GRID, -1)))
    # corner slots for the box mounting bosses (positions differ per box model)
    for sx in (6, px - 6):
        for sy in (6, py - 6):
            holes.append(box(8, 3.6, pz + 2, True).translate((sx, sy, pz / 2)))
    p = p - Manifold.batch_boolean(holes, OpType_add())
    # 18650 saddles along the plate top edge (holder or bare cell + zip ties)
    r = CELL_18650[0] / 2
    for x in (px * 0.25, px * 0.25 + CELL_18650[1] - 12):
        s = box(10, r * 2 + 6, r + pz).translate((x - 5, py - (r * 2 + 6) - 2, 0))
        s = s - cyl(12, r).rotate((0, 90, 0)).translate((x - 6, py - r - 5, pz + r))
        s = s - box(12, 4, 2).translate((x - 6, py - r - 7, pz + 1))  # zip-tie slot
        p = p + s
    return p


def OpType_add():
    from manifold3d import OpType
    return OpType.Add


def pole_clamp() -> Manifold:
    """Collar for the pole with a flange to screw the box (2x M4, 40 mm apart)."""
    ri = POLE_D / 2 + POLE_FIT / 2
    ro = ri + 5
    h = 22
    c = cyl(h, ro)
    flange = box(60, 6, h).translate((-30, ro - 1, 0))
    ears = box(16, 10, h).translate((-8, -ro - 8, 0))
    c = c + flange + ears
    c = c - cyl(h + 2, ri).translate((0, 0, -1))
    c = c - box(2.5, 12, h + 2).translate((-1.25, -ro - 9, -1))           # slit
    c = c - cyl(30, 1.7).rotate((0, 90, 0)).translate((-15, -ro - 3, h / 2))  # M3 tightening
    for x in (-20, 20):
        c = c - cyl(20, 2.2).rotate((-90, 0, 0)).translate((x, ro - 5, h / 2))  # M4 to box
    return c


def panel_bracket() -> Manifold:
    """Pole-top socket + tilted plate for the solar panel (4x M3 or VHB tape)."""
    ri = POLE_D / 2 + POLE_FIT / 2
    sock = ring(45, ri + 4, ri) + cyl(4, ri + 4).translate((0, 0, 41))  # closed top
    pw, ph = PANEL[0] - 16, PANEL[1] - 20
    plate = box(pw, ph, 4, True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            plate = plate - cyl(10, 1.7, center=True).translate((sx * (pw / 2 - 8), sy * (ph / 2 - 8), 0))
    plate = plate - box(pw - 40, ph - 40, 10, True)  # lighten
    rib = box(8, ph * 0.9, 4, True) + box(pw * 0.9, 8, 4, True)
    plate = (plate + rib).rotate((PANEL_TILT, 0, 0)).translate((0, 0, 60))
    strut = box(10, 10, 30, True).translate((0, 0, 50))
    return sock + strut + plate


def shield_plate(top: bool = False) -> Manifold:
    """Stevenson-style louvre: conical shell, open centre, 3 bosses for M4 threaded rods."""
    h, t = 14.0, 2.4
    outer = cyl(h, SHIELD_R, SHIELD_R - 14)
    inner = cyl(h, SHIELD_R - t, SHIELD_R - 14 - t).translate((0, 0, -t))
    s = outer - inner
    if not top:
        s = s - cyl(h + 2, 26).translate((0, 0, -1))
    bosses, holes = [], []
    for k in range(3):
        a = math.radians(90 + k * 120)
        x, y = 40 * math.cos(a), 40 * math.sin(a)
        bosses.append(cyl(h, 5.5).translate((x, y, 0)))
        holes.append(cyl(h + 2, 2.2).translate((x, y, -1)))
    for b in bosses:
        s = s + b
    for hl in holes:
        s = s - hl
    return s


def shield_base_arm() -> Manifold:
    """Bottom disc of the shield (SHT40/BH1750 carrier) + arm + pole collar."""
    ri = POLE_D / 2 + POLE_FIT / 2
    disc = cyl(4, 46) - cyl(6, 14).translate((0, 0, -1))
    for k in range(3):
        a = math.radians(90 + k * 120)
        disc = disc - cyl(6, 2.2).translate((40 * math.cos(a), 40 * math.sin(a), -1))
    # sensor carrier: small bridge with 2x M2.5 holes (Adafruit STEMMA QT boards use 2.5 mm holes)
    bridge = box(40, 8, 4).translate((-20, -4, 0))
    bridge = bridge - cyl(6, 1.35).translate((-10, 0, -1)) - cyl(6, 1.35).translate((10, 0, -1))
    arm = box(110, 14, 8).translate((40, -7, 0))
    collar = ring(22, ri + 5, ri).translate((150 + ri, 0, 0))
    collar = collar - box(2.5, 30, 24).translate((150 + 2 * ri + 2, -15, -1))  # slit
    return disc + bridge + arm + collar


def probe_cap() -> Manifold:
    """Cap over the electronics of a capacitive soil sensor; fill with epoxy / potting."""
    outer = box(32, 14, 42)
    inner = box(26, 8, 40).translate((3, 3, -1))
    cable = cyl(10, 2.6).translate((16, 7, 36))
    return outer - inner - cable


PRINTABLE = {
    "mount_plate": (mount_plate, 1),
    "pole_clamp": (pole_clamp, 2),
    "panel_bracket": (panel_bracket, 1),
    "shield_plate": (lambda: shield_plate(False), SHIELD_PLATES),
    "shield_top": (lambda: shield_plate(True), 1),
    "shield_base_arm": (shield_base_arm, 1),
    "probe_cap": (probe_cap, 1),
}


# ----------------------------------------------------------------- reference (bought) parts
def ref_parts():
    """Returns list of (name, manifold, rgb) in assembly position."""
    out = []
    pole = cyl(POLE_LEN, POLE_D / 2).translate((0, 0, -POLE_IN_GROUND))
    out.append(("pole_pvc_25mm", pole, (0.85, 0.85, 0.85)))

    # enclosure (REF), hanging on the side of the pole, facing -Y
    bx, by, bz = BOX
    yb = -(POLE_D / 2 + 5 + 6 + 2)
    body = box(bx, by, bz).translate((-bx / 2, yb - by, BOX_Z))
    lid = box(bx, by, 6).translate((-bx / 2, yb - by, BOX_Z + bz))
    out.append(("ip65_box", body, (0.55, 0.58, 0.6)))
    out.append(("ip65_box_lid", lid, (0.7, 0.72, 0.74)))
    # cable glands under the box
    for i in range(5):
        g = cyl(14, 6).translate((-bx / 2 + 20 + i * 29, yb - by / 2, BOX_Z - 14))
        out.append((f"gland_{i}", g, (0.15, 0.15, 0.15)))
    # LoRa antenna on the box side
    ant = cyl(190, 5, 4).translate((bx / 2 + 8, yb - by / 2, BOX_Z + bz - 10))
    out.append(("antenna_868", ant, (0.1, 0.1, 0.1)))

    # solar panel on the bracket
    pw, ph, pt = PANEL
    panel = box(pw, ph, pt, True).translate((0, 0, 4)).rotate((PANEL_TILT, 0, 0))
    panel = panel.translate((0, 0, POLE_LEN - POLE_IN_GROUND + 60))
    out.append(("solar_panel_6v", panel, (0.1, 0.18, 0.42)))

    # soil probes (in the ground, 30 cm from the pole)
    soil = box(23, 1.6, 98).translate((-11.5, -300, -80))
    out.append(("soil_moisture_probe", soil, (0.05, 0.35, 0.15)))
    ds = cyl(50, 3).translate((60, -300, -150))
    out.append(("ds18b20_probe", ds, (0.75, 0.75, 0.75)))

    # latching valve on the drip line (REF), left of the pole on the ground
    v = box(70, 40, 50).translate((250, -150, 0)) + cyl(110, 13).rotate((0, 90, 0)).translate((230, -130, 20))
    out.append(("valve_9v_latching", v, (0.2, 0.2, 0.2)))
    coil = cyl(45, 15).translate((285, -130, 50))
    out.append(("valve_solenoid", coil, (0.1, 0.1, 0.1)))
    pipe = cyl(1000, 8).rotate((0, 90, 0)).translate((-300, -130, 20))
    out.append(("drip_line_16mm", pipe, (0.05, 0.05, 0.05)))
    return out


def printable_in_assembly():
    bx, by, bz = BOX
    top = POLE_LEN - POLE_IN_GROUND
    yb = -(POLE_D / 2 + 5 + 6 + 2)
    out = []
    pc = pole_clamp().rotate((0, 0, 180))
    out.append(("pole_clamp_low", pc.translate((0, 0, BOX_Z + 8)), (0.95, 0.55, 0.1)))
    out.append(("pole_clamp_high", pc.translate((0, 0, BOX_Z + bz - 30)), (0.95, 0.55, 0.1)))
    plate = mount_plate().translate((-PLATE[0] / 2, yb - by + (by - PLATE[1]) / 2, BOX_Z + 4))
    out.append(("mount_plate", plate, (0.95, 0.55, 0.1)))
    out.append(("panel_bracket", panel_bracket().translate((0, 0, top - 41)), (0.95, 0.55, 0.1)))
    # shield to the +X side of the pole
    ri = POLE_D / 2 + POLE_FIT / 2
    sx = -(150 + ri)
    base = shield_base_arm().translate((sx, 0, SHIELD_Z))
    out.append(("shield_base_arm", base, (0.97, 0.97, 0.95)))
    for i in range(SHIELD_PLATES):
        out.append((f"shield_plate_{i}", shield_plate().translate((sx, 0, SHIELD_Z + 12 + i * 13)), (0.97, 0.97, 0.95)))
    out.append(("shield_top", shield_plate(True).translate((sx, 0, SHIELD_Z + 12 + SHIELD_PLATES * 13)), (0.97, 0.97, 0.95)))
    for k in range(3):
        a = math.radians(90 + k * 120)
        rod = cyl(SHIELD_PLATES * 13 + 30, 2).translate((sx + 40 * math.cos(a), 40 * math.sin(a), SHIELD_Z - 4))
        out.append((f"m4_rod_{k}", rod, (0.6, 0.6, 0.6)))
    cap = probe_cap().translate((-16, -307, 18))
    out.append(("probe_cap", cap, (0.95, 0.55, 0.1)))
    return out


# ----------------------------------------------------------------- export
def mesh_arrays(m: Manifold):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    f = np.asarray(mesh.tri_verts).astype(np.int64)
    return v, f


def write_stl(path: Path, m: Manifold, name: str):
    v, f = mesh_arrays(m)
    tris = v[f]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    with open(path, "wb") as fh:
        fh.write(name.encode()[:80].ljust(80, b" "))
        fh.write(struct.pack("<I", len(f)))
        for k in range(len(f)):
            fh.write(struct.pack("<12fH", *n[k], *tris[k, 0], *tris[k, 1], *tris[k, 2], 0))


def write_obj(path: Path, parts):
    mtl = path.with_suffix(".mtl")
    with open(mtl, "w") as fm:
        for name, _, rgb in parts:
            fm.write(f"newmtl {name}\nKd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}\n\n")
    with open(path, "w") as fo:
        fo.write(f"mtllib {mtl.name}\n")
        base = 1
        for name, m, _ in parts:
            v, f = mesh_arrays(m)
            fo.write(f"o {name}\nusemtl {name}\n")
            for p in v:
                fo.write(f"v {p[0]:.3f} {p[1]:.3f} {p[2]:.3f}\n")
            for t in f:
                fo.write(f"f {t[0] + base} {t[1] + base} {t[2] + base}\n")
            base += len(v)


def render(parts, path: Path, title: str, elev=18, azim=-60, zoom_box=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(10, 10), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    light = np.array([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    allv = []
    for _, m, rgb in parts:
        v, f = mesh_arrays(m)
        tris = v[f]
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
        shade = 0.45 + 0.55 * np.clip(n @ light, 0, 1)
        cols = np.clip(np.outer(shade, rgb), 0, 1)
        pc = Poly3DCollection(tris, facecolors=cols, edgecolors="none", linewidths=0)
        ax.add_collection3d(pc)
        allv.append(v)
    allv = np.vstack(allv)
    lo, hi = (zoom_box if zoom_box else (allv.min(0), allv.max(0)))
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=13)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main():
    STL_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    stats = ["part, qty, volume_cm3_each, est_PETG_g_total (100% infill upper bound)"]
    total_g = 0.0
    for name, (fn, qty) in PRINTABLE.items():
        m = fn()
        assert m.status().name == "NoError", (name, m.status())
        write_stl(STL_DIR / f"{name}.stl", m, name)
        vol = m.volume() / 1000.0
        g = vol * PETG_DENSITY * qty
        total_g += g
        stats.append(f"{name}, {qty}, {vol:.1f}, {g:.0f}")
    stats.append(f"TOTAL (upper bound, 100% infill), , , {total_g:.0f}")
    (RENDER_DIR / "print_stats.txt").write_text("\n".join(stats) + "\n", encoding="utf-8")
    print("\n".join(stats))

    parts = ref_parts() + printable_in_assembly()
    write_obj(STL_DIR / "assembly.obj", parts)
    render(parts, RENDER_DIR / "assembly.png",
           "AgroAI Node v1 - assemblaggio (z=0 suolo; arancione/bianco = stampato 3D)",
           zoom_box=((-500, -450, -300), (500, 100, 1750)))
    top = POLE_LEN - POLE_IN_GROUND
    render(parts, RENDER_DIR / "assembly_top.png", "AgroAI Node v1 - box, schermo sensori, pannello",
           elev=22, azim=-35, zoom_box=((-350, -200, BOX_Z - 40), (150, 120, top + 120)))

    # printable parts laid out flat
    layout = []
    for k, (name, (fn, qty)) in enumerate(PRINTABLE.items()):
        m = fn()
        lo = np.asarray(m.bounding_box()[:3])
        hi = np.asarray(m.bounding_box()[3:])
        cx, cy = (k % 3) * 210.0, -(k // 3) * 210.0
        m = m.translate((cx - (lo[0] + hi[0]) / 2, cy - (lo[1] + hi[1]) / 2, -lo[2]))
        layout.append((name, m, (0.95, 0.55, 0.1)))
    render(layout, RENDER_DIR / "printable_parts.png", "Parti da stampare (PETG/ASA)", elev=35, azim=-70)
    print("written:", STL_DIR, RENDER_DIR)


if __name__ == "__main__":
    main()
