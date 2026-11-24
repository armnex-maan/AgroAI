"""Photoreal render of the Visual Planner scene with Cycles (run by the backend render service, Blender --background).

Input (job folder): scene.glb (the planner's own meshes: terrain, beds, roads, buildings, greenhouse... exported by the
browser with three.js) and meta.json:
  camera {matrix (16, three.js column-major world matrix), fov (vertical deg), aspect}, sun [x,y,z] (three.js, toward sun),
  fog {near, far}, width, samples,
  impostors [{name, items: [x,y,z,h,rot]*}]  trees/crops drawn as impostors in the browser -> real 3D models here,
  instances [{proto, matrices: [16]*}]        repeated meshes exported once (node "agro-proto-*") + their world matrices,
  grass {center: [x,z], radius}                 real grass blades scattered on the terrain near the farm.
Assets (render assets folder): src/<tree>/<tree>_1k.blend (Poly Haven CC0 trees), crops/<crop>.blend (make_crops.py).
Missing tree assets fall back to simple procedural trees, so the render always completes.

usage: blender --background --factory-startup --disable-autoexec --python render_scene.py -- <job_dir> <assets_dir> <public_planner_dir>
Prints "STAGE <name>" and "PROGRESS <done>/<total>" lines for the service.
"""
import json
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

JOB, ASSETS, PUB = sys.argv[sys.argv.index("--") + 1:][:3]
meta = json.load(open(os.path.join(JOB, "meta.json"), encoding="utf-8"))
HAZE = (0.65, 0.745, 0.82)
C3 = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))           # three.js (x, y, z) -> Blender (x, -z, y)
C4 = C3.to_4x4()
C4i = C4.inverted()


def stage(s):
    print("STAGE", s, flush=True)


def to_b(v):
    return Vector((v[0], -v[2], v[1]))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ------------------------------------------------------------------------------------------------ planner meshes
stage("import")
bpy.ops.import_scene.gltf(filepath=os.path.join(JOB, "scene.glb"))
for o in list(scene.objects):
    if o.type in ("CAMERA", "LIGHT"):
        bpy.data.objects.remove(o, do_unlink=True)


def hidden_collection(name):
    """A collection linked to the scene but excluded from the view layer: source of instances, never rendered itself."""
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    bpy.context.view_layer.layer_collection.children[col.name].exclude = True
    return col


def move_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


# ------------------------------------------------------------------------------------------------ instancing helper
def instancer(name, col, locs, quats, scales):
    """Point cloud + geometry nodes instancing `col` at every point (rotation quaternion w,x,y,z, scale xyz)."""
    n = len(locs)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    me.vertices.foreach_set("co", np.asarray(locs, np.float32).ravel())
    ra = me.attributes.new("rot", "QUATERNION", "POINT"); ra.data.foreach_set("value", np.asarray(quats, np.float32).ravel())
    sa = me.attributes.new("scl", "FLOAT_VECTOR", "POINT"); sa.data.foreach_set("vector", np.asarray(scales, np.float32).ravel())
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    gn = bpy.data.node_groups.new(name, "GeometryNodeTree")
    gn.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    gn.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = gn.nodes, gn.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints"); L.new(gi.outputs[0], m2p.inputs["Mesh"])
    ci = N.new("GeometryNodeCollectionInfo"); ci.inputs["Collection"].default_value = col
    ci.transform_space = "ORIGINAL"
    rot = N.new("GeometryNodeInputNamedAttribute"); rot.data_type = "QUATERNION"; rot.inputs["Name"].default_value = "rot"
    scl = N.new("GeometryNodeInputNamedAttribute"); scl.data_type = "FLOAT_VECTOR"; scl.inputs["Name"].default_value = "scl"
    ip = N.new("GeometryNodeInstanceOnPoints")
    L.new(m2p.outputs["Points"], ip.inputs["Points"]); L.new(ci.outputs[0], ip.inputs["Instance"])
    L.new(rot.outputs["Attribute"], ip.inputs["Rotation"]); L.new(scl.outputs["Attribute"], ip.inputs["Scale"])
    L.new(ip.outputs[0], go.inputs[0])
    ob.modifiers.new("inst", "NODES").node_group = gn
    return ob


