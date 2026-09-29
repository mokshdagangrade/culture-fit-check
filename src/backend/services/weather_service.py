def get_weather(location: dict) -> dict:
    """
    Placeholder for weather data.

    Later this can call:
    - OpenWeatherMap
    - WeatherAPI
    - Google Weather API
    - another weather provider
    """

    city = location.get("city", "Unknown")

    return {
        "location": city,
        "condition": "Partly Cloudy",
        "temperature": "72°F",
        "description": "Partly cloudy with mild temperatures",
        "humidity": "55%",
        "wind": "6 mph",
    }