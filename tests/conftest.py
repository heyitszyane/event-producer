"""Shared test isolation fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_casefile_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep every test's casefiles out of the developer's real .local_state.

    Without this, tests that call /run or create casefiles leak blank
    casefiles into the local demo storage root on every pytest run.
    """
    monkeypatch.setenv("EVENT_PRODUCER_CASEFILE_ROOT", str(tmp_path / "casefile-events"))


@pytest.fixture(autouse=True)
def _default_model_env_to_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent developer live-model env from leaking into hermetic tests."""
    monkeypatch.setenv("EVENT_PRODUCER_LOAD_DOTENV", "false")
    monkeypatch.delenv("CASEFILE_STORE", raising=False)
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
