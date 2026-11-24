"""Bake a hemi-octahedral impostor atlas of a Poly Haven tree with Cycles (run inside Blender, --background).

usage: blender --background --disable-autoexec <tree>.blend --python bake_impostor.py -- <object> <out_dir> <name> [N] [px] [samples]

Frames: N x N views on the upper hemisphere (hemi-octahedral grid, grid points uv = (i/(N-1), j/(N-1))).
Outputs (three.js convention: X east, Y up, Z south):
  <name>_color.png   RGBA, lit by a uniform white sky (albedo x ambient occlusion), alpha = coverage
  <name>_normal.png  RGB, object-space normal (mix of leaf normal and crown-sphere normal) * 0.5 + 0.5
  <name>.json        frames, frame size, centre and radius of the bounding sphere normalised by the tree height
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OBJ, OUT, NAME = argv[0], argv[1], argv[2]
N = int(argv[3]) if len(argv) > 3 else 8
PX = int(argv[4]) if len(argv) > 4 else 256
SAMPLES = int(argv[5]) if len(argv) > 5 else 64
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(OUT, "_frames_" + NAME)
os.makedirs(TMP, exist_ok=True)

scene = bpy.context.scene
tree = bpy.data.objects[OBJ]
for o in scene.objects:
    o.hide_render = o is not tree
    o.hide_viewport = o is not tree

# ---- bounding sphere (Blender coords) from the vertices
me = tree.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
co = np.empty(len(me.vertices) * 3, dtype=np.float32)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
mw = np.array(tree.matrix_world)
co = co @ mw[:3, :3].T + mw[:3, 3]
base_z = float(co[:, 2].min())
height = float(co[:, 2].max() - base_z)
lo, hi = co.min(0), co.max(0)
centre = (lo + hi) / 2
radius = float(np.sqrt(((co - centre) ** 2).sum(1)).max()) * 1.01
crown = np.array([centre[0], centre[1], base_z + height * 0.62])

# the photoscans carry a patch of ground/roots at the trunk base: lit by the white sky it bakes as a pale disc.
# Remove every face lying entirely in the bottom 3.5 % of the tree (the trunk foot is hidden by grass anyway).
if os.environ.get("KEEP_BASE") != "1":
    import bmesh
    bm = bmesh.new(); bm.from_mesh(tree.data)
    lim = base_z + height * 0.035
    mwm = tree.matrix_world
    kill = [f for f in bm.faces if max((mwm @ v.co).z for v in f.verts) < lim]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(tree.data); bm.free()
    print(f"BASE removed {len(kill)} faces below {lim:.2f}")

# optional fruit (orchard variants): glossy spheres on the outer shell of the crown, FRUIT="r,g,b" (linear) [FRUIT_N]
# Built as a separate small object (fast); it is rendered and baked together with the tree.
extra = []
if os.environ.get("FRUIT"):
    import bmesh
    rgb = [float(x) for x in os.environ["FRUIT"].split(",")]
    count = int(os.environ.get("FRUIT_N", "160"))
    fm = bpy.data.materials.new("fruit")
    fm.use_nodes = True
    pb = fm.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = (*rgb, 1)
    pb.inputs["Roughness"].default_value = 0.5
    pb.inputs["Specular IOR Level"].default_value = 0.2    # a glossy coat would bake the white sky into pale/pink fruit
    me_t = tree.data
    npoly = len(me_t.polygons)
    cen = np.empty(npoly * 3, dtype=np.float32); me_t.polygons.foreach_get("center", cen); cen = cen.reshape(-1, 3)
    mat_i = np.empty(npoly, dtype=np.int32); me_t.polygons.foreach_get("material_index", mat_i)
    leaf_idx = [i for i, m in enumerate(me_t.materials) if m and "lea" in m.name]
    cen = cen[np.isin(mat_i, leaf_idx)] @ mw[:3, :3].T + mw[:3, 3]
    d = np.linalg.norm(cen - crown, axis=1)
    shell = cen[(d > np.quantile(d, 0.45)) & (cen[:, 2] > base_z + height * 0.3)]
    rnd = np.random.default_rng(7)
    # spread evenly over the crown: reject candidates too close to a fruit already placed
    min_d = height * 0.07
    chosen = []
    for p in shell[rnd.permutation(len(shell))[:count * 40]]:
        if all(np.linalg.norm(p - q) > min_d for q in chosen):
            chosen.append(p)
            if len(chosen) >= count:
                break
    picks = crown + (np.array(chosen) - crown) * 1.03
    bm = bmesh.new()
    rad = height * float(os.environ.get("FRUIT_R", "0.022"))
    for p in picks:
        r = rad * rnd.uniform(0.85, 1.15)
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=r, matrix=Matrix.Translation(Vector(p)), calc_uvs=False)
    for f in bm.faces:
        f.smooth = True
    fme = bpy.data.meshes.new("fruit"); bm.to_mesh(fme); bm.free()
    fme.materials.append(fm)
    fob = bpy.data.objects.new("fruit", fme)
    scene.collection.objects.link(fob)
    extra.append(fob)
    print(f"FRUIT added {len(picks)} on {len(shell)} shell faces")
for o in extra:
    o.hide_render = False
print(f"BAKE {NAME}: verts {len(co)} height {height:.2f} radius {radius:.2f}")


def b2t(v):  # Blender (x, y, z) -> three (x, z, -y)
    return np.array([v[0], v[2], -v[1]])


def t2b(v):  # three (x, y, z) -> Blender (x, -z, y)
    return Vector((v[0], -v[2], v[1]))


def decode(u, v):
    """Hemi-octahedral grid point (0..1) -> unit direction (three coords, y >= 0)."""
    px, py = u * 2 - 1, v * 2 - 1
    x, z = (px + py) / 2, (px - py) / 2
    y = 1 - abs(x) - abs(z)
    d = np.array([x, y, z])
    return d / np.linalg.norm(d)


def basis(d):
    """Right/up of the frame looking along -d (three coords), same convention as the runtime shader."""
    up_ref = np.array([0, 1, 0]) if abs(d[1]) < 0.999 else np.array([0, 0, -1])
    f = -d
    r = np.cross(f, up_ref); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return r, u


# ---- render settings
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.device = "GPU"
scene.render.resolution_x = scene.render.resolution_y = PX
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.use_persistent_data = True
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
scene.render.image_settings.color_mode = "RGBA"

world = bpy.data.worlds.new("white") if not scene.world else scene.world
scene.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
bg = wn.nodes.new("ShaderNodeBackground")
bg.inputs["Color"].default_value = (1, 1, 1, 1)
bg.inputs["Strength"].default_value = 1.0
wo = wn.nodes.new("ShaderNodeOutputWorld")
wn.links.new(bg.outputs[0], wo.inputs["Surface"])

cam_data = bpy.data.cameras.new("imp_cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = radius * 2
cam_data.clip_start = 0.01
cam_data.clip_end = radius * 10
cam = bpy.data.objects.new("imp_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
c3 = b2t(centre)


def place(d):
    r, u = basis(d)
    pos = c3 + d * radius * 4
    m = Matrix((
        (*t2b(r), 0), (*t2b(u), 0), (*t2b(d), 0), (0, 0, 0, 1),
    )).transposed()
    m.translation = t2b(pos)
    cam.matrix_world = m


def render_all(tag, ext):
    for j in range(N):
        for i in range(N):
            place(decode(i / (N - 1), j / (N - 1)))
            scene.render.filepath = os.path.join(TMP, f"{tag}_{i}_{j}.{ext}")
            bpy.ops.render.render(write_still=True)


# ---- pass 1: colour under a uniform white sky
scene.cycles.samples = SAMPLES
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
render_all("c", "png")

# ---- pass 2: normals as emission, alpha kept from each material
crown_b = Vector(crown)
for mat in {m for ob in [tree, *extra] for m in ob.data.materials if m}:
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output) if any(
        n.type == "OUTPUT_MATERIAL" and n.is_active_output for n in nt.nodes) else next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    alpha_src = None
    for n in nt.nodes:
        if n.type in ("GROUP", "BSDF_PRINCIPLED") and "Alpha" in n.inputs and n.inputs["Alpha"].is_linked:
            alpha_src = n.inputs["Alpha"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sub = nt.nodes.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = crown_b
    nt.links.new(geo.outputs["Position"], sub.inputs[0])
    sph = nt.nodes.new("ShaderNodeVectorMath"); sph.operation = "NORMALIZE"
    nt.links.new(sub.outputs[0], sph.inputs[0])
    leaf = "leaves" in mat.name or "leaf" in mat.name
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "VECTOR"
    mix.inputs["Factor"].default_value = 0.6 if leaf else 0.15
    nt.links.new(geo.outputs["Normal"], mix.inputs[4])
    nt.links.new(sph.outputs[0], mix.inputs[5])
    nrm = nt.nodes.new("ShaderNodeVectorMath"); nrm.operation = "NORMALIZE"
    nt.links.new(mix.outputs[1], nrm.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(nrm.outputs[0], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")              # Blender (x, y, z) -> three (x, z, -y)
    neg = nt.nodes.new("ShaderNodeMath"); neg.operation = "MULTIPLY"; neg.inputs[1].default_value = -1
    nt.links.new(sep.outputs[0], comb.inputs[0])
    nt.links.new(sep.outputs[2], comb.inputs[1])
    nt.links.new(sep.outputs[1], neg.inputs[0]); nt.links.new(neg.outputs[0], comb.inputs[2])
    enc = nt.nodes.new("ShaderNodeVectorMath"); enc.operation = "MULTIPLY_ADD"
    enc.inputs[1].default_value = (0.5, 0.5, 0.5); enc.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(comb.outputs[0], enc.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(enc.outputs[0], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    if alpha_src is not None:
        nt.links.new(alpha_src, mx.inputs["Fac"])
    else:
        mx.inputs["Fac"].default_value = 1.0
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    for l in list(out.inputs["Surface"].links):
        nt.links.remove(l)
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 0
scene.cycles.transparent_max_bounces = 32
scene.render.image_settings.file_format = "OPEN_EXR"
scene.render.image_settings.color_depth = "16"
render_all("n", "exr")


# ---- atlas
def load(path):
    img = bpy.data.images.load(path)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(PX, PX, 4)
    bpy.data.images.remove(img)
    return a


def dilate(rgb, alpha, steps=12):
    """Spread colours into transparent pixels so mipmaps do not bleed black."""
    rgb = rgb.copy(); filled = alpha > 0.02
    for _ in range(steps):
        acc = np.zeros_like(rgb); cnt = np.zeros(alpha.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            f = np.roll(np.roll(filled, dy, 0), dx, 1)
            acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * f[..., None]; cnt += f
        grow = (~filled) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        filled = filled | grow
    rest = ~filled
    if rest.any():
        rgb[rest] = rgb[filled].mean(0)
    return rgb


S = N * PX
color = np.zeros((S, S, 4), np.float32)
normal = np.zeros((S, S, 4), np.float32)
for j in range(N):
    for i in range(N):
        c = load(os.path.join(TMP, f"c_{i}_{j}.png"))
        n = load(os.path.join(TMP, f"n_{i}_{j}.exr"))
        a = c[..., 3]
        c[..., :3] = dilate(c[..., :3], a)
        nn = n[..., :3]
        nn = dilate(nn, a)
        color[j * PX:(j + 1) * PX, i * PX:(i + 1) * PX] = c
        normal[j * PX:(j + 1) * PX, i * PX:(i + 1) * PX, :3] = nn
        normal[j * PX:(j + 1) * PX, i * PX:(i + 1) * PX, 3] = 1


def save(arr, path, srgb_already):
    img = bpy.data.images.new(os.path.basename(path), S, S, alpha=True)
    img.colorspace_settings.name = "sRGB" if srgb_already else "Non-Color"
    img.pixels.foreach_set(np.clip(arr, 0, 1).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()


save(color, os.path.join(OUT, f"{NAME}_color.png"), True)
save(normal, os.path.join(OUT, f"{NAME}_normal.png"), False)
c_n = np.array([c3[0], c3[1] - base_z, c3[2]]) / height   # sphere centre from the trunk base (origin), in tree heights
json.dump({"name": NAME, "frames": N, "px": PX, "height": height, "radius": radius / height,
           "centre": [float(c_n[0]), float(c_n[1]), float(c_n[2])]},
          open(os.path.join(OUT, f"{NAME}.json"), "w"), indent=1)
print("DONE", NAME)
