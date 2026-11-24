"""Distant Tuscan landscape around the farm, rendered by Cycles as an equirectangular band (sky transparent).

The app draws this band far away around the camera (engine/Horizon.tsx): hills, field patchwork, woods, cypresses and
farmhouses beyond the 3D terrain, at no runtime cost. Demonstrative scenery, never data.

Blender frame: X east, Y north, Z up; farm centre at the origin; eye at EYE metres.
usage: blender --background --factory-startup --python make_horizon.py -- <out.png> <width> [calib]
"""
import math
import random
import sys

import bpy
import numpy as np
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, WIDTH = argv[0], int(argv[1])
CALIB = len(argv) > 2 and argv[2] == "calib"
EYE = 200.0                         # above the usual planner camera: the band also fits higher, zoomed-out views
LAT_MIN, LAT_MAX = math.radians(-24), math.radians(8)
R0, R1 = 120.0, 26000.0
HAZE = (0.65, 0.745, 0.82)          # linear of the app's haze colour #d3e0ea
SKY_ROT = -1.75                     # app: SKY_ROTATION
import os  # noqa: E402
HDRI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "public", "planner",
                    "kloofendal_48d_partly_cloudy_puresky_2k.hdr")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rnd = random.Random(11)


def fbm(x, y, octaves=5, seed=0.0):
    s, a, f, n = 0.0, 0.5, 1.0, 0.0
    for _ in range(octaves):
        s += a * noise.noise(Vector((x * f + seed, y * f - seed, 0.37 * seed)), noise_basis="PERLIN_NEW")
        n += a; a *= 0.5; f *= 2.03
    return s / n


