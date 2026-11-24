# Irrigation, greenhouses, paths

- Irrigation type comes from `plot_conditions.irrigation` (drip | sprinkler | furrow | manual | none). The scene draws
  drip lines along the rows (drip), sprinkler heads in the beds (sprinkler), furrows (furrow), nothing otherwise.
  It never adds irrigation the farmer did not declare.
- Section kinds: bed, path, access, water (tank / water point), no_crop, shade, greenhouse. A greenhouse is a section:
  crops planned in it are drawn under the tunnel.
- Paths and accesses: gravel colour, slightly below the beds.
- Sprinkler heads show rotating water jets (SprinklerJets) only when the quality profile has wind/animation on.
- Irrigation mains are `pipe` features (buried = dashed blue line, surface = grey pipe), drawn only if the farmer adds them.

## Irrigation advice and demo (Nov 2026)
- `backend/app/ml/agronomy/irrigation.py`: Kc ini/mid/end from FAO-56 Table 12 (same table as heights; every crop with a
  FAO height has a Kc; ranges -> middle value, noted), FAO TM4 field efficiencies (drip 0.90, sprinkler 0.75, surface
  0.60). Months in field from `rotation_planner.CALENDAR`; stages split evenly (indicative, stated). Need = Kc × ET0 −
  0.8 × rain (Open-Meteo ERA5 multi-year monthly means at the farm location, cached 6 h). System suggestion is level
  «suggerimento» (no source claimed) and is shown next to the system the farmer declared.
- `POST /rotation/plots/{id}/irrigation {year, assignments}` -> per bed: kc, months (stage, kc, et0, etc, rain_eff,
  net_mm, liters_week, gross with efficiency), peak, season_net_mm, sources, notes. No location -> Kc only, says why.
- Frontend: `IrrigationPanel.tsx` in Props («Impianti»), `IrrigationDemo.tsx` (drip drops + wet bulbs, sprinkler jets +
  wetted circle, furrow water advancing) for the beds of one plot; during the demo the foliage carpet is hidden to show
  the water. Labelled «animazione, non un calcolo idraulico».
- New farm elements (`Equipment.tsx`, kinds in rotation_features SPEC): greenhouse (tunnel / vetro / ombraio), net
  (antigrandine / ombreggiante / antinsetto), fence, equipment (trattore, motocoltivatore, atomizzatore, rimorchio, pompa,
  centralina), beehive, compost, solar. Pea has its own GLB (scripts/crops/crops.mjs `pea`).
