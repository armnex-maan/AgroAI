from fastapi import APIRouter

from app.config import settings
from app.services import llm_service

router = APIRouter()


@router.get("/ai/config")
def ai_config():
    return {"provider": settings.ai_provider, "model": settings.ai_model, "language": settings.ai_language,
            "key_configured": bool({"nvidia": settings.nvidia_api_key,
                                    "anthropic": settings.anthropic_api_key,
                                    "ollama": "local"}.get(settings.ai_provider))}


@router.post("/ai/test")
async def ai_test():
    return await llm_service.status()