def smooth(a, b, t):
    t = min(1.0, max(0.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def height(x, y):
    r = math.hypot(x, y)
    near = smooth(1300, 3600, r)                                                # flat-ish where the 3D terrain is
    plain = fbm(x / 900, y / 900, 3, 0.7) * 18 * smooth(200, 1500, r)
    roll = (fbm(x / 2600, y / 2600, 5, 3.1) * 0.5 + 0.5) ** 1.35 * 520         # rolling hills
    big = max(0.0, fbm(x / 8000, y / 8000, 4, 7.7) + 0.15) ** 1.1 * 1100 * smooth(4000, 14000, r)   # far ridges
    det = fbm(x / 500, y / 500, 3, 1.9) * 14
    return plain + near * (roll + big + det) - r * r / (2 * 6371000.0)


def forest(x, y):
    n = fbm(x / 2000, y / 2000, 4, 5.3) + 0.12 * smooth(1500, 6000, math.hypot(x, y))   # more woods on the hills
    return smooth(-0.02, 0.14, n)


def lin(hexs):
    h = hexs.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def hazed(mat, shader_out, strength=1.0):
    """Aerial perspective: mix toward the haze colour with view distance (same colour as the app's fog)."""
    nt = mat.node_tree; N = nt.nodes; L = nt.links
    out = N["Material Output"]
    cam = N.new("ShaderNodeCameraData")
    m1 = N.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; m1.inputs[1].default_value = -1 / 9000.0
    L.new(cam.outputs["View Distance"], m1.inputs[0])
    ex = N.new("ShaderNodeMath"); ex.operation = "EXPONENT"; L.new(m1.outputs[0], ex.inputs[0])
    inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0; L.new(ex.outputs[0], inv.inputs[1])
    k = N.new("ShaderNodeMath"); k.operation = "MULTIPLY"; k.inputs[1].default_value = 0.92 * strength; L.new(inv.outputs[0], k.inputs[0])
    em = N.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*HAZE, 1); em.inputs["Strength"].default_value = 1.0
    mx = N.new("ShaderNodeMixShader")
    L.new(k.outputs[0], mx.inputs["Fac"]); L.new(shader_out, mx.inputs[1]); L.new(em.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs["Surface"])


def principled(name, color, rough=0.9, var=0.0, per_instance=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.2
    if per_instance:
        oi = N.new("ShaderNodeObjectInfo")
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*[c * (1 - var) for c in color], 1)
        ramp.color_ramp.elements[1].color = (*[min(1, c * (1 + var)) for c in color], 1)
        L.new(oi.outputs["Random"], ramp.inputs[0]); L.new(ramp.outputs[0], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (*color, 1)
    hazed(m, b.outputs[0])
    return m


# ------------------------------------------------------------------------------ terrain (radial mesh)
NR, NA = (60, 256) if CALIB else (240, 1536)
rs = [R0 * (R1 / R0) ** (i / (NR - 1)) for i in range(NR)]
verts, faces, fw, dens = [], [], [], []
for i, r in enumerate(rs):
    for j in range(NA):
        a = 2 * math.pi * j / NA
        x, y = r * math.cos(a), r * math.sin(a)
        verts.append((x, y, height(x, y)))
        f = forest(x, y)
        fw.append(f)
        dens.append(f * (1.0 if r < 6000 else 0.35 if r < 12000 else 0.06))
for i in range(NR - 1):
    for j in range(NA):
        a, b = i * NA + j, i * NA + (j + 1) % NA
        faces.append((a, b, b + NA, a + NA))
me = bpy.data.meshes.new("terrain"); me.from_pydata(verts, [], faces); me.update()
for p in me.polygons:
    p.use_smooth = True
fa = me.attributes.new("forest", "FLOAT", "POINT"); fa.data.foreach_set("value", fw)
da = me.attributes.new("density", "FLOAT", "POINT"); da.data.foreach_set("value", dens)
terrain = bpy.data.objects.new("terrain", me); scene.collection.objects.link(terrain)

# terrain material: field patchwork (one colour per Voronoi cell), woods where "forest", aerial haze
tm = bpy.data.materials.new("terrain"); tm.use_nodes = True
nt = tm.node_tree; N = nt.nodes; L = nt.links
b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.95; b.inputs["Specular IOR Level"].default_value = 0.15
tc = N.new("ShaderNodeTexCoord")
mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / 170, 1 / 120, 1 / 170)
L.new(tc.outputs["Object"], mp.inputs["Vector"])
dist = N.new("ShaderNodeTexNoise"); dist.inputs["Scale"].default_value = 1.3; dist.inputs["Detail"].default_value = 2
L.new(mp.outputs[0], dist.inputs["Vector"])
warp = N.new("ShaderNodeMix"); warp.data_type = "VECTOR"; warp.inputs["Factor"].default_value = 0.25
L.new(mp.outputs[0], warp.inputs[4]); L.new(dist.outputs["Color"], warp.inputs[5])
vor = N.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 1.0
L.new(warp.outputs[1], vor.inputs["Vector"])
sep = N.new("ShaderNodeSeparateColor"); L.new(vor.outputs["Color"], sep.inputs[0])
ramp = N.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
pal = ["#b99a48", "#5e8a32", "#7c6446", "#c9b06a", "#4f7a2c", "#8c9a52", "#6e9440", "#a8843f", "#557f30", "#93744e"]
els = ramp.color_ramp.elements
while len(els) < len(pal):
    els.new(0.5)
for k, hx in enumerate(pal):
    els[k].position = k / len(pal); els[k].color = (*lin(hx), 1)
L.new(sep.outputs[0], ramp.inputs[0])
grain = N.new("ShaderNodeTexNoise"); grain.inputs["Scale"].default_value = 0.004; grain.inputs["Detail"].default_value = 8
L.new(tc.outputs["Object"], grain.inputs["Vector"])
gmix = N.new("ShaderNodeMix"); gmix.data_type = "RGBA"; gmix.blend_type = "OVERLAY"; gmix.inputs["Factor"].default_value = 0.25
L.new(ramp.outputs[0], gmix.inputs[6]); L.new(grain.outputs["Color"], gmix.inputs[7])
fat = N.new("ShaderNodeAttribute"); fat.attribute_name = "forest"
fcol = N.new("ShaderNodeMix"); fcol.data_type = "RGBA"
L.new(fat.outputs["Fac"], fcol.inputs["Factor"]); L.new(gmix.outputs[2], fcol.inputs[6]); fcol.inputs[7].default_value = (*lin("#26401b"), 1)
L.new(fcol.outputs[2], b.inputs["Base Color"])
hazed(tm, b.outputs[0])
me.materials.append(tm)

# ------------------------------------------------------------------------------ instanced woods (geometry nodes)
def proxy_tree(name, crown_r, crown_h, cypress=False):
    import bmesh
    bm = bmesh.new()
    if cypress:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=0.16, radius2=0.01, depth=1.0,
                              matrix=__import__("mathutils").Matrix.Translation((0, 0, 0.55)))
    else:
        g = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=crown_r)
        for v in g["verts"]:
            v.co.z = v.co.z * crown_h / crown_r + 0.62
            v.co += Vector((rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04)))
        bmesh.ops.create_cone(bm, cap_ends=False, segments=5, radius1=0.035, radius2=0.025, depth=0.4,
                              matrix=__import__("mathutils").Matrix.Translation((0, 0, 0.2)))
    m = bpy.data.meshes.new(name); bm.to_mesh(m); bm.free()
    for p in m.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, m)
    scene.collection.objects.link(o); o.hide_render = True
    return o


