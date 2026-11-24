import pytest

from app.config import settings
from app.services import llm_service


def test_ai_config_hides_key(client):
    body = client.get("/api/v1/ai/config").json()
    assert body["provider"] == "none"
    assert "nvapi" not in str(body)


def test_ai_advice_requires_provider(client):
    r = client.post("/api/v1/agronomy/ai-advice", json={"lat": 45.27, "lon": 8.5})
    assert r.status_code == 409


async def test_explain_falls_back_to_template():
    out = await llm_service.explain(["Soil moisture low (18.0%)."], ["Plan irrigation within 24h."])
    assert "18.0%" in out and "Plan irrigation" in out


async def test_nvidia_without_key_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "nvidia")
    monkeypatch.setattr(settings, "nvidia_api_key", None)
    with pytest.raises(llm_service.LLMUnavailable):
        await llm_service.complete("hi", cache=False)


def test_reasoning_tags_are_stripped():
    assert llm_service._strip_reasoning("<think>secret plan</think>\nCiao") == "Ciao"
