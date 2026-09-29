def get_company_details(user_id: str | None = None) -> dict:
    """
    Placeholder for fetching company details.

    Later this can pull from:
    - MongoDB
    - user profile
    - company onboarding form
    - external company API
    """

    return {
        "name": "Demo Company",
        "industry": "Technology",
        "description": "A company building AI-powered products.",
        "target_audience": "Young professionals",
        "brand_voice": "Friendly, modern, informative",
        "products": "AI-powered software tools",
    }