def format_trends(trends: list) -> str:
    if not trends:
        return "No trend information available."

    formatted = []

    for i, trend in enumerate(trends, 1):
        topic = trend.get("topic", "Unknown")
        score = trend.get("score")

        if score is not None:
            formatted.append(
                f"{i}. {topic} (trend score: {score})"
            )
        else:
            formatted.append(
                f"{i}. {topic}"
            )

    return "\n".join(formatted)


def build_context_prompt(
    user_message: str,
    company: dict | None = None,
    trends: list | None = None,
    location: dict | None = None,
    weather: dict | None = None,
) -> tuple[str, str]:

    company = company or {}
    trends = trends or []
    location = location or {}
    weather = weather or {}

    system_prompt = """
You are Wavelength, an AI marketing assistant.

Your goal is to create culturally, locally, and contextually relevant
marketing content.

You may receive information about:
- the company
- company audience
- brand voice
- location
- current weather
- current trends

Rules:

1. Always prioritize the user's request.
2. Use company information to maintain brand relevance.
3. Use trends only when they are relevant.
4. Use location and weather only when they improve the response.
5. Do not force all available context into the answer.
6. Do not invent information.
7. If context is missing, work with the information that is available.
8. For casual conversation such as "hi" or "hello", respond naturally.
"""

    prompt = f"""
## COMPANY INFORMATION

Name:
{company.get("name", "Unknown")}

Industry:
{company.get("industry", "Unknown")}

Description:
{company.get("description", "Not provided")}

Target Audience:
{company.get("target_audience", "Not provided")}

Brand Voice:
{company.get("brand_voice", "Not provided")}

Products / Services:
{company.get("products", "Not provided")}


## TARGET LOCATION

City:
{location.get("city", "Unknown")}

State:
{location.get("state", "Unknown")}

Country:
{location.get("country", "Unknown")}


## CURRENT WEATHER

Condition:
{weather.get("condition", "Unknown")}

Temperature:
{weather.get("temperature", "Unknown")}

Description:
{weather.get("description", "Not provided")}


## CURRENT TRENDS

{format_trends(trends)}


## USER REQUEST

{user_message}
"""

    return system_prompt.strip(), prompt.strip()