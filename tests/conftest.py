"""Shared test isolation fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_model_env_to_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent developer live-model env from leaking into hermetic tests."""
    for key in (
        "ENABLE_LIVE_MODEL",
        "ENABLE_LIVE_GEMINI",
        "STRICT_LIVE_MODEL",
        "MODEL_PROVIDER",
        "MODEL_NAME",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_API_BASE_URL",
        "LOCAL_LLM_API_BASE_URL",
        "LOCAL_LLM_MODEL",
        "MODEL_REQUEST_TIMEOUT_SECONDS",
        "MODEL_MAX_OUTPUT_TOKENS",
    ):
        monkeypatch.delenv(key, raising=False)
