def get_company_details(user: dict) -> dict:
    """Map the authenticated MongoDB user profile to company prompt context."""
    return {
        "name": user.get("business_name") or "Your brand",
        "industry": user.get("industry") or "Not provided",
        "description": user.get("description") or "Not provided",
        "target_audience": user.get("target_audience") or "Not provided",
        "brand_voice": user.get("tone") or "neutral",
        "products": user.get("products") or "Not provided",
        "past_taglines": user.get("past_taglines", []),
    }