tree = proxy_tree("tree", 0.42, 0.36)
tree.data.materials.append(principled("crown", lin("#3a5c25"), 0.9, var=0.4, per_instance=True))
cyp = proxy_tree("cypress", 0, 0, cypress=True)
cyp.data.materials.append(principled("cypress", lin("#24361c"), 0.9, var=0.2, per_instance=True))

gn = bpy.data.node_groups.new("woods", "GeometryNodeTree")
gn.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
gn.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
G = gn.nodes; GL = gn.links
gi = G.new("NodeGroupInput"); go = G.new("NodeGroupOutput")


def scatter(obj, density, smin, smax, attr="density"):
    na = G.new("GeometryNodeInputNamedAttribute"); na.data_type = "FLOAT"; na.inputs["Name"].default_value = attr
    mul = G.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = density
    GL.new(na.outputs["Attribute"], mul.inputs[0])
    dp = G.new("GeometryNodeDistributePointsOnFaces"); dp.distribute_method = "RANDOM"
    GL.new(gi.outputs[0], dp.inputs["Mesh"]); GL.new(mul.outputs[0], dp.inputs["Density"])
    dp.inputs["Seed"].default_value = rnd.randint(0, 999)
    oi = G.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = obj
    def sock(coll, name, typ):
        return next(x for x in coll if x.name == name and x.type == typ)
    rv = G.new("FunctionNodeRandomValue"); rv.data_type = "FLOAT"
    sock(rv.inputs, "Min", "VALUE").default_value = smin; sock(rv.inputs, "Max", "VALUE").default_value = smax
    rr = G.new("FunctionNodeRandomValue"); rr.data_type = "FLOAT_VECTOR"
    sock(rr.inputs, "Min", "VECTOR").default_value = (0, 0, 0); sock(rr.inputs, "Max", "VECTOR").default_value = (0, 0, 6.283)
    ip = G.new("GeometryNodeInstanceOnPoints")
    GL.new(dp.outputs["Points"], ip.inputs["Points"]); GL.new(oi.outputs["Geometry"], ip.inputs["Instance"])
    GL.new(sock(rv.outputs, "Value", "VALUE"), ip.inputs["Scale"]); GL.new(sock(rr.outputs, "Value", "VECTOR"), ip.inputs["Rotation"])
    return ip


trees_i = scatter(tree, 1 / 60.0 if not CALIB else 1 / 6000.0, 9.0, 17.0)
cyp_i = scatter(cyp, 1 / 4000.0 if not CALIB else 1 / 400000.0, 11.0, 18.0, attr="cypress")
join = G.new("GeometryNodeJoinGeometry")
GL.new(gi.outputs[0], join.inputs[0]); GL.new(trees_i.outputs[0], join.inputs[0]); GL.new(cyp_i.outputs[0], join.inputs[0])
GL.new(join.outputs[0], go.inputs[0])
# cypresses: sparse, along field edges away from the woods
cyw = [(1 - f) * (1.0 if 900 < math.hypot(*v[:2]) < 9000 else 0.0) for f, v in zip(fw, verts)]
ca = me.attributes.new("cypress", "FLOAT", "POINT"); ca.data.foreach_set("value", cyw)
mod = terrain.modifiers.new("woods", "NODES"); mod.node_group = gn

