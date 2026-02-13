from __future__ import annotations

import os
from typing import Any


class LLMClientError(RuntimeError):
    pass


def _load_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMClientError("GEMINI_API_KEY environment variable is missing")
    return api_key


def generate_content(prompt: str) -> str:
    api_key = _load_api_key()

    try:
        from google import genai
    except Exception as e:  # pragma: no cover
        raise LLMClientError(
            "google.genai is required but could not be imported (install the google-genai package)"
        ) from e

    try:
        client = genai.Client(api_key=api_key)
        config: Any
        try:
            config = genai.types.GenerateContentConfig(temperature=0)
        except Exception:
            config = {"temperature": 0}

        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=config,
        )
    except Exception as e:
        raise LLMClientError("Gemini API call failed") from e

    text = getattr(resp, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise LLMClientError("Gemini API returned empty response")

    return text
