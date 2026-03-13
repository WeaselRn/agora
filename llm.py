"""
Agora — Model-agnostic LLM client with Gemini implementation.

Provides retry logic for malformed JSON, rate limiting for Gemini free tier,
and a swappable architecture via a single config value.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod

from google import genai

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# JSON Extraction Helpers
# ─────────────────────────────────────────────

def extract_json(text: str) -> dict:
    """Extract a JSON object from an LLM response, handling markdown fences."""
    # Try to find JSON in code fences first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try to find a JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        text = text[brace_start : brace_end + 1]

    return json.loads(text)


# ─────────────────────────────────────────────
# Abstract Base Client
# ─────────────────────────────────────────────

class LLMClient(ABC):
    """Abstract base class for LLM providers. Swap providers by subclassing."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Send a prompt and return the raw text response."""
        ...

    async def generate_json(self, prompt: str, retries: int = 3) -> dict:
        """Generate a response and parse it as JSON, retrying on parse failure."""
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                raw = await self.generate(prompt)
                return extract_json(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "JSON parse failed (attempt %d/%d): %s — retrying",
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    # Append a correction hint to the prompt for the retry
                    prompt = (
                        prompt
                        + "\n\n[SYSTEM NOTE: Your previous response was not valid JSON. "
                        "Return ONLY a raw JSON object, no markdown fences, no explanation.]"
                    )
        raise ValueError(f"Failed to get valid JSON after {retries} attempts: {last_error}")


# ─────────────────────────────────────────────
# Gemini Client
# ─────────────────────────────────────────────

class GeminiClient(LLMClient):
    """Gemini API client using the google-genai SDK."""

    # Gemini free tier: 15 requests/min → ~4 seconds between requests
    MIN_INTERVAL = 4.0

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a free key at https://aistudio.google.com/apikey"
            )

        self._model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
        self._client = genai.Client(api_key=api_key)
        self._semaphore = asyncio.Semaphore(3)
        self._last_call_time: float = 0.0

    async def generate(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the text response."""
        loop = asyncio.get_running_loop()
        for attempt in range(3):
            try:
                async with self._semaphore:
                    # Rate limiting — enforce minimum interval
                    now = time.monotonic()
                    elapsed = now - self._last_call_time
                    if elapsed < self.MIN_INTERVAL:
                        await asyncio.sleep(self.MIN_INTERVAL - elapsed)
                    self._last_call_time = time.monotonic()  # stamp BEFORE call so next coroutine backs off
                    response = await loop.run_in_executor(
                        None,
                        lambda: self._client.models.generate_content(
                            model=self._model,
                            contents=prompt,
                        ),
                    )
                    return response.text
            except Exception as exc:  # noqa: BLE001
                if "429" in str(exc) or "quota" in str(exc).lower():
                    wait = 15 * (attempt + 1)  # 15s, 30s, 45s
                    logger.warning(
                        "Rate limited, waiting %ds (attempt %d/3)",
                        wait,
                        attempt + 1,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        raise RuntimeError("Exceeded retry limit on rate limiting")


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────

def create_llm_client() -> LLMClient:
    """Create an LLM client based on environment configuration.

    Currently supports Gemini. To add a new provider:
    1. Subclass LLMClient and implement generate()
    2. Add a new branch here keyed on LLM_PROVIDER env var
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        return GeminiClient()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. Supported: gemini"
        )