# repeated planner meshes (wheat plants, shrubs...): exported once, instanced here with their world matrices
stage("instances")
protos = {o.name.split(".")[0]: o for o in scene.objects if o.name.startswith("agro-proto-")}
for k, inst in enumerate(meta.get("instances", [])):
    src = protos.get(inst["proto"])
    if src is None:
        continue
    col = hidden_collection(f"proto{k}")
    move_to(src, col)
    for ch in src.children_recursive:
        move_to(ch, col)
    m = np.asarray(inst["matrices"], np.float64).reshape(-1, 4, 4).transpose(0, 2, 1)   # column-major -> rows
    locs, quats, scales = [], [], []
    for mt in m:
        mb = C4 @ Matrix(mt.tolist()) @ C4i
        t, q, s = mb.decompose()
        locs.append(t); quats.append((q.w, q.x, q.y, q.z)); scales.append(s)
    instancer(f"inst{k}", col, locs, quats, scales)
for o in protos.values():               # protos without matrices (should not happen) are not rendered at the origin
    if o.users_collection and o.users_collection[0] == scene.collection:
        o.hide_render = True

# ------------------------------------------------------------------------------------------------ real trees and crops
TREES = {"broadleaf_a": "tree_small_02", "broadleaf_b": "island_tree_01", "broadleaf_c": "island_tree_03",
         "olive_a": "island_tree_02", "fruit_red": "island_tree_01", "fruit_orange": "island_tree_01"}
FRUIT = {"fruit_red": (0.5, 0.012, 0.012), "fruit_orange": (0.85, 0.28, 0.02)}


def append_object(path, name):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [name]
    ob = dst.objects[0]
    return ob


def mesh_bounds(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(0), co.max(0)


def procedural_tree(name):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=7, radius1=0.25, radius2=0.15, depth=2.2, matrix=Matrix.Translation((0, 0, 1.1)))
    g = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=2.2)
    for v in g["verts"]:
        v.co.z = v.co.z * 0.85 + 3.6
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.16, 0.04, 1)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return bpy.data.objects.new(name, me)


def add_fruit(col, tree_ob, rgb, count=55, rad_k=0.034):
    lo, hi = mesh_bounds(tree_ob)
    height = hi[2] - lo[2]
    crown = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2] + height * 0.62])
    me = tree_ob.data
    cen = np.empty(len(me.polygons) * 3, np.float32); me.polygons.foreach_get("center", cen); cen = cen.reshape(-1, 3)
    mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
    leaf = [i for i, m in enumerate(me.materials) if m and "lea" in m.name]
    cen = cen[np.isin(mi, leaf)]
    if not len(cen):
        return
    d = np.linalg.norm(cen - crown, axis=1)
    shell = cen[(d > np.quantile(d, 0.45)) & (cen[:, 2] > lo[2] + height * 0.3)]
    rnd = np.random.default_rng(7)
    chosen = []
    for p in shell[rnd.permutation(len(shell))[:count * 40]]:
        if all(np.linalg.norm(p - q) > height * 0.07 for q in chosen):
            chosen.append(p)
            if len(chosen) >= count:
                break
    bm = bmesh.new()
    for p in chosen:
        p = crown + (p - crown) * 1.03
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=height * rad_k * rnd.uniform(0.85, 1.15),
                                  matrix=Matrix.Translation(Vector(p)))
    fme = bpy.data.meshes.new("fruit"); bm.to_mesh(fme); bm.free()
    for p in fme.polygons:
        p.use_smooth = True
    fm = bpy.data.materials.new("fruit"); fm.use_nodes = True
    pb = fm.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = (*rgb, 1); pb.inputs["Roughness"].default_value = 0.35
    pb.inputs["Coat Weight"].default_value = 0.3
    fme.materials.append(fm)
    fob = bpy.data.objects.new("fruit", fme)
    fob.matrix_world = tree_ob.matrix_world
    col.objects.link(fob)


_tree_cache = {}


def tree_object(t):
    """Real tree model (appended once per file; later uses share its mesh)."""
    if t in _tree_cache:
        src = _tree_cache[t]
        return src.copy(), True
    path = os.path.join(ASSETS, "src", t, f"{t}_1k.blend")
    ob = append_object(path, f"{t}_LOD0") if os.path.exists(path) else procedural_tree(t)
    _tree_cache[t] = ob
    return ob, False


