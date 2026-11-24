# Rotation in the planner

- Year strip: season_year ("Oggi", from crop_history) + next 4 years.
- Per year and plot: saved plan (`plans` in GET /rotation/farm, rows of planned_crops) else the proposal from
  `POST /rotation/plots/{id}/plan` (cache it with React Query; label it "Proposta").
- Changing a crop by hand: `POST /rotation/plots/{id}/check` with the earlier planned years, then re-check the later
  years of the same bed (see PlanView). Store `manual: true`.
- Saving: `PUT /rotation/plots/{id}/plans/{year}` for each year; the server fills missing verdicts.
- Rule levels shown with their badge: obbligatoria / disciplinare / buona pratica / suggerimento AI.
  Never show a recommendation as mandatory.

## Project save and versions (phase 5)
- «Salva progetto» = ONE request `PUT /api/v1/rotation/project` {layouts, plans, goals}: one transaction, all or nothing
  (unknown plot -> 404, bad part kind -> 400, nothing written). Drawings first (`_apply_layout` returns sent id -> saved
  id, so `tmp-…` parts keep their plans), then plans (`_apply_plan`, refresh_area: area = real area of the part as drawn
  now; a part not in the plot -> whole plot; missing verdict -> checked by the engine).
- Every save stores a `planner_revisions` row (alembic 0008): snapshot of drawings + plans of every plot (never crop
  history). The very first save also stores «Situazione prima del primo salvataggio». Max 30 kept.
  `GET /rotation/project/revisions`, `POST /rotation/project/revisions/{id}/restore` (years not in the version are
  removed; plots deleted since then are skipped and counted; a restore is itself a new version).
- Old per-plot endpoints (`/plots/{id}/layout`, `/plots/{id}/plans/{year}`) stay for the 2D editor and other clients.
- Unsaved planner changes are kept in localStorage `agroai.planner.draft.<farmId>` (offer «Riprendi / Scarta» on next
  open; removed when saved or fully undone) and a beforeunload warning protects them.
