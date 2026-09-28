"""
Wavelength -- end-to-end pipeline (Session 4).

Flow: brand + region input -> (stub) trend grounding -> caption generation -> response

Generation is now a REAL LLM call when LLM_API_KEY is set (see llm.py and
.env.example), and falls back to the template stub when it is not, so the
whole pipeline runs for a teammate without a key.

Trend retrieval is still a stub -- Session 5 wires in real regional signals
in trend_retrieval.py.
"""

import re
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import llm
from trend_retrieval import get_mock_context

from evaluator import EvaluateRequest, EvaluateResponse, run_evaluation

load_dotenv()

app = FastAPI(title="Wavelength API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = (
    "You are a regional marketing copywriter. You write short-form copy that "
    "sounds native to one specific market, not like US copy that was translated. "
    "You never invent facts about the brand. You output nothing but the copy."
)


class CaptionRequest(BaseModel):
    brand_name: str
    industry: str
    tone: str  # e.g. "playful", "premium", "no-nonsense"
    country: str  # "US" or "India"
    region: str  # e.g. "Texas", "Maharashtra"
    city: Optional[str] = None  # e.g. "Austin", "Mumbai"
    content_type: str  # "caption" | "notification" | "meme"
    num_candidates: int = Field(default=5, ge=1, le=10)


class CaptionResponse(BaseModel):
    candidates: list[str]
    grounding_context: dict
    note: str
    source: str  # "llm" | "stub" -- which path produced these candidates
    model: Optional[str] = None  # the model that produced them, when source == "llm"


def build_prompt(req: CaptionRequest, context: dict) -> str:
    location = ", ".join(p for p in [req.city, req.region, req.country] if p)
    return f"""Write {req.num_candidates} distinct {req.content_type} options for this brand and market.

Brand: {req.brand_name}
Industry: {req.industry}
Tone: {req.tone}
Market: {location}

Local signals retrieved for this market. Use one only where it genuinely fits
the brand; ignore any signal that does not:
- Trend: {context.get("trend")}
- Weather: {context.get("weather")}

Rules:
- One option per line, numbered 1. to {req.num_candidates}.
- Under 15 words each.
- No hashtags, no emoji, no explanation before or after the list.
"""


_NUMBERING = re.compile(r"^\s*\d+[\.\)]\s*")


def parse_candidates(raw: str, limit: int) -> list[str]:
    """Pull the numbered lines out of the model's reply."""
    lines = (_NUMBERING.sub("", line).strip(" -\"'“”") for line in raw.splitlines())
    return [line for line in lines if line][:limit]


def generate_caption_stub(req: CaptionRequest, context: dict) -> list[str]:
    """
    No-LLM fallback, kept on purpose: every teammate can run the full pipeline
    without needing an API key, and the eval harness gets a trivial baseline.
    """
    trend = context.get("trend", "no trend data yet")
    weather = context.get("weather", "unknown weather")
    location = req.city or req.region
    return [
        f"[{req.brand_name}] draft {req.content_type} for {location}, {req.country} "
        f"-- tone: {req.tone}. Trend hook: {trend}. Weather context: {weather}.",
        f"[{req.brand_name}] alt draft #2 -- shorter, punchier version for {location}.",
    ]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_configured": llm.is_configured(),
        "model": llm.model_name() if llm.is_configured() else None,
    }


@app.post("/generate-caption", response_model=CaptionResponse)
def generate_caption(req: CaptionRequest):
    context = get_mock_context(req.country, req.region, req.city)
    fallback_reason = "LLM_API_KEY not set"

    if llm.is_configured():
        try:
            raw = llm.call_llm(build_prompt(req, context), system=SYSTEM_PROMPT)
            candidates = parse_candidates(raw, req.num_candidates)
            if candidates:
                return CaptionResponse(
                    candidates=candidates,
                    grounding_context=context,
                    source="llm",
                    model=llm.model_name(),
                    note=(
                        "Real LLM call. Weather is a real live signal; the trend is "
                        "still a stub -- see trend_retrieval.py."
                    ),
                )
            fallback_reason = "LLM returned no usable lines"
        except llm.LLMError as exc:
            fallback_reason = str(exc)

    return CaptionResponse(
        candidates=generate_caption_stub(req, context),
        grounding_context=context,
        source="stub",
        model=None,
        note=(
            f"TEMPLATE STUB ({fallback_reason}). No real generation. "
            "Copy .env.example to .env and add a key to use the LLM path."
        ),
    )

@app.post("/evaluate-copy", response_model=EvaluateResponse)
def evaluate_copy(req: EvaluateRequest):
    context = get_mock_context(req.country, req.region, req.city)
    return run_evaluation(req, context)

