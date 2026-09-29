def get_google_trends(
    location: dict | None = None,
    company: dict | None = None,
) -> list:
    """
    Placeholder for Google Trends.

    Later this can use:
    - pytrends
    - Google Trends data source
    - custom trend scraper/API
    """

    return [
        {
            "topic": "Artificial Intelligence",
            "score": 95,
        },
        {
            "topic": "Fall activities",
            "score": 78,
        },
        {
            "topic": "Local events",
            "score": 65,
        },
    ]


def select_trends(trends: list, limit: int = 5) -> list:
    """
    Returns the highest scoring trends.
    """

    return sorted(
        trends,
        key=lambda trend: trend.get("score", 0),
        reverse=True,
    )[:limit]