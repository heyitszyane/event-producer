"""Local model-provider settings for the dev harness.

This module is intentionally small and file-backed. It updates only the local
``.env`` file in the repo root so clone reviewers can configure Gemini,
OpenRouter, or a local OpenAI-compatible server without touching source code.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ProviderName = Literal["gemini", "openrouter", "openai_compatible", "local", "ollama", "lmstudio"]

_ENV_KEYS = {
    "ENABLE_LIVE_MODEL",
    "MODEL_PROVIDER",
    "MODEL_NAME",
    "ENABLE_LIVE_GEMINI",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_COMPATIBLE_API_BASE_URL",
    "LOCAL_LLM_API_BASE_URL",
    "LOCAL_LLM_MODEL",
}
_LOCAL_PROVIDERS = {"local", "ollama", "lmstudio"}


class ModelSettingsPublic(BaseModel):
    provider: str
    live_enabled: bool
    effective_mode: str
    model_name: str
    api_base_url: str | None = None
    has_api_key: bool
    fallback_reason: str | None = None
    env_path: str
    restart_required: bool = False


class ModelSettingsUpdate(BaseModel):
    provider: ProviderName
    model_name: str = Field(default="", max_length=160)
    api_base_url: str = Field(default="", max_length=500)
    api_key: str | None = Field(default=None, max_length=2000)
    live_enabled: bool = True


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def env_path() -> Path:
    return repo_root() / ".env"


def read_env_file(path: Path | None = None) -> dict[str, str]:
    target = path or env_path()
    values: dict[str, str] = {}
    if not target.exists():
        return values
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _quote_env(value: str) -> str:
    if not value:
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def write_env_values(updates: dict[str, str], path: Path | None = None) -> None:
    target = path or env_path()
    existing = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    seen: set[str] = set()
    output: list[str] = []

    for raw in existing:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(raw)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={_quote_env(updates[key])}")
            seen.add(key)
        else:
            output.append(raw)

    missing = [key for key in updates if key not in seen]
    if missing and output and output[-1].strip():
        output.append("")
    for key in missing:
        output.append(f"{key}={_quote_env(updates[key])}")

    target.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def updates_from_settings(settings: ModelSettingsUpdate, current: dict[str, str]) -> dict[str, str]:
    provider = settings.provider
    model_name = settings.model_name.strip()
    api_base_url = settings.api_base_url.strip()
    api_key = None if settings.api_key is None else settings.api_key.strip()

    updates: dict[str, str] = {
        "ENABLE_LIVE_MODEL": "true" if settings.live_enabled else "false",
        "MODEL_PROVIDER": provider,
    }

    if provider == "gemini":
        updates["GEMINI_MODEL"] = model_name or current.get("GEMINI_MODEL", "") or "gemini-2.5-flash"
        if api_key is not None:
            updates["GEMINI_API_KEY"] = api_key
    elif provider == "openrouter":
        updates["OPENROUTER_MODEL"] = (
            model_name or current.get("OPENROUTER_MODEL", "") or "google/gemini-2.5-flash"
        )
        if api_key is not None:
            updates["OPENROUTER_API_KEY"] = api_key
    elif provider in _LOCAL_PROVIDERS:
        updates["LOCAL_LLM_MODEL"] = model_name or current.get("LOCAL_LLM_MODEL", "") or "qwen2.5-coder:latest"
        updates["LOCAL_LLM_API_BASE_URL"] = (
            api_base_url
            or current.get("LOCAL_LLM_API_BASE_URL", "")
            or "http://127.0.0.1:1234/v1/chat/completions"
        )
        if api_key is not None:
            updates["OPENAI_COMPATIBLE_API_KEY"] = api_key
    else:
        updates["MODEL_NAME"] = model_name or current.get("MODEL_NAME", "")
        updates["OPENAI_COMPATIBLE_API_BASE_URL"] = api_base_url or current.get(
            "OPENAI_COMPATIBLE_API_BASE_URL", ""
        )
        if api_key is not None:
            updates["OPENAI_COMPATIBLE_API_KEY"] = api_key

    return updates


def apply_to_process_env(values: dict[str, str]) -> None:
    for key, value in values.items():
        if key in _ENV_KEYS:
            os.environ[key] = value
