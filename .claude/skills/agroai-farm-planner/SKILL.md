---
name: agroai-farm-planner
description: Build or change AgroAI's Visual Farm Planner (3D/2D/satellite views of real plots, beds, crops, greenhouses, irrigation, rotation 2026-2030). Use for any work on frontend/src/components/rotation/planner/*, FarmMap, the rotation plots API, plot geometry or crop 3D models.
---

# AgroAI – Visual Farm Planner

The planner is a VIEW and EDITOR of the rotation data. It never owns agronomic logic.

## Golden rules
1. **Independent from AgroVision.** Never touch `backend/app/ml/vision/*`, the v4 plant model, diagnosis APIs.
2. **One agronomic engine.** Crop choice, verdicts, reasons come only from `backend/app/ml/agronomy/rotation*.py`
   through `/api/v1/rotation/*`. The 3D scene may display them, never recompute them.
3. **Everything drawn is data.** Each bed, crop, greenhouse, tank, path maps to a `plot_sections` row, a
   `crop_history` / `planned_crops` row, or `plot_conditions` (irrigation). No decorative objects pretending to be data;
   pure scenery (trees around the farm, sky) is allowed only if visibly not selectable.
4. **No invented numbers.** Heights: FAO-56 Table 12 (`crop_heights.py`). If a value has no source, show
   "non disponibile", never a guess. Row counts / spacings are not shown as agronomic data unless sourced.
5. **Proposals are labelled.** Unsaved plans are "Proposta di AgroAI"; saved plans are "Piano"; history is "Oggi".
6. **Real scale first.** Geometry in metres. Any visual exaggeration (plant size) is shown on screen with its factor.
7. **Demo data only in demo mode.** Never write fake plots or crops to the database from the planner.

See references/ for details: farm-geometry.md, crop-models.md, crop-rotation.md, irrigation.md, performance.md.