def asset_collection(name):
    """Collection with the real model of an impostor name; returns (collection, model height in metres)."""
    col = hidden_collection(f"asset_{name}")
    if name in TREES:
        t = TREES[name]
        path = os.path.join(ASSETS, "src", t, f"{t}_1k.blend")
        ob, shared = tree_object(t)
        ob.matrix_world = Matrix.Identity(4)
        col.objects.link(ob)
        bpy.context.view_layer.update()
        lo, hi = mesh_bounds(ob)
        h = float(hi[2] - lo[2])
        if not shared:
            # the photoscans carry a patch of ground at the trunk foot: drop the faces in the bottom 3.5 %
            bm = bmesh.new(); bm.from_mesh(ob.data)
            lim = lo[2] + h * 0.035
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if max(v.co.z for v in f.verts) < lim], context="FACES")
            bm.to_mesh(ob.data); bm.free()
            lo, hi = mesh_bounds(ob)
            h = float(hi[2] - lo[2])
        ob.location.z = -float(lo[2])
        if name in FRUIT:
            bpy.context.view_layer.update()
            add_fruit(col, ob, FRUIT[name])
        return col, h
    crop = name[len("crop_"):] if name.startswith("crop_") else name
    path = os.path.join(ASSETS, "crops", f"{crop}.blend")
    if os.path.exists(path):
        ob = append_object(path, "crop")
    else:
        ob = procedural_tree(name); ob.scale = (0.12, 0.12, 0.12)
    col.objects.link(ob)
    bpy.context.view_layer.update()
    lo, hi = mesh_bounds(ob)
    return col, float(hi[2] - lo[2]) * (ob.scale.z or 1)


stage("assets")
for k, grp in enumerate(meta.get("impostors", [])):
    items = np.asarray(grp["items"], np.float64).reshape(-1, 5)
    if not len(items):
        continue
    col, h = asset_collection(grp["name"])
    locs = [to_b(it[:3]) for it in items]
    quats = []
    for it in items:
        q = Quaternion((0, 0, 1), float(it[4]))
        quats.append((q.w, q.x, q.y, q.z))
    scales = [(s, s, s) for s in (items[:, 3] / max(h, 1e-3))]
    instancer(f"imp{k}_{grp['name']}", col, locs, quats, scales)
    print("ASSET", grp["name"], len(items), "model height", round(h, 2), flush=True)

