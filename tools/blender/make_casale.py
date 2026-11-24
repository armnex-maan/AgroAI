"""Tuscan farmhouse (casale) for the AgroAI planner, modelled procedurally in Blender.

Canonical size: 14 m across (X) x 24 m long (Y), 2 floors (eave at 6.6 m), base at the origin, Z up.
Materials are named by surface (wall, stone, roof, wood, shutter, glass); the app applies its own PBR textures by name.
UVs are in texture tiles (wall/stone 3 m, roof 2 m along the slope, wood 2.2 m), like the app's procedural buildings.
Ambient occlusion is baked with Cycles into the colour attribute (exported as COLOR_0, used as a multiplier).

usage: blender --background --factory-startup --python make_casale.py -- <out.glb> [preview.png]
"""
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
PREVIEW = argv[1] if len(argv) > 1 else None

W, L, FH, FLOORS = 14.0, 24.0, 3.3, 2
H = FH * FLOORS                     # eave height 6.6 m
OVER = 0.7                          # roof overhang
PITCH = math.radians(22)            # low Tuscan roof pitch
TILE = {"wall": 3.0, "stone": 3.0, "roof": 2.0, "wood": 2.2, "shutter": 1.0, "glass": 1.0}
MATS = ["wall", "stone", "roof", "wood", "shutter", "glass"]
COLORS = {"wall": (0.86, 0.68, 0.45), "stone": (0.62, 0.56, 0.47), "roof": (0.62, 0.28, 0.16), "wood": (0.33, 0.22, 0.13),
          "shutter": (0.12, 0.24, 0.13), "glass": (0.03, 0.04, 0.05)}

bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
MI = {m: i for i, m in enumerate(MATS)}


def add_box(size, loc, mat, rot_z=0.0):
    sx, sy, sz = size
    g = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(loc) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Diagonal((sx, sy, sz, 1)))
    for f in {f for v in g["verts"] for f in v.link_faces}:
        f.material_index = MI[mat]


def add_poly(pts, mat):
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    f.material_index = MI[mat]
    return f


def add_cyl(a, b, r, mat, seg=8):
    a, b = Vector(a), Vector(b)
    d = b - a
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    g = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length,
                              matrix=Matrix.Translation((a + b) / 2) @ rot)
    for f in {f for v in g["verts"] for f in v.link_faces}:
        f.material_index = MI[mat]


def hip_roof(cx, cy, w, l, z0, over, pitch, mat="roof", fascia=0.16):
    """Hip roof over a w x l rectangle (ridge along Y), eave at z0; returns the ridge height."""
    hw, hl = w / 2 + over, l / 2 + over
    rise = hw * math.tan(pitch)
    rl = max(0.01, hl - hw)
    A, B, C, D = (cx - hw, cy - hl, z0), (cx + hw, cy - hl, z0), (cx + hw, cy + hl, z0), (cx - hw, cy + hl, z0)
    P, Q = (cx, cy - rl, z0 + rise), (cx, cy + rl, z0 + rise)
    add_poly([A, B, P], mat); add_poly([C, D, Q], mat)
    add_poly([B, C, Q, P], mat); add_poly([D, A, P, Q], mat)
    # fascia boards and soffit
    lo = z0 - fascia
    for p, q in ((A, B), (B, C), (C, D), (D, A)):
        add_poly([(p[0], p[1], lo), (q[0], q[1], lo), q, p], "wood")
    add_poly([(A[0], A[1], lo), (D[0], D[1], lo), (C[0], C[1], lo), (B[0], B[1], lo)], "wood")
    # ridge and hip caps (coppi)
    for p, q in ((P, Q), (A, P), (B, P), (C, Q), (D, Q)):
        add_cyl((p[0], p[1], p[2] + 0.06), (q[0], q[1], q[2] + 0.06), 0.13, mat, 8)
    return z0 + rise


def window(side, along, z, w=1.0, h=1.45, door=False):
    """Window (or door) on a long wall (side = -1 west / +1 east, at x = side * W/2) centred at y = along, sill at z."""
    x = side * W / 2
    n = side
    add_box((0.02, w, h), (x + n * 0.012, along, z + h / 2), "glass" if not door else "wood")
    fr = 0.13
    add_box((0.06, w + 2 * fr, fr), (x + n * 0.03, along, z + h + fr / 2), "stone")          # lintel
    add_box((0.14, w + 2 * fr + 0.1, 0.09), (x + n * 0.07, along, z - 0.045), "stone")         # sill
    for s in (-1, 1):
        add_box((0.06, fr, h), (x + n * 0.03, along + s * (w / 2 + fr / 2), z + h / 2), "stone")  # jambs
        if not door:                                                                          # open shutters (persiane)
            add_box((0.05, w / 2, h * 1.02), (x + n * 0.05, along + s * (w / 2 + fr + w / 4 + 0.02), z + h / 2), "shutter")


