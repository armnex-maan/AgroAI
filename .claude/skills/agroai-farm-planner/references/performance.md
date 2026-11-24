# Performance

- Target: 60 fps desktop, 30 fps mid-range phone. Device pixel ratio capped at 1.5 on phones.
- InstancedMesh for every repeated part; at most ~6000 plants in the whole scene. Large fields use a larger visual
  spacing and bigger plants; the exaggeration factor is shown on screen.
- Lazy-load the planner (`React.lazy`): three.js must not be in the main bundle.
- Dispose geometries/materials on unmount; no per-frame React state updates (use refs in useFrame).
- Textures 1k JPG, repeat-wrapped; one HDRI at 1k for lighting.
- 2D mode = same scene with an orthographic top camera (no second renderer).

## AgroAI Farm Engine (planner/engine/)
- `quality.ts`: profiles high / medium / battery (dpr, shadow map, N8AO, grass, trees, plant budget, plant LOD distance,
  frameloop). "auto" = device guess + drei PerformanceMonitor stepping down; the choice is kept in localStorage.
- `terrain.ts`: TerrainSource interface. "demo" = procedural hills (always labelled as not real data); "dem" = real
  elevation grid (Copernicus GLO-30 / TINITALY) to plug in. The farm zone is always flat at y = 0.
- `Landscape.tsx`: terrain mesh (vertex colours + CC0 grass texture), wind-blown grass (instanced, shader sway),
  forests with 2-level LOD (re-assigned every 0.4 s). `FarmEngine.tsx`: sun + shadows, Sky, fog, HDRI fill, N8AO.
- Global React Query default refetches every 5 s: planner queries MUST set `refetchInterval: false`.
- Dev check: `window.__farmEngine` (fps, draw calls, triangles, shadows) is filled in development builds only.
- Sky = Poly Haven pure-sky HDRI as background + environment (`SKY_HDRI`, `SKY_ROTATION` in FarmEngine.tsx). The sun was
  measured in the file (47.9 deg elevation); `SUN_DIR` is that direction turned by the same rotation, so shadows match the sky.
  Changing the HDRI means re-measuring its sun.
- Post-processing: high = N8AO + light bloom + ACES + saturation/contrast + vignette; medium = grading only (no AO/bloom).
- `engine/Shrubs.tsx`: CC0 bush/herb photoscans scattered just outside the farm (scenery, not selectable); budget
  `shrubs`/`herbs` per profile. Each glTF mesh is one InstancedMesh variant.
- Buildings: one mesh per surface group (wall, plank, metal, roof, metalRoof, plain) with CC0 PBR textures; UVs projected in
  metres (`projectUV` in Structures.tsx, roofs along the slope).
- Measured on Intel UHD (integrated), Nov 2026 after the sky/texture update: high ~23-30 fps / 1.5-1.6 M tris (shadow pass
  included); medium 47 fps / ~0.58 M tris.
- After photo foliage (leaf-card trees, crop carpets): medium 56-57 fps / ~0.52 M tris; high ~24 fps / ~1.37 M tris on
  Intel UHD. Leaf cards cost overdraw (alpha test), not triangles.

## Nov 2026 – countryside, impostors, ultra profile
- Profiles: `ultra` (discrete GPU from the WebGL renderer string: 4096 shadows, full-res N8AO, 26k trees, 70k grass,
  4096 px landcover) / `high` / `medium` (integrated GPUs: Intel UHD/Iris, AMD Radeon Graphics) / `battery`.
  `PerformanceMonitor` starts 9 s after the scene opens (loading and shader compilation must not trigger a downgrade).
- `engine/countryside.ts`: deterministic demo landscape (fields on a jittered grid, woods, olive groves, vineyards,
  hedgerows, white roads) -> one painted landcover texture for the terrain + the impostor trees standing on it.
- Measured Nov 2026, 1672x941, default view: RTX 3500 Ada ultra ~90 fps (~2.9 M tris incl. shadow pass);
  Intel UHD medium ~38 fps. Chrome picks the integrated GPU by default on hybrid laptops
  (`--force_high_performance_gpu` or the Windows graphics setting selects the discrete one).
- Layout: immersive dark planner (`styles/planner.css`, `.vp-dark`): scene full-bleed, glass panels over it.
- Horizon: `engine/Horizon.tsx` draws a Cycles-rendered panorama band (8192 px WebP) on a sphere band that follows the
  camera (transparent sky, no depth write, no fog): distant hills at zero runtime cost. Fog is linear 150..10500 m to match
  the haze baked in the band. Farmhouse («casale» type): `public/planner/buildings/casale.glb` (Blender, AO in vertex colour).

## Photoreal render (Blender Cycles), Nov 2026
- «Render foto» (3D mode only): `renderExport.ts` exports what is on screen (no recomputation): glb of the planner meshes,
  impostor instances as (name, x, y, z, height, turn), other InstancedMeshes as one prototype + world matrices; UI objects
  (lines, MeshBasicMaterial handles, ShaderMaterial points, invisible hit areas, `userData.noExport`) are left out.
- Backend `render_service.py` + `tools/blender/render_scene.py` (see tools/blender/README.md). The planner switches its
  canvas to frameloop "demand" while Blender works (shared GPU): ~1 min per 1920 px image on the RTX 3500 Ada.
- The image is labelled as an illustration (caption burnt in): plant factor and demonstrative landscape, never a photo.