# ------------------------------------------------------------------------------------------------ grass near the farm
stage("grass")
terrain = next((o for o in scene.objects if o.type == "MESH" and o.name.startswith("agro-terrain")), None)
g = meta.get("grass")
if terrain is not None and g:
    rnd = random.Random(5)
    bm = bmesh.new()
    for b in range(9):                                        # one clump: 9 curved blades, 1 m tall at scale 1
        a = rnd.uniform(0, 6.283); ox, oy = rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12)
        hgt, lean, w = rnd.uniform(0.55, 1.0), rnd.uniform(0.15, 0.4), rnd.uniform(0.025, 0.04)
        dx, dy = math.cos(a), math.sin(a); px, py = -dy * w, dx * w
        pts = [(ox + dx * lean * t * t, oy + dy * lean * t * t, hgt * t) for t in (0, 0.35, 0.7, 1.0)]
        vs = []
        for i, (x, y, z) in enumerate(pts):
            k = 1 - i / (len(pts) - 1)
            vs.append((bm.verts.new((x - px * k, y - py * k, z)), bm.verts.new((x + px * k, y + py * k, z))))
        for i in range(len(vs) - 1):
            bm.faces.new((vs[i][0], vs[i][1], vs[i + 1][1], vs[i + 1][0]))
    cme = bpy.data.meshes.new("clump"); bm.to_mesh(cme); bm.free()
    gm = bpy.data.materials.new("grass"); gm.use_nodes = True
    nt = gm.node_tree; pb = nt.nodes["Principled BSDF"]
    oi = nt.nodes.new("ShaderNodeObjectInfo"); rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = (0.09, 0.2, 0.035, 1); rp.color_ramp.elements[1].color = (0.24, 0.36, 0.07, 1)
    nt.links.new(oi.outputs["Random"], rp.inputs[0])
    gc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(gc.outputs["Generated"], sep.inputs[0])
    # blade colour: the clump's own green (per instance), darker at the base, full at the tip
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 1.0
    nt.links.new(rp.outputs[0], mx.inputs[6]); mx.inputs[7].default_value = (0.5, 0.5, 0.5, 1)
    inv = nt.nodes.new("ShaderNodeMix"); inv.data_type = "RGBA"
    nt.links.new(sep.outputs[2], inv.inputs["Factor"]); nt.links.new(mx.outputs[2], inv.inputs[6]); nt.links.new(rp.outputs[0], inv.inputs[7])
    nt.links.new(inv.outputs[2], pb.inputs["Base Color"])
    pb.inputs["Roughness"].default_value = 0.85
    pb.inputs["Specular IOR Level"].default_value = 0.15      # blades must not sparkle
    # light through the blades: a translucent mix (subsurface on thin single-sided blades makes white fireflies)
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent"); nt.links.new(inv.outputs[2], tr.inputs["Color"])
    ms = nt.nodes.new("ShaderNodeMixShader"); ms.inputs["Fac"].default_value = 0.2
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(pb.outputs[0], ms.inputs[1]); nt.links.new(tr.outputs[0], ms.inputs[2]); nt.links.new(ms.outputs[0], out.inputs["Surface"])
    cme.materials.append(gm)
    clump = bpy.data.objects.new("clump", cme)
    gcol = hidden_collection("grass_clump"); gcol.objects.link(clump)
    excl = hidden_collection("grass_exclude")
    for o in scene.objects:
        if o.type == "MESH" and o is not terrain and not o.name.startswith(("inst", "imp", "agro-proto")) and o.name not in excl.objects:
            if any(c.name.startswith(("proto", "asset_")) for c in o.users_collection):
                continue
            excl.objects.link(o)
    cx, cy = g["center"][0], -g["center"][1]
    gn = bpy.data.node_groups.new("grass", "GeometryNodeTree")
    gn.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    gn.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = gn.nodes, gn.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    oinfo = N.new("GeometryNodeObjectInfo"); oinfo.inputs["Object"].default_value = terrain; oinfo.transform_space = "RELATIVE"
    pos = N.new("GeometryNodeInputPosition")
    dist = N.new("ShaderNodeVectorMath"); dist.operation = "DISTANCE"; dist.inputs[1].default_value = (cx, cy, 0)
    flat = N.new("ShaderNodeVectorMath"); flat.operation = "MULTIPLY"; flat.inputs[1].default_value = (1, 1, 0)
    L.new(pos.outputs[0], flat.inputs[0]); L.new(flat.outputs[0], dist.inputs[0])
    far = N.new("FunctionNodeCompare"); far.data_type = "FLOAT"; far.operation = "GREATER_THAN"; far.inputs[1].default_value = float(g["radius"]) + 15
    L.new(dist.outputs["Value"], far.inputs[0])
    dg = N.new("GeometryNodeDeleteGeometry"); dg.domain = "FACE"
    L.new(oinfo.outputs["Geometry"], dg.inputs["Geometry"]); L.new(far.outputs[0], dg.inputs["Selection"])
    dp = N.new("GeometryNodeDistributePointsOnFaces"); dp.distribute_method = "RANDOM"
    dp.inputs["Density"].default_value = float(g.get("density", 7.0))
    L.new(dg.outputs[0], dp.inputs["Mesh"])
    ex = N.new("GeometryNodeCollectionInfo"); ex.inputs["Collection"].default_value = excl; ex.transform_space = "ORIGINAL"
    rl = N.new("GeometryNodeRealizeInstances"); L.new(ex.outputs[0], rl.inputs[0])
    prox = N.new("GeometryNodeProximity")
    L.new(rl.outputs[0], prox.inputs[0])
    pos2 = N.new("GeometryNodeInputPosition")
    near = N.new("FunctionNodeCompare"); near.data_type = "FLOAT"; near.operation = "LESS_THAN"; near.inputs[1].default_value = 0.35
    try:
        L.new(pos2.outputs[0], prox.inputs["Sample Position"])
    except KeyError:
        pass
    L.new(prox.outputs["Distance"], near.inputs[0])
    dist2 = N.new("ShaderNodeVectorMath"); dist2.operation = "DISTANCE"; dist2.inputs[1].default_value = (cx, cy, 0)
    flat2 = N.new("ShaderNodeVectorMath"); flat2.operation = "MULTIPLY"; flat2.inputs[1].default_value = (1, 1, 0)
    L.new(pos2.outputs[0], flat2.inputs[0]); L.new(flat2.outputs[0], dist2.inputs[0])
    out_r = N.new("FunctionNodeCompare"); out_r.data_type = "FLOAT"; out_r.operation = "GREATER_THAN"; out_r.inputs[1].default_value = float(g["radius"])
    L.new(dist2.outputs["Value"], out_r.inputs[0])
    either = N.new("FunctionNodeBooleanMath"); either.operation = "OR"
    L.new(near.outputs[0], either.inputs[0]); L.new(out_r.outputs[0], either.inputs[1])
    dp2 = N.new("GeometryNodeDeleteGeometry"); dp2.domain = "POINT"
    L.new(dp.outputs["Points"], dp2.inputs["Geometry"]); L.new(either.outputs[0], dp2.inputs["Selection"])
    gci = N.new("GeometryNodeCollectionInfo"); gci.inputs["Collection"].default_value = gcol; gci.transform_space = "ORIGINAL"

    def sock(coll, name, typ):
        return next(x for x in coll if x.name == name and x.type == typ)
    rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"
    sock(rs.inputs, "Min", "VALUE").default_value = 0.12; sock(rs.inputs, "Max", "VALUE").default_value = 0.3
    rr = N.new("FunctionNodeRandomValue"); rr.data_type = "FLOAT_VECTOR"
    sock(rr.inputs, "Min", "VECTOR").default_value = (0, 0, 0); sock(rr.inputs, "Max", "VECTOR").default_value = (0, 0, 6.283)
    ip = N.new("GeometryNodeInstanceOnPoints")
    L.new(dp2.outputs[0], ip.inputs["Points"]); L.new(gci.outputs[0], ip.inputs["Instance"])
    L.new(sock(rs.outputs, "Value", "VALUE"), ip.inputs["Scale"]); L.new(sock(rr.outputs, "Value", "VECTOR"), ip.inputs["Rotation"])
    L.new(ip.outputs[0], go.inputs[0])
    gob = bpy.data.objects.new("grass", bpy.data.meshes.new("grass"))
    scene.collection.objects.link(gob)
    gob.modifiers.new("grass", "NODES").node_group = gn