def window_end(side, along, z, w=1.0, h=1.45):
    """Window on a short wall (side = -1 south / +1 north, at y = side * L/2) centred at x = along."""
    y = side * L / 2
    n = side
    fr = 0.13
    add_box((w, 0.02, h), (along, y + n * 0.012, z + h / 2), "glass")
    add_box((w + 2 * fr, 0.06, fr), (along, y + n * 0.03, z + h + fr / 2), "stone")
    add_box((w + 2 * fr + 0.1, 0.14, 0.09), (along, y + n * 0.07, z - 0.045), "stone")
    for s in (-1, 1):
        add_box((fr, 0.06, h), (along + s * (w / 2 + fr / 2), y + n * 0.03, z + h / 2), "stone")
        add_box((w / 2, 0.05, h * 1.02), (along + s * (w / 2 + fr + w / 4 + 0.02), y + n * 0.05, z + h / 2), "shutter")


# ---- body
add_box((W, L, H), (0, 0, H / 2), "wall")
add_box((W + 0.12, L + 0.12, 0.85), (0, 0, 0.425), "stone")                                   # plinth
add_box((W + 0.1, L + 0.1, 0.16), (0, 0, FH), "stone")                                       # string course
add_box((W + 0.3, L + 0.3, 0.28), (0, 0, H - 0.14), "stone")                                  # eave cornice
for sx in (-1, 1):                                                                            # corner quoins
    for sy in (-1, 1):
        for k in range(int(H / 0.32)):
            long_y = k % 2 == 0
            dx, dy = (0.35, 0.6) if long_y else (0.6, 0.35)
            add_box((dx, dy, 0.3), (sx * (W / 2 - dx / 2 + 0.03), sy * (L / 2 - dy / 2 + 0.03), 0.16 + k * 0.32), "stone")

# ---- windows and doors
bays = [-9.6, -6.4, -3.2, 0.0, 3.2, 6.4, 9.6]
for side in (-1, 1):
    for i, y in enumerate(bays):
        if side == 1 and y == 0.0:
            window(side, y, 0.05, w=1.7, h=2.6, door=True)                                    # main door
        else:
            window(side, y, 1.0, h=1.4)
        window(side, y, FH + 0.9)
for side in (-1, 1):
    for x in (-4.0, 0.0, 4.0):
        window_end(side, x, 1.0, h=1.4)
        window_end(side, x, FH + 0.9)

