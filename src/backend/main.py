"""
Wavelength -- mock end-to-end pipeline skeleton (Session 4)

Flow: brand + region input -> (stub) trend grounding -> caption generation -> response

This is intentionally a THIN skeleton: the generation step currently uses a
simple template with NO real grounding yet. Session 5 wires in real trend
retrieval (Google Trends, festival calendars) to replace the stub in
trend_retrieval.py, and a real LLM call to replace generate_caption_stub().
"""

from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from trend_retrieval import get_mock_context

load_dotenv()

app = FastAPI(title="Wavelength API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CaptionRequest(BaseModel):
    brand_name: str
    industry: str
    tone: str  # e.g. "playful", "premium", "no-nonsense"
    country: str  # "US" or "India"
    region: str  # e.g. "Texas", "Maharashtra"
    city: Optional[str] = None  # e.g. "Austin", "Mumbai"
    content_type: str  # "caption" | "notification" | "meme"


class CaptionResponse(BaseModel):
    candidates: list[str]
    grounding_context: dict
    note: str


def generate_caption_stub(req: CaptionRequest, context: dict) -> list[str]:
    """
    Placeholder generator. Swap this for a real LLM call (see call_llm below)
    once your team picks a provider. Keeping a non-LLM fallback means every
    teammate can run the full pipeline without needing an API key yet.
    """
    trend = context.get("trend", "no trend data yet")
    weather = context.get("weather", "unknown weather")
    location = req.city or req.region
    return [
        f"[{req.brand_name}] draft {req.content_type} for {location}, {req.country} "
        f"-- tone: {req.tone}. Trend hook: {trend}. Weather context: {weather}.",
        f"[{req.brand_name}] alt draft #2 -- shorter, punchier version for {location}.",
    ]


def call_llm(prompt: str) -> str:
    """
    Real LLM call. Left unimplemented on purpose -- wire up whichever
    provider your team standardizes on (Anthropic/OpenAI/open-source),
    then swap generate_caption_stub() for this in /generate-caption below.
    """
    raise NotImplementedError("Wire up your LLM provider of choice here.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-caption", response_model=CaptionResponse)
def generate_caption(req: CaptionRequest):
    context = get_mock_context(req.country, req.region, req.city)
    candidates = generate_caption_stub(req, context)
    return CaptionResponse(
        candidates=candidates,
        grounding_context=context,
        note=(
            "MOCK PIPELINE -- no real trend grounding or LLM call yet. "
            "Weather is a real live call; trend is a stub. "
            "See trend_retrieval.py and call_llm() to wire in real sources."
        ),
    )
