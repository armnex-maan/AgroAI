from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://agroai:agroai_dev@localhost:5432/agroai"
    redis_url: str = "redis://localhost:6379/0"

    api_secret: str = "change-me"
    device_hmac_secret: str = "device-secret"
    cors_origins: str = "http://localhost:5173"
    public_api_url: str = ""

    media_root: str = str(BACKEND_DIR / "media")

    simulation_enabled: bool = True
    simulation_interval_seconds: int = 10
    simulation_default_scenario: str = "healthy"

    ai_provider: str = "none"  # none | anthropic | ollama | nvidia
    ai_language: str = "English"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-5-5"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    nvidia_api_key: str | None = None
    nvidia_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_thinking: bool = False

    @property
    def ai_model(self) -> str | None:
        return {"anthropic": self.anthropic_model, "ollama": self.ollama_model,
                "nvidia": self.nvidia_model}.get(self.ai_provider)

    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    soilgrids_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"

    yamnet_enabled: bool = True
    perch_enabled: bool = True
    species_location_filter: bool = True
    birdnet_enabled: bool = False
    # Score thresholds are NOT calibrated probabilities; they only bucket results.
    identification_probable: float = 0.5
    identification_possible: float = 0.2
    custom_model_min_confidence: float = 0.6

    # Photoreal render of the Visual Planner (Blender Cycles). Empty = auto-detect Blender / ~/agroai-assets.
    render_blender: str = ""
    render_assets: str = ""
    render_allow_remote: bool = False      # the render runs a local process on the GPU: localhost only by default

    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_url_sync(self) -> str:
        return self.database_url

    @property
    def media_path(self) -> Path:
        p = Path(self.media_root)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
