"""
Wavelength -- API

Auth (signup/login), profile (business details + states + past taglines),
tagline generation per state, thumbs up/down feedback, and a STUBBED
email draft/approval flow. See README for what's real vs. still stubbed.
"""

from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import llm
from db import users_collection, feedback_collection
from auth import hash_password, verify_password, create_token, get_current_user
from models import (
    SignupRequest, LoginRequest, AuthResponse,
    ProfileUpdate, ProfileResponse,
    GenerateRequest, GenerateResponse, TaglineCandidate,
    FeedbackRequest,
    EmailDraftRequest, EmailDraftResponse, EmailSendRequest,
    ChatRequest, ChatResponse,
)
from trend_retrieval import get_mock_context

from evaluator import EvaluateRequest, EvaluateResponse, run_evaluation

app = FastAPI(title="Wavelength API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
from services.company_service import get_company_details
from services.location_service import get_location
from services.weather_service import get_weather
from services.trend_service import get_google_trends, select_trends

from prompt_builder import build_context_prompt
SYSTEM_PROMPT = (
    "You are a regional marketing copywriter. You write short-form copy that "
    "sounds native to one specific market, not like US copy that was translated. "
    "You never invent facts about the brand. You output nothing but the copy."
)

# states classified as India for the country tag used in generation/grounding
INDIA_STATES = {"Maharashtra", "Delhi", "Tamil Nadu"}


def user_to_profile(user: dict) -> ProfileResponse:
    return ProfileResponse(
        email=user["email"],
        business_name=user.get("business_name"),
        industry=user.get("industry"),
        tone=user.get("tone"),
        states=user.get("states", []),
        past_taglines=user.get("past_taglines", []),
        profile_complete=bool(user.get("business_name") and user.get("states")),
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_configured": llm.is_configured(),
        "model": llm.model_name() if llm.is_configured() else None,
    }


# ---------- Auth ----------

@app.post("/auth/signup", response_model=AuthResponse)
def signup(req: SignupRequest):
    if users_collection.find_one({"email": req.email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    doc = {
        "email": req.email,
        "password_hash": hash_password(req.password),
        "business_name": None,
        "industry": None,
        "tone": None,
        "states": [],
        "past_taglines": [],
        "created_at": datetime.now(timezone.utc),
    }
    result = users_collection.insert_one(doc)
    token = create_token(str(result.inserted_id))
    return AuthResponse(token=token, profile_complete=False)


@app.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    user = users_collection.find_one({"email": req.email})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_token(str(user["_id"]))
    profile_complete = bool(user.get("business_name") and user.get("states"))
    return AuthResponse(token=token, profile_complete=profile_complete)


# ---------- Profile ----------

@app.get("/me", response_model=ProfileResponse)
def get_me(user: dict = Depends(get_current_user)):
    return user_to_profile(user)


@app.put("/me", response_model=ProfileResponse)
def update_me(update: ProfileUpdate, user: dict = Depends(get_current_user)):
    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    if changes:
        users_collection.update_one({"_id": user["_id"]}, {"$set": changes})
    updated = users_collection.find_one({"_id": user["_id"]})
    return user_to_profile(updated)


# ---------- Tagline generation ----------

def generate_for_state(business_name: str, tone: str, content_type: str, prompt: str,
                        past_taglines: list[str], country: str, region: str) -> TaglineCandidate:
    context = get_mock_context(country, region)
    style_hint = f" Style reference: \"{past_taglines[0]}\"" if past_taglines else ""
    text = (
        f"[{business_name}] {content_type} for {region}, {country} -- tone: {tone}. "
        f"Prompt: {prompt}. Trend hook: {context.get('trend')}. "
        f"Weather: {context.get('weather')}.{style_hint}"
    )
    return TaglineCandidate(state=region, text=text, grounding_context=context)


@app.post("/generate-taglines", response_model=GenerateResponse)
def generate_taglines(req: GenerateRequest, user: dict = Depends(get_current_user)):
    states = req.states or user.get("states", [])
    if not states:
        raise HTTPException(status_code=400, detail="No states selected -- add states in your profile first")

    business_name = user.get("business_name") or "Your brand"
    tone = user.get("tone") or "neutral"
    past_taglines = user.get("past_taglines", [])

    results = [
        generate_for_state(
            business_name, tone, req.content_type, req.prompt, past_taglines,
            country="India" if state in INDIA_STATES else "US",
            region=state,
        )
        for state in states
    ]

    return GenerateResponse(
        results=results,
        note=(
            "MOCK GENERATION -- template-based, not a real LLM call yet. "
            "Trend is a stub; weather is real for mapped states. "
            "See trend_retrieval.py, and wire a real LLM call into generate_for_state()."
        ),
    )


# ---------- Feedback ----------

@app.post("/feedback")
def submit_feedback(req: FeedbackRequest, user: dict = Depends(get_current_user)):
    if req.thumbs not in ("up", "down"):
        raise HTTPException(status_code=400, detail="thumbs must be 'up' or 'down'")
    feedback_collection.insert_one({
        "user_id": user["_id"],
        "state": req.state,
        "tagline_text": req.tagline_text,
        "thumbs": req.thumbs,
        "created_at": datetime.now(timezone.utc),
    })
    return {"status": "recorded"}


# ---------- Email draft / approval (STUB) ----------

@app.post("/draft-email", response_model=EmailDraftResponse)
def draft_email(req: EmailDraftRequest, user: dict = Depends(get_current_user)):
    business_name = user.get("business_name") or "Your brand"
    lines = [f"{state}: {text}" for state, text in req.selected_taglines.items()]
    body = (
        f"Hi there,\n\nHere's what's new from {business_name} this week:\n\n"
        + "\n\n".join(lines)
        + "\n\nSee you soon!"
    )
    return EmailDraftResponse(
        subject=f"{business_name} -- this week's update",
        body=body,
        note="STUB -- drafted with a template, not a real LLM call yet.",
    )


@app.post("/send-email")
def send_email(req: EmailSendRequest, user: dict = Depends(get_current_user)):
    if not req.approved:
        raise HTTPException(status_code=400, detail="Email must be approved before sending")
    # TODO: wire up a real email provider (e.g. SendGrid, SES) here.
    return {
        "status": "stubbed",
        "note": "No real email was sent -- this endpoint is a placeholder for the send integration.",
    }

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):

    company = get_company_details()

    location = get_location()

    weather = get_weather(location)

    trends = get_google_trends(
        location=location,
        company=company,
    )

    trends = select_trends(
        trends,
        limit=5,
    )

    system_prompt, prompt = build_context_prompt(
        user_message=req.message,
        company=company,
        trends=trends,
        location=location,
        weather=weather,
    )

    response = llm.call_llm(
        prompt=prompt,
        system=system_prompt,
        temperature=0.7,
        max_tokens=500,
    )

    return ChatResponse(
        response=response
    )