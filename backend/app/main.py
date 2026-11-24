from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.api.v1 import router as v1_router
from app.schemas.common import Health

app = FastAPI(
    title="AGROAI",
    description="Agricultural Intelligence Platform — IoT, bioacoustics, computer vision, prediction.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(v1_router)


@app.on_event("startup")
def _warm_models() -> None:
    import threading

    def warm():
        if settings.yamnet_enabled:
            from app.ml.audio import yamnet
            yamnet.status()
        if settings.perch_enabled:
            from app.ml.audio import perch, taxonomy
            from app.core.database import SessionLocal
            from app.models import Farm
            perch.status()
            if settings.species_location_filter:
                with SessionLocal() as db:
                    farms = [(f.latitude, f.longitude) for f in db.query(Farm).all() if f.latitude is not None]
                for lat, lon in farms:
                    taxonomy.local_species(lat, lon)  # cached species list of each farm's area

    threading.Thread(target=warm, name="model-warmup", daemon=True).start()


@app.on_event("startup")
def _sync_rotation_rules() -> None:
    """Keep regulation_sources / rotation_rules equal to the reviewed rules in rotation_rules.py."""
    from app.core.database import SessionLocal
    from app.services import rotation_store
    try:
        with SessionLocal() as db:
            rotation_store.sync_rules(db)
    except Exception as e:  # tables not created yet (fresh DB before migrations): the API still starts
        print(f"rotation rules not synced: {e.__class__.__name__}")


@app.get("/health", response_model=Health, tags=["meta"])
def health() -> Health:
    return Health(
        status="ok",
        version=__version__,
        simulation_enabled=settings.simulation_enabled,
        ai_provider=settings.ai_provider,
    )
