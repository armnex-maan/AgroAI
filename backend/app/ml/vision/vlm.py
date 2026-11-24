"""Vision-language assessment of a plant photo via the configured LLM provider.

The model must return JSON and may only name causes from the knowledge base.
Output is a preliminary visual assessment, never a confirmed diagnosis.
"""
from __future__ import annotations

import base64
import json
import re

import httpx

from app.config import settings
from app.ml.vision.causes import CAUSES
from app.ml.vision.differential import FEATURES, ORGANS
from app.services.llm_service import LLMUnavailable

LIKELIHOODS = ("high", "medium", "low")


OBS_FIELDS = ("fruit_location", "texture", "colour", "shape", "leaves", "stems", "sun_exposed", "mould", "wilting")


def _prompt(crop: str | None, color: dict, ctx: dict) -> str:
    causes = "\n".join(f"- {cid}: {c['name']} — {c['signs']}" for cid, c in CAUSES.items())
    obs_schema = ",\n".join(f'    "{f}": "{"|".join(FEATURES[f])}|unknown"' for f in OBS_FIELDS)
    return f"""You are a cautious plant pathologist. Look at the photo and return ONLY a JSON object:
{{
  "observations": {{
    "organs": ["organs WITH symptoms, any of: {"|".join(ORGANS)}"],
{obs_schema}
  }},
  "is_plant_image": true/false,
  "plant_guess": "crop or plant name, or null if unsure",
  "plant_part": "leaf|fruit|stem|whole plant|field|other",
  "image_quality": "good|fair|poor",
  "visible_symptoms": ["short factual descriptions of what is visible, in {settings.ai_language}"],
  "overall": "looks_healthy|mild_symptoms|marked_symptoms|unclear",
  "causes": [{{"id": "<one id from the list>", "likelihood": "high|medium|low", "why": "visible evidence, in {settings.ai_language}"}}],
  "plant_guess" and "plant_part" values: write them in {settings.ai_language} too,
  "summary": "2-3 sentences for the farmer, in {settings.ai_language}",
  "cannot_tell": "what cannot be determined from a photo, in {settings.ai_language}"
}}
Rules for "observations": describe only what is VISIBLE, use "unknown" when you cannot see it.
- fruit_location: stem_end = upper part / shoulders near the stalk and calyx; blossom_end = the opposite end
  (bottom, where the flower was); sun_side = only the side facing the sun. Look carefully where the calyx is.
- texture cannot be touched: estimate from the look (greasy/marbled sheen, sunken, papery, wet rot).
- leaves / stems: "affected" if they show lesions, blight or dead tissue; "healthy" if visible and green.
Rules for "causes": choose at most 4, ONLY these ids, and consider the differential diagnosis
(e.g. for dark lesions on fruit compare blossom_end_rot, late_blight, heat_sunscald, anthracnose,
early_blight, grey_mould): the LOCATION, shape and texture of lesions decide between them.
Never call blossom_end_rot unless the lesion is at the blossom end. In "why" cite the visible evidence for
AND against. Base causes ONLY on the image: do not use soil-moisture numbers, AGROAI interprets sensors itself.
{causes}
Use "high" only when the visible pattern is typical and clear. Several causes look alike in photos
(e.g. nutrient deficiencies vs. water stress): say so in cannot_tell. Never claim a confirmed diagnosis.
Farmer says the crop is: {crop or "not specified"}.
Colour measurement of the photo (fractions of leaf area): {json.dumps({k: color[k] for k in ("healthy_green", "chlorotic_yellow", "necrotic_brown", "whitish_coating") if k in color})}.
If whitish_coating is above 0.02, look closely for a grey-white film or patches on the leaf surface and say
whether it looks like powdery mildew, dust/spray residue or light reflection — and if you cannot tell, say so.
Inspect the whole plant in the photo (leaves, stems, fruits), not only the most obvious damage: several
problems can be present at once."""


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise LLMUnavailable("vision model did not return JSON")
    data = json.loads(m.group(0))
    causes = []
    for c in data.get("causes") or []:
        cid = str(c.get("id", "")).strip()
        if cid in CAUSES and cid not in {x["id"] for x in causes}:
            lk = c.get("likelihood") if c.get("likelihood") in LIKELIHOODS else "low"
            causes.append({"id": cid, "likelihood": lk, "why": str(c.get("why", ""))[:400]})
    data["causes"] = causes[:4]
    raw_obs = data.get("observations") if isinstance(data.get("observations"), dict) else {}
    obs: dict = {"organs": [o for o in (raw_obs.get("organs") or []) if o in ORGANS]}
    for f in OBS_FIELDS:
        v = raw_obs.get(f)
        if isinstance(v, str) and v in FEATURES[f]:
            obs[f] = v
    data["observations"] = obs
    data["visible_symptoms"] = [str(s)[:200] for s in (data.get("visible_symptoms") or [])][:8]
    return data


async def assess(jpeg: bytes, crop: str | None, color: dict, ctx: dict) -> dict:
    if settings.ai_provider != "nvidia" or not settings.nvidia_api_key:
        raise LLMUnavailable("intelligenza artificiale per le immagini non configurata (serve AI_PROVIDER=nvidia)")
    b64 = base64.b64encode(jpeg).decode()
    body = {
        "model": settings.nvidia_model, "max_tokens": 1800, "temperature": 0.1,
        "chat_template_kwargs": {"enable_thinking": settings.nvidia_thinking},
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": _prompt(crop, color, ctx)},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
    }
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{settings.nvidia_base_url}/chat/completions", json=body,
                             headers={"Authorization": f"Bearer {settings.nvidia_api_key}"})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"].get("content") or ""
    except httpx.HTTPError as exc:
        detail = exc.response.text[:200] if isinstance(exc, httpx.HTTPStatusError) else str(exc)
        raise LLMUnavailable(f"vision model call failed: {detail}") from exc
    try:
        return _parse(text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMUnavailable(f"could not parse vision model answer: {exc}") from exc
