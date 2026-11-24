from fastapi import APIRouter

from app.api.v1 import telemetry, devices, farms, alerts, simulation, intelligence, ws, audio, agronomy, ai, vision, deterrent, home, rotation, rotation_plots, rotation_features, render

router = APIRouter(prefix="/api/v1")
router.include_router(telemetry.router, tags=["telemetry"])
router.include_router(devices.router, tags=["devices"])
router.include_router(farms.router, tags=["farms"])
router.include_router(alerts.router, tags=["alerts"])
router.include_router(simulation.router, tags=["simulation"])
router.include_router(intelligence.router, tags=["intelligence"])
router.include_router(audio.router, tags=["audio"])
router.include_router(agronomy.router, tags=["agronomy"])
router.include_router(ai.router, tags=["ai"])
router.include_router(vision.router, tags=["vision"])
router.include_router(deterrent.router, tags=["deterrent"])
router.include_router(home.router, tags=["home"])
router.include_router(rotation.router, tags=["rotation"])
router.include_router(rotation_plots.router, tags=["rotation"])
router.include_router(rotation_features.router, tags=["rotation"])
router.include_router(render.router, tags=["render"])
router.include_router(ws.router, tags=["ws"])
