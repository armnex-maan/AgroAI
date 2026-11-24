"""Procedural crop plants for AgroAI (Blender, Cycles materials). Each crop becomes ONE object named "crop" in
<out_dir>/<name>.blend, base at the origin, real size in metres (Z up). Variants without fruit end in "_green".

usage: blender --background --factory-startup --python make_crops.py -- <out_dir> [preview.png]
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
PREVIEW = argv[1] if len(argv) > 1 else None
os.makedirs(OUT, exist_ok=True)


# ------------------------------------------------------------------------------------------------ materials
def hexc(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a]


def leaf_material(name, base, tip, vein, rough=0.45, sss=0.12, vein_amt=0.55, bump=0.35, spots=None, vein_scale=9.0):
    """Leaf: colour from base to tip along U, light midrib and side veins from the UVs, fine bump, translucency."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = min(0.85, rough + 0.15)
    bsdf.inputs["Specular IOR Level"].default_value = 0.22
    bsdf.inputs["Subsurface Weight"].default_value = sss
    bsdf.inputs["Subsurface Radius"].default_value = (0.02, 0.05, 0.01)
    uv = N.new("ShaderNodeUVMap")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(uv.outputs[0], sep.inputs[0])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = hexc(base); ramp.color_ramp.elements[1].color = hexc(tip)
    L.new(sep.outputs[0], ramp.inputs[0])
    # midrib: |v - 0.5| small
    sub = N.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = 0.5
    L.new(sep.outputs[1], sub.inputs[0])
    ab = N.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"; L.new(sub.outputs[0], ab.inputs[0])
    mid = N.new("ShaderNodeMapRange"); mid.inputs[1].default_value = 0.0; mid.inputs[2].default_value = 0.035
    mid.inputs[3].default_value = 1.0; mid.inputs[4].default_value = 0.0
    L.new(ab.outputs[0], mid.inputs[0])
    # side veins: stripes along (u + |v-0.5| * 0.9)
    add = N.new("ShaderNodeMath"); add.operation = "MULTIPLY_ADD"; add.inputs[1].default_value = 0.9
    L.new(ab.outputs[0], add.inputs[0]); L.new(sep.outputs[0], add.inputs[2])
    wave = N.new("ShaderNodeTexWave"); wave.wave_type = "BANDS"; wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = vein_scale; wave.inputs["Distortion"].default_value = 1.5; wave.inputs["Detail"].default_value = 1.0
    comb = N.new("ShaderNodeCombineXYZ"); L.new(add.outputs[0], comb.inputs[0])
    L.new(comb.outputs[0], wave.inputs["Vector"])
    sharp = N.new("ShaderNodeMapRange"); sharp.inputs[1].default_value = 0.9; sharp.inputs[2].default_value = 1.0
    L.new(wave.outputs["Fac"], sharp.inputs[0])
    veins = N.new("ShaderNodeMath"); veins.operation = "MAXIMUM"
    L.new(mid.outputs[0], veins.inputs[0]); L.new(sharp.outputs[0], veins.inputs[1])
    vfac = N.new("ShaderNodeMath"); vfac.operation = "MULTIPLY"; vfac.inputs[1].default_value = vein_amt
    L.new(veins.outputs[0], vfac.inputs[0])
    mixv = N.new("ShaderNodeMix"); mixv.data_type = "RGBA"
    L.new(vfac.outputs[0], mixv.inputs["Factor"]); L.new(ramp.outputs[0], mixv.inputs[6])
    mixv.inputs[7].default_value = hexc(vein)
    # mottling
    noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 60; noise.inputs["Detail"].default_value = 6
    mott = N.new("ShaderNodeMix"); mott.data_type = "RGBA"; mott.blend_type = "OVERLAY"; mott.inputs["Factor"].default_value = 0.25
    L.new(mixv.outputs[2], mott.inputs[6]); L.new(noise.outputs["Color"], mott.inputs[7])
    col = mott.outputs[2]
    if spots:
        vor = N.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 90
        sp = N.new("ShaderNodeMapRange"); sp.inputs[1].default_value = 0.0; sp.inputs[2].default_value = 0.08
        sp.inputs[3].default_value = spots[1]; sp.inputs[4].default_value = 0.0
        L.new(vor.outputs["Distance"], sp.inputs[0])
        mixs = N.new("ShaderNodeMix"); mixs.data_type = "RGBA"
        L.new(sp.outputs[0], mixs.inputs["Factor"]); L.new(col, mixs.inputs[6]); mixs.inputs[7].default_value = hexc(spots[0])
        col = mixs.outputs[2]
    L.new(col, bsdf.inputs["Base Color"])
    # bump: veins + fine noise
    bmp = N.new("ShaderNodeBump"); bmp.inputs["Strength"].default_value = bump; bmp.inputs["Distance"].default_value = 0.002
    bsum = N.new("ShaderNodeMath"); bsum.operation = "MULTIPLY_ADD"; bsum.inputs[1].default_value = 0.4
    L.new(noise.outputs["Fac"], bsum.inputs[0]); L.new(veins.outputs[0], bsum.inputs[2])
    L.new(bsum.outputs[0], bmp.inputs["Height"])
    L.new(bmp.outputs[0], bsdf.inputs["Normal"])
    # translucency: light through the leaf
    tr = N.new("ShaderNodeBsdfTranslucent"); L.new(col, tr.inputs["Color"])
    mx = N.new("ShaderNodeMixShader"); mx.inputs["Fac"].default_value = 0.12
    L.new(bsdf.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])
    return m


