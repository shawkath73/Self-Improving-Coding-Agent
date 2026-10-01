from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    pass


@dataclass
class GeminiClient:
    model: str = "gemini-3.6-flash"
    retries: int = 3
    timeout_seconds: float = 60

    def __post_init__(self):
        self._client = None
        self.usage = {}

    def complete(self, prompt: str) -> str:
        if self._client is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError as exc:
                raise ConfigurationError(
                    "Gemini SDK is unavailable in this Python environment. "
                    f"Install it with '{sys.executable} -m pip install google-genai'. "
                    f"Python executable: {sys.executable}"
                ) from exc
            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise ConfigurationError("GEMINI_API_KEY is required.")
            self._client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=int(self.timeout_seconds * 1000)
                ),
            )
        for attempt in range(self.retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=prompt
                )
                if not response.text:
                    raise ConfigurationError("Gemini returned an empty response.")
                metadata = getattr(response, "usage_metadata", None)
                if metadata:
                    self.usage = {
                        "input_tokens": getattr(metadata, "prompt_token_count", None),
                        "output_tokens": getattr(metadata, "candidates_token_count", None),
                        "total_tokens": getattr(metadata, "total_token_count", None),
                    }
                return response.text
            except ConfigurationError:
                raise
            except Exception:
                if attempt >= self.retries:
                    raise
                time.sleep(2**attempt)


@dataclass
class AnthropicClient:
    model: str = "claude-3-5-sonnet-latest"
    timeout_seconds: float = 60

    def __post_init__(self):
        self._client = None
        self.usage = {}

    def complete(self, prompt: str) -> str:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ConfigurationError("Install verified-execution-agent[anthropic].") from exc
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ConfigurationError("ANTHROPIC_API_KEY is required.")
            self._client = anthropic.Anthropic(
                api_key=key,
                timeout=self.timeout_seconds,
            )
        response = self._client.messages.create(
            model=self.model, max_tokens=2048, messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
