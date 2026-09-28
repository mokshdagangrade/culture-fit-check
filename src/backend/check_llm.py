"""
One-command check that your .env is wired up correctly.

    cd src/backend && python check_llm.py

Run this before you report that "the app is broken" -- it tells you whether
the problem is your key, your model name, or the app itself.
"""

from dotenv import load_dotenv

import backend.llm as llm

load_dotenv()

if not llm.is_configured():
    raise SystemExit(
        "LLM_API_KEY is not set.\n"
        "  cp .env.example .env   then paste your key into .env\n"
        "The app still runs without it -- it falls back to the template stub."
    )

print(f"provider : {llm.base_url()}")
print(f"model    : {llm.model_name()}")

try:
    reply = llm.call_llm("Reply with exactly: wavelength ok", temperature=0, max_tokens=16)
except llm.LLMError as exc:
    raise SystemExit(
        f"\nFAILED: {exc}\n\n"
        "Common causes:\n"
        "  - key pasted with quotes or a trailing space\n"
        "  - LLM_MODEL no longer offered by this provider (check their model list)\n"
        "  - LLM_BASE_URL does not match the provider the key belongs to"
    )

print(f"reply    : {reply}")
print("\nOK -- your .env works.")