# ------------------------------------------------------------------------------------------------ terrain detail
grass_img = os.path.join(PUB, "aerial_grass_rock_diff_1k.jpg")
if terrain is not None and os.path.exists(grass_img) and terrain.data.materials:
    tmat = terrain.data.materials[0]
    nt = tmat.node_tree
    pb = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if pb is not None and pb.inputs["Base Color"].is_linked:
        src = pb.inputs["Base Color"].links[0].from_socket
        img = bpy.data.images.load(grass_img)
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        lum = None
        for k, (scale, off) in enumerate(((1 / 7.0, 0.0), (1 / 31.0, 0.37))):
            mpg = nt.nodes.new("ShaderNodeMapping"); mpg.inputs["Scale"].default_value = (scale, scale, scale)
            mpg.inputs["Location"].default_value = (off, off, 0)
            nt.links.new(geo.outputs["Position"], mpg.inputs["Vector"])
            tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img
            nt.links.new(mpg.outputs[0], tx.inputs["Vector"])
            bw = nt.nodes.new("ShaderNodeRGBToBW"); nt.links.new(tx.outputs["Color"], bw.inputs[0])
            w = nt.nodes.new("ShaderNodeMath"); w.operation = "MULTIPLY"; w.inputs[1].default_value = 0.6 if k == 0 else 0.4
            nt.links.new(bw.outputs[0], w.inputs[0])
            if lum is None:
                lum = w
            else:
                add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
                nt.links.new(lum.outputs[0], add.inputs[0]); nt.links.new(w.outputs[0], add.inputs[1]); lum = add
        k = nt.nodes.new("ShaderNodeMapRange")
        k.inputs["From Min"].default_value = 0.0; k.inputs["From Max"].default_value = 0.3
        k.inputs["To Min"].default_value = 0.0; k.inputs["To Max"].default_value = 1.0
        k.clamp = False
        nt.links.new(lum.outputs[0], k.inputs["Value"])
        cl = nt.nodes.new("ShaderNodeClamp"); cl.inputs["Min"].default_value = 0.6; cl.inputs["Max"].default_value = 1.12   # no bright specks (pebbles of the photo)
        nt.links.new(k.outputs["Result"], cl.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 0.7
        nt.links.new(src, mul.inputs[6])
        cc = nt.nodes.new("ShaderNodeCombineColor")
        for i in range(3):
            nt.links.new(cl.outputs[0], cc.inputs[i])
        nt.links.new(cc.outputs[0], mul.inputs[7])
        nt.links.new(mul.outputs[2], pb.inputs["Base Color"])
        pb.inputs["Roughness"].default_value = 0.95

# ------------------------------------------------------------------------------------------------ aerial haze
stage("materials")
fog = meta.get("fog", {"near": 150, "far": 10500})
for mat in bpy.data.materials:
    if not mat.use_nodes or mat.name in ("grass",):
        continue
    nt = mat.node_tree
    for pb in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
        bc = pb.inputs["Base Color"]
        cam = nt.nodes.new("ShaderNodeCameraData")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = fog["near"]; mr.inputs["From Max"].default_value = fog["far"]
        mr.inputs["To Max"].default_value = 0.92
        nt.links.new(cam.outputs["View Distance"], mr.inputs["Value"])
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
        nt.links.new(mr.outputs["Result"], mix.inputs["Factor"])
        if bc.is_linked:
            nt.links.new(bc.links[0].from_socket, mix.inputs[6])
        else:
            mix.inputs[6].default_value = bc.default_value
        mix.inputs[7].default_value = (*HAZE, 1)
        nt.links.new(mix.outputs[2], bc)

# ------------------------------------------------------------------------------------------------ sky, sun, horizon
stage("light")
sun_t = Vector(meta["sun"]).normalized()
sun_b = to_b(sun_t)
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = float(meta.get("sun_energy", 6.0)); sun.angle = math.radians(1.2)
sun.color = (1.0, 0.91, 0.78)
so = bpy.data.objects.new("sun", sun); scene.collection.objects.link(so)
so.rotation_euler = sun_b.to_track_quat("Z", "Y").to_euler()

world = bpy.data.worlds.new("sky"); scene.world = world; world.use_nodes = True
W, WL = world.node_tree.nodes, world.node_tree.links
for n in list(W):
    if n.type != "OUTPUT_WORLD":
        W.remove(n)
wout = next(n for n in W if n.type == "OUTPUT_WORLD")
tc = W.new("ShaderNodeTexCoord")
# lighting sky (non-camera rays): soft gradient, so the only sharp shadows come from the sun lamp
sepd = W.new("ShaderNodeSeparateXYZ"); WL.new(tc.outputs["Generated"], sepd.inputs[0])
gz = W.new("ShaderNodeMapRange"); gz.inputs["From Min"].default_value = -0.05; gz.inputs["From Max"].default_value = 0.6
WL.new(sepd.outputs[2], gz.inputs["Value"])
grad = W.new("ShaderNodeMix"); grad.data_type = "RGBA"
grad.inputs[6].default_value = (*HAZE, 1); grad.inputs[7].default_value = (0.22, 0.42, 0.85, 1)
WL.new(gz.outputs["Result"], grad.inputs["Factor"])
bg_light = W.new("ShaderNodeBackground"); bg_light.inputs["Strength"].default_value = float(meta.get("sky_energy", 0.55))
WL.new(grad.outputs[2], bg_light.inputs["Color"])
# camera rays: the photographed sky (same HDRI as the planner), turned so its sun sits at the lamp's azimuth,
# with the rendered horizon band (distant hills) over it
hdri = os.path.join(PUB, "kloofendal_48d_partly_cloudy_puresky_2k.hdr")
env = W.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(hdri)
mp = W.new("ShaderNodeMapping")
hdr_sun_az = (0.5 - 1218.0 / 2048.0) * 2 * math.pi            # azimuth of the HDRI sun in Blender's equirect lookup
mp.inputs["Rotation"].default_value = (0, 0, hdr_sun_az - math.atan2(sun_b.y, sun_b.x))
WL.new(tc.outputs["Generated"], mp.inputs["Vector"]); WL.new(mp.outputs[0], env.inputs["Vector"])
hdr_mul = W.new("ShaderNodeMix"); hdr_mul.data_type = "RGBA"; hdr_mul.blend_type = "MULTIPLY"; hdr_mul.inputs["Factor"].default_value = 1
WL.new(env.outputs[0], hdr_mul.inputs[6]); hdr_mul.inputs[7].default_value = (1.0, 1.0, 1.0, 1)
cam_col = hdr_mul.outputs[2]
band_path = os.path.join(PUB, "horizon", "horizon.webp")
if os.path.exists(band_path):
    LAT_MIN, LAT_MAX = math.radians(-24), math.radians(8)
    at = W.new("ShaderNodeMath"); at.operation = "ARCTAN2"; WL.new(sepd.outputs[0], at.inputs[0]); WL.new(sepd.outputs[1], at.inputs[1])
    uu = W.new("ShaderNodeMath"); uu.operation = "MULTIPLY_ADD"; uu.inputs[1].default_value = 1 / (2 * math.pi); uu.inputs[2].default_value = 0.5
    WL.new(at.outputs[0], uu.inputs[0])
    asn = W.new("ShaderNodeMath"); asn.operation = "ARCSINE"; WL.new(sepd.outputs[2], asn.inputs[0])
    vv = W.new("ShaderNodeMath"); vv.operation = "MULTIPLY_ADD"; vv.inputs[1].default_value = 1 / (LAT_MAX - LAT_MIN)
    vv.inputs[2].default_value = -LAT_MIN / (LAT_MAX - LAT_MIN)
    WL.new(asn.outputs[0], vv.inputs[0])
    uv = W.new("ShaderNodeCombineXYZ"); WL.new(uu.outputs[0], uv.inputs[0]); WL.new(vv.outputs[0], uv.inputs[1])
    band = W.new("ShaderNodeTexImage"); band.image = bpy.data.images.load(band_path); band.extension = "CLIP"
    band.interpolation = "Cubic"
    WL.new(uv.outputs[0], band.inputs["Vector"])
    bmix = W.new("ShaderNodeMix"); bmix.data_type = "RGBA"
    WL.new(band.outputs["Alpha"], bmix.inputs["Factor"]); WL.new(cam_col, bmix.inputs[6]); WL.new(band.outputs["Color"], bmix.inputs[7])
    cam_col = bmix.outputs[2]
bg_cam = W.new("ShaderNodeBackground"); bg_cam.inputs["Strength"].default_value = 1.0
WL.new(cam_col, bg_cam.inputs["Color"])
lp = W.new("ShaderNodeLightPath")
wmix = W.new("ShaderNodeMixShader")
WL.new(lp.outputs["Is Camera Ray"], wmix.inputs["Fac"]); WL.new(bg_light.outputs[0], wmix.inputs[1]); WL.new(bg_cam.outputs[0], wmix.inputs[2])
WL.new(wmix.outputs[0], wout.inputs["Surface"])

# ------------------------------------------------------------------------------------------------ camera and render
stage("camera")
cm = meta["camera"]
mt = np.asarray(cm["matrix"], np.float64).reshape(4, 4).T
cam = bpy.data.cameras.new("cam")
cam.sensor_fit = "VERTICAL"
cam.angle_y = math.radians(cm["fov"])
cam.clip_start = 0.3; cam.clip_end = 40000
co = bpy.data.objects.new("cam", cam); scene.collection.objects.link(co); scene.camera = co
co.matrix_world = C4 @ Matrix(mt.tolist())

r = scene.render
r.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for kind in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = kind
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            break
    except TypeError:
        continue
for d in prefs.devices:
    d.use = d.type in ("OPTIX", "CUDA")
scene.cycles.device = "GPU" if any(d.use for d in prefs.devices) else "CPU"
scene.cycles.samples = int(meta.get("samples", 128))
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.diffuse_bounces = 3
scene.cycles.glossy_bounces = 3
scene.cycles.transmission_bounces = 6
scene.cycles.transparent_max_bounces = 64
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.blur_glossy = 1.0
r.resolution_x = int(meta.get("width", 1920))
r.resolution_y = int(round(r.resolution_x / float(cm["aspect"])))
r.resolution_percentage = 100
r.film_transparent = False
scene.view_settings.view_transform = "AgX"
for look in (meta.get("look") or "AgX - Punchy", "AgX - Punchy", "Punchy", "AgX - Medium High Contrast", "Medium High Contrast"):
    try:
        scene.view_settings.look = look
        break
    except TypeError:
        continue
scene.view_settings.exposure = float(meta.get("exposure", 0.45))
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGB"
r.filepath = os.path.join(JOB, "render.png")


def on_stats(sc, *a):
    txt = a[0] if a and isinstance(a[0], str) else ""
    import re
    m = re.search(r"Sample (\d+)/(\d+)", txt)
    if m:
        print("PROGRESS", m.group(1), m.group(2), flush=True)


try:
    bpy.app.handlers.render_stats.append(on_stats)
except Exception:
    pass
stage("render")
print("RES", r.resolution_x, r.resolution_y, "objects", len(scene.objects), flush=True)
bpy.ops.render.render(write_still=True)
stage("done")
