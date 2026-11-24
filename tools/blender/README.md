# Blender asset pipeline (Visual Planner 3D)

Blender 5.3, Cycles on GPU (OptiX). Scripts run headless:

```powershell
# 1. crops modelled procedurally -> crops/<name>.blend (object "crop", metres, base at the origin)
blender --background --factory-startup --python tools/blender/make_crops.py -- <work>/crops [preview.png]

# 2. impostor atlas of a tree or crop (8 x 8 views, 256 px trees / 192 px crops)
blender --background --disable-autoexec <file>.blend --python tools/blender/bake_impostor.py -- <object> <work>/out <name> 8 256 64

# 3. WebP + manifest for the app (needs Pillow)
python tools/blender/publish_impostors.py <work>/out frontend/public/planner/impostors frontend/src/components/rotation/planner/engine/impostors.json <names...>
```

Trees: Poly Haven CC0 models `tree_small_02`, `island_tree_01`, `island_tree_02`, `island_tree_03` (object `<name>_LOD0`).
The colour atlas is lit by a uniform white sky (albedo x ambient occlusion); the normal atlas mixes the leaf normal with
the crown-sphere normal so the runtime sun lights the crown as one volume. Runtime: `engine/impostor.ts`.

## Farmhouse and horizon

```powershell
# Tuscan farmhouse -> frontend/public/planner/buildings/casale.glb (materials by name: wall, stone, roof, wood, shutter, glass)
blender --background --factory-startup --python tools/blender/make_casale.py -- frontend/public/planner/buildings/casale.glb [preview.png]

# distant landscape band (equirectangular, latitudes -24..8 deg, transparent sky) -> convert to WebP for the app
blender --background --factory-startup --python tools/blender/make_horizon.py -- <work>/horizon.png 8192 [calib]
```
`calib` renders a small band with coloured markers (east red, north green, west blue) to check the orientation:
north is at u = 0.5, east at u = 0.75. The app maps it in `engine/Horizon.tsx`. The baked aerial haze (9 km scale)
matches the app fog (`FarmEngine`, linear 150 .. 10500 m), so the edge of the 3D terrain blends into the band.

## Photoreal render («Render foto» in the planner)

The planner exports the scene on screen (`frontend/.../planner/renderExport.ts`: `scene.glb` with its own meshes +
`meta.json` with camera, sun, fog, impostor trees/crops and instanced plants); the backend
(`backend/app/services/render_service.py`, `POST /api/v1/render`) queues it and runs, one job at a time:

```powershell
blender --background --factory-startup --disable-autoexec --python tools/blender/render_scene.py -- <job_dir> <assets_dir> frontend/public/planner
```

`render_scene.py` replaces impostors with the real models (Poly Haven trees from `<assets>/src/<tree>/<tree>_1k.blend`,
crops from `<assets>/crops/*.blend`, built on first use with `make_crops.py`), instances repeated plants with geometry
nodes, grows grass near the farm, adds the terrain grass detail, aerial haze matching the app fog, a single sun (the sky
lights softly, the photographed sky and the horizon band are seen by the camera only) and renders with Cycles (OptiX),
AgX Punchy. The service adds a light grade and a caption («render illustrativo… piante ingrandite ×N… paesaggio
dimostrativo»). Missing tree assets fall back to simple trees. Settings: `RENDER_BLENDER`, `RENDER_ASSETS`
(default `~/agroai-assets`), `RENDER_ALLOW_REMOTE` (default false: localhost only).
Measured on an RTX 3500 Ada laptop: about 1 minute from click to image (1920 px, 128 samples, ~27k real trees).