# ---- roof, dovecote tower, chimneys
ridge = hip_roof(0, 0, W, L, H, OVER, PITCH)
tx, ty, ts = 0.0, 5.0, 3.6
add_box((ts, ts, ridge + 2.2 - (H + 1.0)), (tx, ty, (ridge + 2.2 + H + 1.0) / 2), "wall")    # colombaia
for k, (dx, dy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
    for o in (-0.7, 0.7):
        px, py = tx + dx * (ts / 2 + 0.012) + (0 if dx else o), ty + dy * (ts / 2 + 0.012) + (0 if dy else o)
        add_box((0.02 if dx else 0.45, 0.45 if dx else 0.02, 0.75), (px, py, ridge + 1.3), "glass")
add_box((ts + 0.2, ts + 0.2, 0.14), (tx, ty, ridge + 2.2 - 0.07), "stone")
hip_roof(tx, ty, ts, ts, ridge + 2.2, 0.45, math.radians(24))
for cy in (-7.5, -1.5):
    add_box((0.8, 0.95, 3.0), (2.2, cy, ridge - 0.6), "stone")
    add_box((1.15, 1.3, 0.12), (2.2, cy, ridge + 1.05), "roof")
    for s in (-1, 1):
        add_box((0.12, 0.12, 0.35), (2.2 + s * 0.45, cy, ridge + 0.85), "stone")

# ---- portico in front of the main door (east side)
px0 = W / 2
add_box((3.4, 7.0, 0.16), (px0 + 1.7, 0, 0.08), "stone")
for y in (-3.1, 0.0, 3.1):
    add_box((0.48, 0.48, 3.0), (px0 + 3.1, y, 1.5 + 0.16), "stone")
add_box((0.3, 7.2, 0.32), (px0 + 3.1, 0, 3.3), "wood")
z_hi, z_lo, x_out = 4.25, 3.35, px0 + 3.7
add_poly([(px0, -3.7, z_hi), (px0, 3.7, z_hi), (x_out, 3.7, z_lo), (x_out, -3.7, z_lo)], "roof")
add_poly([(px0, 3.7, z_hi - 0.12), (px0, -3.7, z_hi - 0.12), (x_out, -3.7, z_lo - 0.12), (x_out, 3.7, z_lo - 0.12)], "wood")
for y in (-3.7, 3.7):
    add_poly([(px0, y, z_hi), (x_out, y, z_lo), (x_out, y, z_lo - 0.12), (px0, y, z_hi - 0.12)], "wood")

# ---- clean up, density for the AO bake, UVs in tiles
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.normal_update()
long_edges = [e for e in bm.edges if e.calc_length() > 0.7]
for _ in range(4):
    long_edges = [e for e in bm.edges if e.calc_length() > 0.7]
    if not long_edges:
        break
    bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
uv = bm.loops.layers.uv.new("UVMap")
for f in bm.faces:
    mat = MATS[f.material_index]
    t = TILE[mat]
    n = f.normal
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    for loop in f.loops:
        co = loop.vert.co
        if mat == "roof" and 0.05 < az < 0.985:
            hl = math.hypot(n.x, n.y); hx, hy = n.x / hl, n.y / hl
            u, v = -co.x * hy + co.y * hx, (co.x * hx + co.y * hy) / az
        elif az >= ax and az >= ay:
            u, v = co.x, co.y
        elif ax >= ay:
            u, v = co.y, co.z
        else:
            u, v = co.x, co.z
        loop[uv].uv = (u / t, v / t)
for f in bm.faces:
    f.smooth = False
me = bpy.data.meshes.new("casale")
bm.to_mesh(me); bm.free()
for m in MATS:
    mat = bpy.data.materials.new(m)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*COLORS[m], 1)
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.2 if m == "glass" else 0.85
    me.materials.append(mat)
ob = bpy.data.objects.new("casale", me)
scene = bpy.context.scene
scene.collection.objects.link(ob)
print("CASALE faces", len(me.polygons), "verts", len(me.vertices))

# ---- ambient occlusion baked into the colour attribute (ground plane included in the occluders)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
ground = bpy.context.object
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"; prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.device = "GPU"
scene.cycles.samples = 256
world = bpy.data.worlds.new("w"); scene.world = world
attr = me.color_attributes.new("AO", "FLOAT_COLOR", "POINT")
me.color_attributes.active_color = attr
me.attributes.render_color_index = me.color_attributes.find("AO")
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
scene.render.bake.target = "VERTEX_COLORS"
scene.world.light_settings.distance = 4.0
bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
# soften: AO 0.35..1 so the walls never go black
col = attr.data
for c in col:
    k = 0.35 + 0.65 * c.color[0]
    c.color = (k, k, k, 1.0)
print("AO baked")

if PREVIEW:
    gm = bpy.data.materials.new("grass"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.25, 0.06, 1)
    ground.data.materials.append(gm)
    for m in me.materials:     # show the baked AO in the preview
        nt = m.node_tree
        a = nt.nodes.new("ShaderNodeVertexColor"); a.layer_name = "AO"
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1
        mix.inputs[6].default_value = nt.nodes["Principled BSDF"].inputs["Base Color"].default_value
        nt.links.new(a.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], nt.nodes["Principled BSDF"].inputs["Base Color"])
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.75, 1.0, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 4; so = bpy.data.objects.new("sun", sun); scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), 0, math.radians(-35))
    cam = bpy.data.cameras.new("c"); co = bpy.data.objects.new("c", cam); scene.collection.objects.link(co); scene.camera = co
    co.location = (34, -30, 24); co.rotation_euler = (math.radians(62), 0, math.radians(48)); cam.lens = 35
    scene.render.resolution_x, scene.render.resolution_y = 1200, 700
    scene.cycles.samples = 64
    scene.view_settings.view_transform = "AgX"
    scene.render.filepath = PREVIEW
    bpy.ops.render.render(write_still=True)

bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
kw = dict(filepath=OUT, export_format="GLB", use_selection=True, export_apply=True, export_normals=True,
          export_texcoords=True, export_yup=True)
try:
    bpy.ops.export_scene.gltf(**kw, export_vertex_color="ACTIVE")
except TypeError:
    bpy.ops.export_scene.gltf(**kw, export_colors=True)
print("EXPORTED", OUT)