def simple_material(name, color, rough=0.5, coat=0.0, sss=0.0, noise_amt=0.15, noise_scale=30, bump=0.1):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Subsurface Weight"].default_value = sss
    noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = noise_scale; noise.inputs["Detail"].default_value = 4
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "OVERLAY"; mix.inputs["Factor"].default_value = noise_amt
    mix.inputs[6].default_value = hexc(color); L.new(noise.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    bm = N.new("ShaderNodeBump"); bm.inputs["Strength"].default_value = bump; bm.inputs["Distance"].default_value = 0.002
    L.new(noise.outputs["Fac"], bm.inputs["Height"]); L.new(bm.outputs[0], b.inputs["Normal"])
    return m


# ------------------------------------------------------------------------------------------------ geometry
class Builder:
    """Collects triangles per material, then one object."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.mats = []

    def mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def grid(self, pts, uvs, nu, nv, mi):
        """pts/uvs: (nu+1)*(nv+1) lists, row-major by u."""
        vs = [self.bm.verts.new(p) for p in pts]
        for i in range(nu):
            for j in range(nv):
                a, b, c, d = i * (nv + 1) + j, (i + 1) * (nv + 1) + j, (i + 1) * (nv + 1) + j + 1, i * (nv + 1) + j + 1
                try:
                    f = self.bm.faces.new((vs[a], vs[b], vs[c], vs[d]))
                except ValueError:
                    continue
                f.material_index = mi
                f.smooth = True
                for loop, k in zip(f.loops, (a, b, c, d)):
                    loop[self.uv].uv = uvs[k]

    def add_mesh(self, me, matrix, mi):
        tmp = bmesh.new(); tmp.from_mesh(me); tmp.transform(matrix)
        uvl = tmp.loops.layers.uv.active
        vmap = {v: self.bm.verts.new(v.co) for v in tmp.verts}
        for f in tmp.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = mi; nf.smooth = True
            if uvl:
                for l0, l1 in zip(f.loops, nf.loops):
                    l1[self.uv].uv = l0[uvl].uv
        tmp.free()

    def build(self, name):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me); self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def leaf(B, mi, M, L, W, nu=12, nv=6, cup=0.25, droop=0.3, ruffle=0.0, ruffle_freq=9, twist=0.0, profile=0.75, tip=0.0,
         serr=0.0, lobes=0.0, seed=0, shape=1.0):
    """A leaf in its own frame (u along +X from the stem at the origin, v across Y, Z up), then transformed by M."""
    r = random.Random(seed)
    ph = r.random() * 6.28
    pts, uvs = [], []
    for i in range(nu + 1):
        t = i / nu
        tt = t ** shape                       # shape < 1: widest near the tip (obovate), > 1: near the base
        w = W * (max(0.0, math.sin(math.pi * tt)) ** profile) * (1 + lobes * math.sin(t * math.pi * 5) ** 2 * 0.3)
        w = max(w, W * 0.02)
        for j in range(nv + 1):
            s = j / nv * 2 - 1
            x = t * L
            y = s * w / 2
            z = cup * W * (s * s) - droop * L * t * t
            edge = abs(s) ** 2.5
            z += ruffle * W * edge * math.sin(t * ruffle_freq * 6.283 + ph + s * 2)
            y += serr * W * edge * math.sin(t * 40 + ph) * 0.08
            a = twist * t
            y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
            pts.append(M @ Vector((x, y, z)))
            uvs.append((t, j / nv))
    B.grid(pts, uvs, nu, nv, mi)


def sphere_mesh(r=1.0, seg=16, ring=10):
    me = bpy.data.meshes.new("s")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=r, calc_uvs=True)
    bm.to_mesh(me); bm.free()
    return me


def cyl_mesh(r1, r2, h, seg=8):
    me = bpy.data.meshes.new("c")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=r1, radius2=r2, depth=h, calc_uvs=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h / 2))
    bm.to_mesh(me); bm.free()
    return me


def orient(origin, yaw, pitch, roll=0.0):
    return Matrix.Translation(origin) @ Euler((roll, -pitch, yaw), "XYZ").to_matrix().to_4x4()


def tube(B, mi, pts, r0, r1, seg=6):
    """Stem along a polyline."""
    for k in range(len(pts) - 1):
        a, b = Vector(pts[k]), Vector(pts[k + 1])
        d = b - a
        h = d.length
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        rr0 = r0 + (r1 - r0) * k / (len(pts) - 1); rr1 = r0 + (r1 - r0) * (k + 1) / (len(pts) - 1)
        B.add_mesh(cyl_mesh(rr0, rr1, h, seg), Matrix.Translation(a) @ rot, mi)


# ------------------------------------------------------------------------------------------------ crops
GOLD = 2.39996


def lettuce(seed=1):
    r = random.Random(seed)
    B = Builder()
    m_out = B.mat(leaf_material("lettuce_leaves", "#d6ec98", "#5fb236", "#eef8cf", rough=0.5, vein_amt=0.18, bump=0.55, vein_scale=11))
    m_in = B.mat(leaf_material("lettuce_heart_leaves", "#f1f8c0", "#a3d65a", "#f8fce2", rough=0.45, vein_amt=0.15, bump=0.5, vein_scale=11))
    n = 36
    for k in range(n):
        f = k / n                        # 0 outer .. 1 inner
        yaw = k * GOLD + r.uniform(-0.12, 0.12)
        L = 0.19 * (1 - f * 0.55) * r.uniform(0.92, 1.08)
        W = L * r.uniform(0.95, 1.15)
        pitch = math.radians(14 + f * 58 + r.uniform(-5, 5))     # outer leaves spread, inner upright
        o = Vector((math.cos(yaw), math.sin(yaw), 0)) * 0.01 * (1 - f) + Vector((0, 0, 0.01 + f * 0.025))
        leaf(B, m_in if f > 0.6 else m_out, orient(o, yaw, pitch), L, W, nu=22, nv=14, cup=0.1 + f * 0.22,
             droop=0.18 * (1 - f) - 0.12 * f, ruffle=0.07 + 0.04 * (1 - f), ruffle_freq=8, profile=0.45, shape=1.6, seed=seed * 100 + k)
    return B.build("crop")


def cabbage(seed=2):
    r = random.Random(seed)
    B = Builder()
    m_leaf = B.mat(leaf_material("cabbage_leaves", "#8fb48a", "#3f7357", "#b9d3b4", rough=0.32, sss=0.08, vein_amt=0.3, bump=0.35, vein_scale=7))
    m_wrap = B.mat(leaf_material("cabbage_wrap_leaves", "#b7d39a", "#6c9f6a", "#d6e7c4", rough=0.3, sss=0.1, vein_amt=0.25, bump=0.3, vein_scale=7))
    m_head = B.mat(simple_material("cabbage_head", "#a9c98a", rough=0.3, sss=0.1, noise_amt=0.25, noise_scale=14, bump=0.25))
    B.add_mesh(sphere_mesh(1, 24, 16), Matrix.Translation((0, 0, 0.11)) @ Matrix.Diagonal((0.105, 0.105, 0.095, 1)), m_head)
    for k in range(7):                   # leaves wrapping the head
        yaw = k * GOLD
        leaf(B, m_wrap, orient(Vector((0, 0, 0.025)), yaw, math.radians(r.uniform(58, 70))), 0.2, 0.2, nu=18, nv=14,
             cup=0.38, droop=-0.22, ruffle=0.015, profile=0.4, shape=1.5, seed=seed * 50 + k)
    for k in range(11):                  # outer leaves, wide, cupped, bluish
        yaw = k * GOLD + r.uniform(-0.2, 0.2)
        L = 0.28 * r.uniform(0.9, 1.1); W = L * 1.0
        leaf(B, m_leaf, orient(Vector((0, 0, 0.015)), yaw, math.radians(r.uniform(12, 30))), L, W, nu=20, nv=14,
             cup=0.14, droop=0.16, ruffle=0.035, ruffle_freq=4, profile=0.4, shape=1.6, seed=seed * 70 + k)
    return B.build("crop")


def tomato(seed=3, fruit=True):
    r = random.Random(seed)
    B = Builder()
    m_leaf = B.mat(leaf_material("tomato_leaves", "#5f9a3a", "#3c7426", "#7fb055", rough=0.55, vein_amt=0.15, bump=0.6, vein_scale=12))
    m_stem = B.mat(simple_material("tomato_stem", "#5d8a3a", rough=0.7))
    m_stake = B.mat(simple_material("stake", "#9b7a52", rough=0.85, noise_amt=0.35, noise_scale=80))
    H = 1.0
    tube(B, m_stake, [(0.03, 0.02, -0.02), (0.03, 0.02, H * 1.08)], 0.011, 0.009, 6)
    stem = [(r.uniform(-0.01, 0.01), r.uniform(-0.01, 0.01), z) for z in [0, 0.25, 0.5, 0.75, H * 0.95]]
    tube(B, m_stem, stem, 0.011, 0.005)
    # compound leaves: rachis with leaflets
    n = 40
    for k in range(n):
        z = 0.06 + (H * 0.88) * k / n
        yaw = k * GOLD
        length = 0.34 * (1 - 0.4 * k / n) * r.uniform(0.85, 1.12)
        pitch = math.radians(r.uniform(15, 40))
        base = Vector((0, 0, z))
        dirv = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)))
        tip = base + dirv * length + Vector((0, 0, -0.06))
        tube(B, m_stem, [base, (base + tip) / 2 + Vector((0, 0, 0.02)), tip], 0.004, 0.002, 5)
        for j in range(7):
            t = (j + 1) / 8
            p = base.lerp(tip, t) + Vector((0, 0, 0.02 * math.sin(t * 3.14)))
            for side in (-1, 1):
                if j == 6 and side == 1:
                    continue
                ly = yaw + side * math.radians(r.uniform(55, 80)) if j < 6 else yaw
                ll = 0.1 * (1 - 0.3 * abs(t - 0.5)) * r.uniform(0.8, 1.15)
                leaf(B, m_leaf, orient(p, ly, math.radians(r.uniform(-20, 10)), r.uniform(-0.4, 0.4)), ll, ll * 0.55, nu=7, nv=4,
                     cup=0.12, droop=0.2, ruffle=0.08, ruffle_freq=4, serr=0.6, profile=0.7, seed=seed * 1000 + k * 20 + j * 2 + side)
    if fruit:
        m_red = B.mat(simple_material("tomato_fruit", "#c8231a", rough=0.18, coat=0.4, sss=0.05, noise_amt=0.08))
        m_orange = B.mat(simple_material("tomato_fruit_ripening", "#e0661e", rough=0.2, coat=0.4, noise_amt=0.1))
        m_green = B.mat(simple_material("tomato_fruit_green", "#7fae3e", rough=0.25, coat=0.3, noise_amt=0.1))
        m_sepal = B.mat(simple_material("tomato_sepal", "#3f7a28", rough=0.6))
        for k in range(16):
            z = 0.18 + 0.72 * k / 16
            yaw = k * GOLD + r.uniform(-0.3, 0.3)
            d = r.uniform(0.15, 0.21)
            c = Vector((math.cos(yaw) * d, math.sin(yaw) * d, z))
            for j in range(r.randint(3, 6)):
                p = c + Vector((r.uniform(-0.045, 0.045), r.uniform(-0.045, 0.045), r.uniform(-0.06, 0.0)))
                rad = r.uniform(0.032, 0.044)
                mi = m_red if (k < 6 or r.random() < 0.4) and r.random() < 0.85 else (m_orange if r.random() < 0.5 else m_green)
                B.add_mesh(sphere_mesh(1, 14, 9), Matrix.Translation(p) @ Matrix.Diagonal((rad, rad, rad * 0.86, 1)), mi)
                for q in range(5):
                    a = q * 1.2566
                    leaf(B, m_sepal, orient(p + Vector((0, 0, rad * 0.8)), a, math.radians(-25)), rad * 0.9, rad * 0.35, nu=3, nv=2, cup=0.1, droop=0.3)
    return B.build("crop")


def eggplant(seed=4, fruit=True):
    r = random.Random(seed)
    B = Builder()
    m_leaf = B.mat(leaf_material("eggplant_leaves", "#5b8a45", "#3a6430", "#6f6a5a", rough=0.6, vein_amt=0.2, bump=0.55, vein_scale=10))
    m_stem = B.mat(simple_material("eggplant_stem", "#4d4a3a", rough=0.7))
    H = 0.75
    stem = [(0, 0, 0), (0.01, 0, 0.3), (-0.01, 0.01, 0.6), (0, 0, H)]
    tube(B, m_stem, stem, 0.014, 0.006)
    for k in range(26):
        z = 0.12 + (H * 0.82) * k / 26
        yaw = k * GOLD
        L = 0.2 * (1 - 0.35 * k / 26) * r.uniform(0.85, 1.15)
        base = Vector((0, 0, z))
        pet = base + Vector((math.cos(yaw), math.sin(yaw), 0.25)) * 0.07
        tube(B, m_stem, [base, pet], 0.004, 0.003, 5)
        leaf(B, m_leaf, orient(pet, yaw, math.radians(r.uniform(5, 30)), r.uniform(-0.3, 0.3)), L, L * 0.62, nu=12, nv=8,
             cup=0.1, droop=0.3, ruffle=0.05, ruffle_freq=3, lobes=0.8, profile=0.65, tip=0.1, seed=seed * 300 + k)
    if fruit:
        m_fruit = B.mat(simple_material("eggplant_fruit", "#2b0f35", rough=0.12, coat=0.7, noise_amt=0.06))
        m_cal = B.mat(simple_material("eggplant_calyx", "#4f7a36", rough=0.6))
        for k in range(4):
            yaw = k * 1.7 + 0.4
            top = Vector((math.cos(yaw) * 0.12, math.sin(yaw) * 0.12, 0.32 + 0.1 * (k % 2)))
            me = sphere_mesh(1, 16, 12)
            for v in me.vertices:                         # teardrop: thin at the stalk, wide at the bottom
                t = (v.co.z + 1) / 2
                k2 = 0.55 + 0.45 * (1 - t) ** 0.7
                v.co.x *= k2; v.co.y *= k2
            L = r.uniform(0.15, 0.2)
            M = Matrix.Translation(top + Vector((0, 0, -L * 0.55))) @ Euler((r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), 0)).to_matrix().to_4x4() \
                @ Matrix.Diagonal((0.04, 0.04, L * 0.55, 1))
            B.add_mesh(me, M, m_fruit)
            for q in range(5):
                leaf(B, m_cal, orient(top + Vector((0, 0, -0.012)), q * 1.2566, math.radians(-60)), 0.035, 0.022, nu=3, nv=2, cup=0.1, droop=0.1)
    return B.build("crop")


ZSCALE = {"lettuce": 1.7, "cabbage": 1.45}   # heads taller and rounder (real lettuce ~0.3 x 0.25 m, cabbage ~0.5 x 0.35 m)


def save(name, build):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ob = build()
    ob.name = "crop"
    if name in ZSCALE:
        ob.data.transform(Matrix.Diagonal((1, 1, ZSCALE[name], 1)))
        ob.data.update()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{name}.blend"))
    dims = tuple(round(v, 3) for v in ob.dimensions)
    print("CROP", name, len(ob.data.polygons), dims)


CROPS = {
    "lettuce": lambda: lettuce(1),
    "cabbage": lambda: cabbage(2),
    "tomato": lambda: tomato(3, True), "tomato_green": lambda: tomato(3, False),
    "eggplant": lambda: eggplant(4, True), "eggplant_green": lambda: eggplant(4, False),
}
only = os.environ.get("CROPS")
for n, f in CROPS.items():
    if only and n not in only.split(","):
        continue
    save(n, f)

if PREVIEW:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    x = 0.0
    for n in ["lettuce", "cabbage", "tomato", "eggplant"]:
        with bpy.data.libraries.load(os.path.join(OUT, f"{n}.blend")) as (src, dst):
            dst.objects = ["crop"]
        for o in dst.objects:
            scene.collection.objects.link(o); o.location.x = x
        x += 0.75
    scene.render.engine = "CYCLES"
    p = bpy.context.preferences.addons["cycles"].preferences
    p.compute_device_type = "OPTIX"; p.get_devices()
    for d in p.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"; scene.cycles.samples = 96
    scene.render.resolution_x, scene.render.resolution_y = 1400, 640
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("w"); scene.world = world; world.use_nodes = True
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    world.node_tree.links.new(sky.outputs[0], world.node_tree.nodes["Background"].inputs[0])
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 4.5; sun.angle = math.radians(2)
    so = bpy.data.objects.new("sun", sun); scene.collection.objects.link(so); so.rotation_euler = (math.radians(45), 0, math.radians(35))
    bpy.ops.mesh.primitive_plane_add(size=20, location=(x / 2, 0, 0))
    pl = bpy.context.object; sm = simple_material("soil", "#6b4f35", rough=0.95, noise_amt=0.4, noise_scale=40, bump=0.5); pl.data.materials.append(sm)
    cam = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c", cam); scene.collection.objects.link(co); scene.camera = co
    co.location = (x / 2 - 0.37, -2.6, 1.9); co.rotation_euler = (math.radians(55), 0, 0); cam.lens = 32
    scene.render.filepath = PREVIEW
    bpy.ops.render.render(write_still=True)
