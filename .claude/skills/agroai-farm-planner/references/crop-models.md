# Crop models

- Procedural geometry in `planner/plants.ts`, one model per crop or crop group, built from a few low-poly parts
  (stem, leaves, fruit/head). Each part is an InstancedMesh: all plants of a bed share it.
- Group (from rotation.CROPS): frutto, foglia, radice, legume, cereale. Special models: tomato, pepper, eggplant
  (bush + fruits), zucchini/pumpkin/melon (wide leaves + fruits on ground), lettuce/cabbage (head), maize, sunflower,
  wheat/barley (dense ears), onion/garlic/leek (upright blades), carrot/radish (feathery tuft), beans/peas (climbing bush).
- Height = FAO-56 Table 12 mean maximum height (`height_m` in the crop catalog). Crops missing from the table are
  drawn at 0.3 m and the panel says the height is not available.
- Colours: crop colour from `types.ts cropColor`, natural tints for leaves (greens) and fruits (real colours).
- Assets in `frontend/public/planner` are CC0 from Poly Haven (see CREDITS.md): sky, PBR textures (soil, gravel, roof tiles,
  plaster, corrugated iron, planks) and two shrub photoscans. Photoscanned trees are too heavy (millions of triangles). Any new download needs the user's
  approval (file, source, size) and a CREDITS line. Prefer < 2 MB per file; no 50+ MB models.

## Crop library (phase 2)
- Source of truth: `frontend/scripts/crops/crops.mjs` (botanical generators) + `geometry.mjs` (blade, palmate leaf,
  tube, lathe). Build: `node scripts/build-crop-models.mjs` -> `public/planner/crops/<crop>.glb` + `planner/crops/manifest.json`.
- GLB contract: nodes `LOD0` (near, <= ~3k tris), `LOD1` (middle, <= ~650), `LOD2` (far, <= 20); optional `*_green`
  variants (cereals before ripening). Meshes named by part: leaves, stem, fruit, flower, ear, cob, silk, tassel, head, root.
  Height normalised to 1 m (scaled at runtime by FAO-56 height x stage x visual factor). An artist model in Blender with
  the same names replaces a file with no code change.
- Dedicated models: tomato, pepper, eggplant, potato, zucchini, pumpkin, cabbage, lettuce, carrot, bean, wheat, barley,
  maize; aliases: green_bean -> bean, cucumber -> zucchini. Other crops use the procedural fallback in plants.ts.
- Growth stage from the indicative calendar (`/rotation/calendar`, `stageFor` in cropLibrary.ts): young 0.35x (no
  fruit/flowers), growing 0.75x (flowers, green ears), mature 1x; "none"/"harvested" = bare soil. Month 0 = full season.
- Runtime: `CropField.tsx` splits a bed into ~400-plant blocks; each block picks LOD0/1/2 by camera distance.

## Photographic foliage (Nov 2026)
- Woods and hedges: crowns of leaf cards (`engine/foliage.ts`, `leafCloud` + `useLeafMaterial`): quads with the CC0 leaf
  atlas (diffuse + alpha mask), spherical normals, per-tree tint via instanceColor. Pines keep cones.
- Beds: `CropCarpet` in Scene.tsx + `canopy.ts`: 1-3 stacked layers (battery/medium/high) textured with rows of photo
  leaves tinted per crop (`LOOK`), fruit colour only at maturity. Rows use the same direction and spacing as the 3D plants.
  Far away (LOD2) the 3D plants are hidden and the carpet stands for them (`farHidden` in CropField).
- Crop and orchard leaves: triplanar photo leaf detail (`leafDetail.ts`), because the GLBs have no UVs. Brightness-only:
  it never changes the crop colour.
- Near plants (LOD0 150 cards, LOD1 40; fruit trees x2): `photoLeaves.ts` replaces the "leaves" mesh with photographic
  leaf cards scattered on that mesh's own surface (area-weighted), facing like it and taking its vertex colour, so the
  botanical shape and the crop colour stay the model's. Styles: "leaf" (single leaves: lettuce, cabbage, cucurbits),
  "spray" (leafy twigs: solanaceae, potato, bean, carrot, orchards, vines); cereals/maize keep their blades.
