"""
LLM client -- one provider-agnostic wrapper.

Every free provider we care about speaks the OpenAI chat-completions
protocol, so switching providers is a .env change, not a code change.
See .env.example for the free options and their base URLs.

If LLM_API_KEY is unset, is_configured() returns False and main.py falls
back to the template stub -- so a teammate without a key can still run the
whole pipeline end to end.
"""

import os
from functools import lru_cache
from typing import Optional

from openai import OpenAI, OpenAIError

# Groq: free, no card required, fastest to set up. Override in .env.
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class LLMError(RuntimeError):
    """Raised when the provider call fails or no key is configured."""


def is_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


def base_url() -> str:
    return os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=base_url())


def call_llm(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.8,
    max_tokens: int = 512,
) -> str:
    """Send one prompt, get the text back. Raises LLMError on any failure."""
    if not is_configured():
        raise LLMError("LLM_API_KEY is not set -- copy .env.example to .env and add your key.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = _client().chat.completions.create(
            model=model_name(),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except OpenAIError as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    return (response.choices[0].message.content or "").strip()
