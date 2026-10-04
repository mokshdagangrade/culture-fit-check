"""OpenAI-compatible provider client, including Gemini."""

import os
from functools import lru_cache
from typing import Optional

from openai import OpenAI, OpenAIError, APIStatusError, APIConnectionError, APITimeoutError
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Groq: free, no card required, fastest to set up. Override in .env.
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class LLMError(RuntimeError):
    """Raised when the provider call fails or no key is configured."""


def api_key():
    if urlparse(base_url()).hostname == "router.huggingface.co":
        return os.getenv("HF_TOKEN", "")
    return os.getenv("LLM_API_KEY", "")


def is_configured() -> bool:
    return bool(api_key())


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


def base_url() -> str:
    return os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=api_key(), base_url=base_url(), timeout=90.0, max_retries=2)


def call_llm(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.8,
    max_tokens: int = 512,
) -> str:
    """Send one prompt, get the text back. Raises LLMError on any failure."""
    if not is_configured():
        raise LLMError("Set HF_TOKEN for Hugging Face, or LLM_API_KEY for other hosted providers, in the backend .env.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    options = {}
    if urlparse(base_url()).hostname == "generativelanguage.googleapis.com":
        # Gemini spends the shared output budget on thinking as well as copy.
        options["reasoning_effort"] = "low"
        max_tokens = max(max_tokens, 8192)

    try:
        response = _client().chat.completions.create(
            model=model_name(), messages=messages,
            temperature=temperature, max_tokens=max_tokens, **options,
        )
    except APIStatusError as exc:
        # Do not log provider response bodies: they may contain submitted data.
        logger.warning("LLM provider failure: model=%s status=%s request_id=%s",
                       model_name(), exc.status_code, exc.request_id)
        error_body = exc.body if isinstance(exc.body, dict) else {}
        if isinstance(error_body.get("error"), dict):
            error_body = error_body["error"]
        if error_body.get("code") == "model_not_supported":
            message = "This model is not served by your enabled Hugging Face providers. Choose a hosted model in LLM_MODEL or enable its provider in Hugging Face Inference Providers settings."
        elif exc.status_code in (500, 502, 503, 504):
            message = "The AI provider is temporarily unavailable or experiencing high demand. Please retry in a moment."
        elif exc.status_code == 429:
            message = "The AI provider rate limit or quota was reached. Wait before retrying, or check your API quota."
        elif exc.status_code in (401, 403):
            message = "The AI provider rejected the API credentials. Check the backend API key and permissions."
        elif exc.status_code == 402:
            message = "Hosted inference credits are exhausted. Check your provider billing or credit balance."
        elif exc.status_code == 404:
            message = "The configured AI model was not found. Check LLM_MODEL in the backend configuration."
        else:
            message = "The AI provider rejected the generation request. Check the model and provider configuration."
        raise LLMError(message) from exc
    except APITimeoutError as exc:
        logger.warning("LLM provider timeout: model=%s", model_name())
        raise LLMError("The AI provider timed out. Please retry in a moment.") from exc
    except APIConnectionError as exc:
        logger.warning("LLM provider connection failure: model=%s", model_name())
        raise LLMError("Cannot connect to the AI provider. Check the backend internet connection and retry.") from exc
    except OpenAIError as exc:
        logger.warning("LLM client failure: type=%s model=%s", type(exc).__name__, model_name())
        raise LLMError("The AI client could not complete the request. Check the provider configuration.") from exc

    return response_text(response)


def response_text(response):
    if not response.choices:
        raise LLMError("The provider returned no content")
    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise LLMError("The provider truncated the draft; increase the output budget")
    text = (choice.message.content or "").strip()
    if not text:
        raise LLMError("The provider returned an empty draft")
    return text
