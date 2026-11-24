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