# ------------------------------------------------------------------------------ farmhouses on the hills
house_m = bpy.data.meshes.new("house")
hv = [(-5, -8, 0), (5, -8, 0), (5, 8, 0), (-5, 8, 0), (-5, -8, 6), (5, -8, 6), (5, 8, 6), (-5, 8, 6)]
hf = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
house_m.from_pydata(hv, [], hf); house_m.update()
roof_m = bpy.data.meshes.new("roof")
rv_ = [(-5.6, -8.6, 6), (5.6, -8.6, 6), (5.6, 8.6, 6), (-5.6, 8.6, 6), (0, -3, 8.2), (0, 3, 8.2)]
roof_m.from_pydata(rv_, [], [(0, 1, 4), (2, 3, 5), (1, 2, 5, 4), (3, 0, 4, 5)]); roof_m.update()
house_m.materials.append(principled("house_wall", lin("#e3c99c"), 0.85))
roof_m.materials.append(principled("house_roof", lin("#a85a3a"), 0.8))
placed = 0
for _ in range(4000):
    if placed >= (40 if CALIB else 260):
        break
    a = rnd.uniform(0, 2 * math.pi); r = 1600 * (R1 * 0.5 / 1600) ** rnd.random()
    x, y = r * math.cos(a), r * math.sin(a)
    if forest(x, y) > 0.3:
        continue
    z = height(x, y)
    for mesh in (house_m, roof_m):
        o = bpy.data.objects.new("h", mesh); o.location = (x, y, z - 0.5); o.rotation_euler[2] = rnd.uniform(0, 3.14)
        s = rnd.uniform(0.8, 1.4); o.scale = (s, s, s); scene.collection.objects.link(o)
    placed += 1
print("HOUSES", placed)

if CALIB:   # direction markers: red east (+X), green north (+Y), blue west (-X)
    for (x, y), c in (((3000, 0), (1, 0, 0)), ((0, 3000), (0, 1, 0)), ((-3000, 0), (0, 0, 1))):
        bpy.ops.mesh.primitive_cylinder_add(radius=40, depth=900, location=(x, y, height(x, y) + 450))
        mm = bpy.data.materials.new("mk"); mm.use_nodes = True
        e = mm.node_tree.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*c, 1); e.inputs["Strength"].default_value = 5
        mm.node_tree.links.new(e.outputs[0], mm.node_tree.nodes["Material Output"].inputs["Surface"])
        bpy.context.object.data.materials.append(mm)

# ------------------------------------------------------------------------------ light: the app's sky and sun
world = bpy.data.worlds.new("sky"); scene.world = world; world.use_nodes = True
wn = world.node_tree
env = wn.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(HDRI)
mapn = wn.nodes.new("ShaderNodeMapping"); mapn.inputs["Rotation"].default_value = (0, 0, -SKY_ROT)
tco = wn.nodes.new("ShaderNodeTexCoord")
wn.links.new(tco.outputs["Generated"], mapn.inputs["Vector"]); wn.links.new(mapn.outputs[0], env.inputs["Vector"])
wn.links.new(env.outputs[0], wn.nodes["Background"].inputs[0]); wn.nodes["Background"].inputs[1].default_value = 0.8
# sun: the app's SUN_DIR (three: azimuth of the sky sun turned by SKY_ROTATION, 32 deg elevation) -> Blender (x, -z, y)
sx, sz = 0.555, 0.377
c, s = math.cos(SKY_ROT), math.sin(SKY_ROT)
ax, az = sx * c + sz * s, -sx * s + sz * c
hl = math.hypot(ax, az); ax, az = ax / hl, az / hl
el = math.radians(32)
d3 = Vector((ax * math.cos(el), math.sin(el), az * math.cos(el)))
db = Vector((d3.x, -d3.z, d3.y))
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 4.4; sun.color = lin("#ffe7c4"); sun.angle = math.radians(1.5)
so = bpy.data.objects.new("sun", sun); scene.collection.objects.link(so)
so.rotation_euler = db.to_track_quat("Z", "Y").to_euler()

# ------------------------------------------------------------------------------ panoramic camera at the farm
cam = bpy.data.cameras.new("pano"); cam.type = "PANO"
try:
    cam.panorama_type = "EQUIRECTANGULAR"
except Exception:
    cam.cycles.panorama_type = "EQUIRECTANGULAR"
cam.latitude_min, cam.latitude_max = LAT_MIN, LAT_MAX
cam.longitude_min, cam.longitude_max = -math.pi, math.pi
cam.clip_start = 1.0; cam.clip_end = 60000
co = bpy.data.objects.new("pano", cam); scene.collection.objects.link(co); scene.camera = co
co.location = (0, 0, EYE)
co.rotation_euler = (math.radians(90), 0, 0)
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"; prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.device = "GPU"
scene.cycles.samples = 16 if CALIB else 128
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = WIDTH
scene.render.resolution_y = round(WIDTH * (LAT_MAX - LAT_MIN) / (2 * math.pi))
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.view_settings.exposure = -0.75
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = OUT
print("RENDER", scene.render.resolution_x, scene.render.resolution_y)
bpy.ops.render.render(write_still=True)
print("DONE", OUT)
