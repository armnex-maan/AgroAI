"""Pluggable LLM layer: turns deterministic engine output into plain-language advice.

The LLM never produces measurements or decisions; it only rewrites data it is given,
and every call falls back to a deterministic template if the provider fails.
Providers: none | anthropic | ollama | nvidia (OpenAI-compatible NIM API).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import OrderedDict

import httpx

from app.config import settings

log = logging.getLogger("agroai.llm")

_CACHE: "OrderedDict[str, str]" = OrderedDict()
_CACHE_MAX = 128

GROUNDING = (
    "You are AGROAI, an agronomy assistant for farmers. Use ONLY the data in the user message. "
    "Never invent measurements, yields, prices, product names or doses. If something is not in the data, "
    "say it is not known. Present soil and climate figures as estimates to be verified in the field. "
    "Respect every legal status in the data (never suggest a prohibited species). "
    "Write plain text for a farmer: short paragraphs or simple bullet points, no markdown headings. "
    "Answer in {lang}."
)


class LLMUnavailable(RuntimeError):
    pass


def _strip_reasoning(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


async def complete(user: str, max_tokens: int = 700, system: str | None = None, cache: bool = True) -> str:
    """Raw completion from the configured provider. Raises LLMUnavailable on any failure."""
    provider = (settings.ai_provider or "none").lower()
    system = system or GROUNDING.format(lang=settings.ai_language)
    key = hashlib.sha256(f"{provider}|{settings.ai_model}|{system}|{user}|{max_tokens}".encode()).hexdigest()
    if cache and key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]

    try:
        async with httpx.AsyncClient(timeout=90) as c:
            if provider == "nvidia":
                if not settings.nvidia_api_key:
                    raise LLMUnavailable("NVIDIA_API_KEY not set")
                r = await c.post(
                    f"{settings.nvidia_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
                    json={"model": settings.nvidia_model, "max_tokens": max_tokens, "temperature": 0.2,
                          # The rules engine already did the reasoning; the LLM only writes it up.
                          # With thinking on, Nemotron can spend the whole budget before answering.
                          "chat_template_kwargs": {"enable_thinking": settings.nvidia_thinking},
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": user}]},
                )
                r.raise_for_status()
                choice = r.json()["choices"][0]
                text = choice["message"].get("content") or ""
                if not text.strip() and choice.get("finish_reason") == "length":
                    raise LLMUnavailable("nvidia: token budget used up by reasoning before the answer "
                                         "(set NVIDIA_THINKING=false or raise max_tokens)")
            elif provider == "anthropic":
                if not settings.anthropic_api_key:
                    raise LLMUnavailable("ANTHROPIC_API_KEY not set")
                r = await c.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
                    json={"model": settings.anthropic_model, "max_tokens": max_tokens, "system": system,
                          "messages": [{"role": "user", "content": user}]},
                )
                r.raise_for_status()
                text = "".join(b.get("text", "") for b in r.json().get("content", []))
            elif provider == "ollama":
                r = await c.post(f"{settings.ollama_url}/api/chat", json={
                    "model": settings.ollama_model, "stream": False,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                r.raise_for_status()
                text = r.json().get("message", {}).get("content", "")
            else:
                raise LLMUnavailable("AI provider is 'none'")
    except LLMUnavailable:
        raise
    except Exception as exc:
        detail = exc.response.text[:200] if isinstance(exc, httpx.HTTPStatusError) else str(exc)
        log.warning("LLM call failed (%s): %s", provider, detail)
        raise LLMUnavailable(f"{provider}: {type(exc).__name__}: {detail}") from exc

    text = _strip_reasoning(text)
    if not text:
        raise LLMUnavailable(f"{provider}: empty answer")
    _CACHE[key] = text
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return text


def _template(findings: list[str], recs: list[str]) -> str:
    parts = ["Situazione:"] + [f"- {f}" for f in findings]
    if recs:
        parts += ["", "Cosa fare:"] + [f"- {r}" for r in recs]
    return "\n".join(parts)


async def explain(findings: list[str], recommendations: list[str]) -> str:
    """Field-status narrative; deterministic template if the LLM is off or fails."""
    baseline = _template(findings, recommendations)
    try:
        return await complete(
            "Explain this field status to the farmer in at most 5 sentences, keeping every number exactly "
            "as given:\n\n" + baseline, max_tokens=500)
    except LLMUnavailable:
        return baseline


def _site_digest(a: dict) -> dict:
    c, s = a["climate"], a["soil"]
    crop = lambda r: {"crop": r["name"], "class_irrigated": r["class_irrigated"],  # noqa: E731
                      "class_rainfed": r["class_rainfed"], "irrigation_need_mm": r["irrigation_need_mm"],
                      "limiting_factor": r["limiting_factor"], "notes": r["notes"] or None}
    return {
        "location": a["location"],
        "climate_estimate": {"period": c["period"], "annual": c["annual"],
                             "summer_season": c["seasons"]["summer"], "gdd": c["gdd"]},
        "soil_estimate": {"texture": s["texture"], "ph": s["ph"], "ph_source": s["ph_source"],
                          "organic_carbon_g_kg": s["soc_g_kg"], "source": s["source"]},
        "best_crops": [crop(r) for r in a["crops"][:8]],
        "least_suitable": [crop(r) for r in a["crops"][-3:]],
        "cost_tips": [{"title": t["title"], "why": t["why"], "action": t["action"]} for t in a["cost_tips"]],
        "rice_integrated_systems": [{"name": x["name"], "legal_status": x["legal"]["status"],
                                     "legal_note": x["legal"]["note"]} for x in a["rice"]["systems"]],
        "warnings": a["warnings"],
        "method_limits": a["method"]["Limiti"],
    }


async def advise_site(assessment: dict) -> str:
    digest = json.dumps(_site_digest(assessment), ensure_ascii=False)
    return await complete(
        "Here is the AGROAI assessment of a farm site (JSON). Write practical advice for the farmer:\n"
        "1) which 3-4 crops fit best and why (cite the limiting factors and irrigation need),\n"
        "2) the 3 most useful ways to cut costs on this site,\n"
        "3) natural pest control and, only if rice is suitable, which rice co-culture is legal here,\n"
        "4) what to verify before deciding (soil test, local advisors).\n"
        "Keep it under 250 words.\n\nDATA:\n" + digest,
        max_tokens=1400,
    )


async def status() -> dict:
    t = time.time()
    try:
        reply = await complete("Reply with exactly: OK", max_tokens=200, cache=False,
                               system="You are a connectivity check. Reply with exactly: OK")
        return {"provider": settings.ai_provider, "model": settings.ai_model, "ok": True,
                "reply": reply[:80], "latency_s": round(time.time() - t, 2)}
    except LLMUnavailable as exc:
        return {"provider": settings.ai_provider, "model": settings.ai_model, "ok": False, "error": str(exc)}
