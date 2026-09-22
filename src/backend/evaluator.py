from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field
import llm

class IssueType(str, Enum):
    CULTURAL_SALIENCE = "cultural_salience"
    TONE_MISMATCH = "tone_mismatch"
    MISSED_OPPORTUNITY = "missed_opportunity"
    OUTDATED_SLANG = "outdated_slang"
    OTHER = "other"

class SeverityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class FlaggedIssue(BaseModel):
    phrase: str = Field(description="The exact snippet or phrase flagged in the copy.")
    issue_type: IssueType = Field(description="Category of the cultural or tonal issue.")
    severity: SeverityLevel = Field(default=SeverityLevel.MEDIUM)
    explanation: str = Field(description="Detailed reason why this phrase fails cultural fit.")
    suggested_fix: Optional[str] = Field(default=None)

class EvaluateRequest(BaseModel):
    copy: str = Field(..., min_length=1, max_length=1000)
    country: str
    region: str
    city: Optional[str] = None
    brand_name: Optional[str] = None
    industry: Optional[str] = None
    tone: Optional[str] = None

class EvaluateResponse(BaseModel):
    cultural_fit_score: int = Field(..., ge=0, le=100)
    flagged_issues: list[FlaggedIssue] = Field(default_factory=list)
    grounded_rewrite: str
    grounding_context: dict
    source: Literal["llm", "stub"]
    model: Optional[str] = None
    note: Optional[str] = None

def run_evaluation(req: EvaluateRequest, context: dict) -> EvaluateResponse:
    if not llm.is_configured():
        return generate_evaluation_stub(req, context, "LLM_API_KEY not set")

    # LLM execution & structured output logic will live here
    ...

def generate_evaluation_stub(req: EvaluateRequest, context: dict, reason: str) -> EvaluateResponse:
    return EvaluateResponse(
        cultural_fit_score=70,
        flagged_issues=[
            FlaggedIssue(
                phrase=req.copy,
                issue_type=IssueType.TONE_MISMATCH,
                explanation=f"Stub assessment for {req.region}, {req.country}.",
            )
        ],
        grounded_rewrite=f"Revised draft for {req.brand_name or 'brand'} in {req.region}.",
        grounding_context=context,
        source="stub",
        note=f"TEMPLATE STUB ({reason}).",
    )