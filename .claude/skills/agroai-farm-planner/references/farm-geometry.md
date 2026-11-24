# Farm geometry

- Plot traced on the map: `fields.polygon` = GeoJSON Polygon [[lon, lat]...] plus `origin` [lon0, lat0] (north-west
  corner) and `k` [kx, ky] metres per degree. Real area: spherical formula in `backend/app/ml/agronomy/geo.py`
  (same as Turf.js `area`).
- Local editor grid: metres, **x to the east, y to the south**, origin = north-west corner of the bounding box.
  `fields.outline` holds the plot shape in this grid; `width_m` / `length_m` are the bounding box.
- Sections (`plot_sections`): axis-aligned rectangles x, y, w, h in the same grid; real area = rectangle clipped to the
  outline (`geo.area_in`, frontend `clipToRect` in `rotation/plotGeo.ts`).
- 3D world: metres, X east, Y up, Z south. Plot local (x, y) -> world (offset.x + x, 0, offset.z + y), where the plot
  offset comes from its `origin` relative to the farm reference point (first traced plot), using that plot's `k`.
- Plots without a map boundary are placed in a row to the east, 10 m apart, and labelled "non tracciato".
- Auto split: `POST /rotation/plots/{id}/auto-layout` (equal real area strips, paths 0.6 m garden / 3 m field).

## Farm elements (phase 3)
- Table `farm_features` (alembic 0006): kind, name, GeoJSON geometry in WGS84, props. API `/api/v1/rotation/features`
  (GET list + kinds spec + FAO tree heights, POST, PUT, DELETE). Validation per kind in `rotation_features.py` (SPEC):
  building/tank/well = Point, road/pipe/hedge = LineString, orchard/vineyard/pond = Polygon. Unknown props are dropped,
  numbers out of range are refused, missing numbers stay empty (the 3D shows an indicative layout and says so).
- Farm frame conversion: `toWorld` / `toLonLat` in `planner/Structures.tsx`, reference = first traced plot (origin, k).
  No traced plot -> elements cannot be placed (the UI explains why).
- Orchard / vineyard trees: GLB in `public/planner/trees` (same LOD contract), heights from FAO-56 Table 12
  (`crop_heights.TREE_HEIGHT_M`). No sourced bloom/fruit calendar: with a month selected, fruits are hidden.

## Interactive editor (phase 4)
- Tool «Modifica forme» (move icon): handles on the selected section (yellow = move, white = resize corners/edges) or farm
  element (yellow = move, white = vertices). `planner/Editor.tsx` (SectionGizmo, FeatureGizmo): drag on the ground plane,
  snap 10 cm, clamped inside the plot bbox, camera controls paused while dragging; handle size constant on screen.
- Sections are edited as DRAFTS: `VisualPlanner` keeps `Snap { edits, layouts }` in the undo/redo stack; `farmV` = farm
  with draft sections. New parts get `tmp-…` ids; «Salva progetto» PUTs `/plots/{id}/layout` first (ids keep history), maps
  tmp ids to the returned ones, then saves plans (parts that no longer exist fall back to the whole plot).
- New parts: palette «Parti di un appezzamento» -> tap two opposite corners inside a plot (`placingRef` avoids lost taps).
- Rows declared by the farmer: `plot_sections.row_spacing_m / plant_spacing_m / row_dir` (alembic 0007, validated
  0.1-20 m / 0.05-20 m / "x"|"y"); API returns `rows` only when spacing is declared. The 3D uses the declared spacing
  when it is wider than the (exaggerated) plants; `rowsAlongY` follows `row_dir`.
- Moving crops: Props «Sposta questa coltura in…» moves or swaps crops between parts for the chosen year; both are
  re-checked by the rotation engine (`/check`).
- Farm elements move/reshape saves at once (PUT feature geometry). New kind `sprinkler` (Point; type, radius_m, flow_l_h):
  wetted circle drawn only when the radius is declared.

## AI Farm Layout Generator (phase 6)
- `backend/app/ml/agronomy/layout_generator.py` (pure geometry): `variants()` -> up to 3 layouts: «Strisce lungo il lato
  lungo», «Strisce lungo il lato corto», «Serra a nord e strisce» (only with greenhouse_m2; north side because its shadow
  falls north, northern hemisphere) + optional water point at the start of the middle path. Strips have equal REAL area
  inside the outline; strips narrower than 1 m are not offered. Parts default = wanted crops + 2 (3..8) and path width
  0.6 m garden / 3 m field: both labelled in `why` as AgroAI choices, not norms.
- `POST /rotation/plots/{id}/layout-ai` {goals?, parts?, path_m?, greenhouse_m2?, water_point}: for each variant runs
  `rotation_planner.plan_plot` (crops only from the rotation engine; new parts use the whole-plot history) and returns
  metrics (parts, growing m², path share, verdict counts, share of wanted crops placed, unplaced) and a comparison score
  (60% rules / 30% wanted placed / 10% ground not lost in paths; ties -> fewer paths), stated as not agronomic data.
  Writes NOTHING.
- Frontend `planner/AiGenerator.tsx` (lazy): options, variant cards with a top-view sketch, reasons, «Prova nel 3D» =
  pushes the layout + its plan as unsaved draft (tmp ids, proposed flag) -> undo or «Salva progetto» (phase 5 save maps ids).
