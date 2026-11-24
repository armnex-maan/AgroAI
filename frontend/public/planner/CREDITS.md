# Visual Farm Planner – asset credits

All files in this folder come from Poly Haven (https://polyhaven.com) and are released under
CC0 1.0 (public domain): free for any use, attribution not required but given here.

| File | Poly Haven asset | Use |
|---|---|---|
| dirt_aerial_02_diff_1k.jpg, _nor_gl_1k.jpg, _rough_1k.jpg | Dirt Aerial 02 (texture, 1k) | tilled soil of beds |
| aerial_grass_rock_diff_1k.jpg, _nor_gl_1k.jpg, _rough_1k.jpg | Aerial Grass Rock (texture, 1k) | grass around plots |
| alps_field_1k.hdr | Alps Field (HDRI, 1k) | former sky (kept, no longer used) |
| kloofendal_48d_partly_cloudy_puresky_2k.hdr | Kloofendal 48d Partly Cloudy (Pure Sky) (HDRI, 2k) | sky with real clouds and ambient light |
| farm_soil_diff/nor_gl/rough_1k.jpg | Farm Soil (texture, 1k) | tilled soil of beds |
| gravel_road_diff/nor_gl/rough_1k.jpg | Gravel Road (texture, 1k) | paths, accesses, gravel and dirt roads |
| clay_roof_tiles_diff/nor_gl/rough_1k.jpg | Clay Roof Tiles (texture, 1k) | roofs of farmhouse, barn, stable |
| plastered_wall_diff/nor_gl/rough_1k.jpg | Plastered Wall (texture, 1k) | farmhouse and stable walls |
| corrugated_iron_diff/nor_gl/rough_1k.jpg | Corrugated Iron (texture, 1k) | warehouse walls and metal roofs |
| weathered_planks_diff/nor_gl/rough_1k.jpg | Weathered Planks (texture, 1k) | barn and shed wooden walls |
| shrubs/shrub_03/ | Shrub 03 (model, glTF 1k) | wild bushes around the farm (scaled up, scenery only) |
| shrubs/shrub_sorrel_01/ | Shrub Sorrel 01 (model, glTF 1k) | herb clumps near the farm (scaled up, scenery only) |
| foliage/tree_small_02_leaves_diff/alpha/nor_gl_1k.jpg | Tree Small 02 (leaf maps only, 1k) | leaf cards of woods and hedges, crop foliage rows |
| foliage/tree_small_02_branch_diff/nor_gl_1k.jpg | Tree Small 02 (bark maps only, 1k) | reserved for bark |
| foliage/island_tree_02_leaves_diff/alpha/nor_gl_1k.jpg | Island Tree 02 (leaf maps only, 1k) | reserved for a second leaf type |

Downloaded 2026-11-22 from https://dl.polyhaven.org with the user's approval (first 7 files; then the sky, 6 texture
sets and 2 shrub models, about 20 MB; then 8 leaf/bark maps, 2.9 MB; all approved the same day).
Crops, rows, greenhouses, tanks, orchard/vineyard trees and woods are procedural geometry built in code. Poly Haven tree
photoscans (0.3-17 million triangles each) were not used: too heavy for a browser scene with hundreds of trees.

## Impostors (impostors/, Nov 2026)

Baked offline in Blender 5.3 / Cycles with `tools/blender/bake_impostor.py` (64 views of the upper hemisphere,
colour + normal atlases, WebP). Each tree is drawn as one quad at runtime, so the full photoscans can be used.

| File | Source | Use |
|---|---|---|
| broadleaf_a_* | Poly Haven "Tree Small 02" (model, CC0, 1.15 M polygons) | woods and field trees (scenery) |
| broadleaf_b_* | Poly Haven "Island Tree 01" (model, CC0, 0.8 M polygons) | woods, hedgerows (scenery and hedge features) |
| broadleaf_c_* | Poly Haven "Island Tree 03" (model, CC0, 1.06 M polygons) | woods, hedgerows, fruit orchards (drawing of a fruit tree) |
| olive_a_* | Poly Haven "Island Tree 02" (model, CC0, 0.54 M polygons) | olive groves of the countryside, olive orchards |
| fruit_red_*, fruit_orange_* | Poly Haven "Island Tree 01" + AgroAI fruit spheres (bake option FRUIT) | orchards in the full-season view (apple/cherry/plum red, peach/apricot/citrus orange) |
| crop_lettuce, crop_cabbage, crop_tomato(_green), crop_eggplant(_green) | AgroAI procedural plants, `tools/blender/make_crops.py` | crop beds (fruit only in the mature variant) |

The four Poly Haven models (blend, 1k textures, about 320 MB) were downloaded on 2026-11-24 with the user's approval
for baking only; they are not shipped. The atlases add about 13 MB to `public/planner`.

## Farmhouse and horizon (Nov 2026)

| File | Source | Use |
|---|---|---|
| buildings/casale.glb | AgroAI, modelled in Blender by `tools/blender/make_casale.py` (ambient occlusion baked in Cycles) | farm element «Edificio – casale» (scaled to the declared size; textured with the CC0 sets above) |
| horizon/horizon.webp | AgroAI, rendered in Blender/Cycles by `tools/blender/make_horizon.py`, lit with the Kloofendal sky above | distant hills beyond the 3D terrain (demonstrative scenery, not real data) |
