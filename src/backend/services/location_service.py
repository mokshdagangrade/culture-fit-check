def get_location(user_id: str | None = None) -> dict:
    """
    Placeholder for location.

    Later this can come from:
    - company profile
    - frontend-provided location
    - selected campaign location
    - geolocation API
    """

    return {
        "city": "College Park",
        "state": "Maryland",
        "country": "USA",
        "latitude": 38.9897,
        "longitude": -76.9378,
    }