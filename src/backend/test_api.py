import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    """Verify system health endpoint and LLM status reporting."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_configured" in data


def test_generate_caption():
    """Verify /generate-caption pipeline (handles both LLM and stub fallback)."""
    payload = {
        "brand_name": "Nike",
        "industry": "Footwear",
        "tone": "energetic",
        "country": "US",
        "region": "Texas",
        "city": "Austin",
        "content_type": "caption",
        "num_candidates": 3,
    }
    response = client.post("/generate-caption", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert len(data["candidates"]) > 0
    assert "grounding_context" in data
    assert "source" in data


def test_evaluate_copy_success():
    """Verify /evaluate-copy end-to-end response schema and grounding."""
    payload = {
        "copy": "Y'all ready for this drop?",
        "country": "US",
        "region": "Texas",
        "city": "Austin",
        "brand_name": "Nike",
        "industry": "Footwear",
    }
    response = client.post("/evaluate-copy", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Validate output schema fields
    assert "cultural_fit_score" in data
    assert 0 <= data["cultural_fit_score"] <= 100
    assert "flagged_issues" in data
    assert "grounded_rewrite" in data
    assert "grounding_context" in data
    assert "source" in data


def test_evaluate_copy_validation_error():
    """Verify FastAPI Pydantic schema validation for missing required fields."""
    response = client.post("/evaluate-copy", json={})
    assert response.status_code == 422  # Unprocessable Entity