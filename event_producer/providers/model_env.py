"""Environment-driven model/provider configuration (server-side only).

Reads provider toggles and secrets from process environment. Never imported by,
or exposed to, the frontend. The default orchestration rule is:

    ENABLE_LIVE_MODEL=true  AND  selected provider config is present
        -> caller may attempt the selected live provider

Legacy Gemini-only setups are still supported:

    ENABLE_LIVE_GEMINI=true  AND  (GEMINI_API_KEY or GOOGLE_API_KEY) present
        -> caller may attempt live Gemini
    otherwise
        -> rule-based fallback is used, with a recorded fallback_reason.

OpenRouter and local/OpenAI-compatible providers can be selected with
MODEL_PROVIDER when ENABLE_LIVE_MODEL=true. The legacy Gemini env still works
so older demos do not need to change.

The structured parse is delegated to the concrete provider; this module only
resolves the mode gate and the key, so that unit tests can assert mode
decisions deterministically with monkeypatched env.
"""

from __future__ import annotations

import os

# Legacy aliases accepted so older setups keep working. Checked in order of
# precedence for the default Gemini provider.
_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
_OPENAI_COMPATIBLE_KEYS = ("OPENAI_COMPATIBLE_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")
_LOCAL_PROVIDERS = {"local", "ollama", "lmstudio"}
_OPENAI_COMPATIBLE_PROVIDERS = {"openai_compatible", "openrouter", *_LOCAL_PROVIDERS}


def _provider_label(provider: str) -> str:
    return "Gemini" if provider == "gemini" else provider


class ModelEnv:
    """Resolved, immutable view of the provider configuration.

    Attributes:
        provider: Selected model provider ("gemini", "openrouter",
            "openai_compatible", "local", "ollama", or "lmstudio").
        live_enabled: True only when a live toggle is exactly the string "true"
            (case-insensitive).
        api_key: The best-available server-side API key, or "" when none set.
            Local providers may be live without a key; hosted providers require
            one.
        model_name: The model id the provider should request.
        api_base_url: OpenAI-compatible chat completions endpoint, when used.
        effective_mode: "gemini_live" / "openai_compatible_live" when live is
            callable, else "rule_based_fallback".
        fallback_reason: Why live mode is NOT being used. Empty when live is
            genuinely callable, so callers can record it on the trace step.
    """

    def __init__(
        self,
        provider: str,
        live_enabled: bool,
        api_key: str,
        model_name: str,
        api_base_url: str,
        fallback_reason: str,
    ) -> None:
        self.provider = provider
        self.live_enabled = live_enabled
        self.api_key = api_key
        self.model_name = model_name
        self.api_base_url = api_base_url

        local_live_without_key = provider in _LOCAL_PROVIDERS and bool(api_base_url)
        if live_enabled and (api_key or local_live_without_key):
            self.effective_mode: str = (
                "openai_compatible_live"
                if provider in _OPENAI_COMPATIBLE_PROVIDERS
                else "gemini_live"
            )
            self.fallback_reason: str = ""
        else:
            self.effective_mode = "rule_based_fallback"
            label = _provider_label(provider)
            # Prefer the most specific reason.
            self.fallback_reason = fallback_reason or (
                f"live {label} not enabled" if not live_enabled
                else f"no {label} API key provided" if not api_key
                else f"live {label} not enabled and no key"
            )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ModelEnv":
        """Resolve configuration from ``env`` (defaults to ``os.environ``)."""
        e = os.environ if env is None else env

        provider = (e.get("MODEL_PROVIDER", "") or "").strip().lower() or "gemini"
        if provider not in {"gemini", *_OPENAI_COMPATIBLE_PROVIDERS}:
            provider = "gemini"

        live_raw = (e.get("ENABLE_LIVE_MODEL", "") or "").strip().lower()
        legacy_live_raw = (e.get("ENABLE_LIVE_GEMINI", "") or "").strip().lower()
        live_enabled = live_raw == "true" or (provider == "gemini" and legacy_live_raw == "true")

        api_key = ""
        api_base_url = ""

        if provider in _OPENAI_COMPATIBLE_PROVIDERS:
            key_names = _OPENAI_COMPATIBLE_KEYS
            if provider in _LOCAL_PROVIDERS:
                api_key = (e.get("OPENAI_COMPATIBLE_API_KEY", "") or "").strip()
                api_base_url = (
                    (e.get("OPENAI_COMPATIBLE_API_BASE_URL", "") or "").strip()
                    or (e.get("LOCAL_LLM_API_BASE_URL", "") or "").strip()
                    or "http://127.0.0.1:11434/v1/chat/completions"
                )
                model_name = (
                    (e.get("MODEL_NAME", "") or "").strip()
                    or (e.get("LOCAL_LLM_MODEL", "") or "").strip()
                    or "qwen2.5-coder:latest"
                )
            else:
                for name in key_names:
                    val = (e.get(name, "") or "").strip()
                    if val:
                        api_key = val
                        break
                api_base_url = (
                    (e.get("OPENAI_COMPATIBLE_API_BASE_URL", "") or "").strip()
                    or (
                        "https://openrouter.ai/api/v1/chat/completions"
                        if provider == "openrouter"
                        else ""
                    )
                )
                model_name = (
                    (e.get("MODEL_NAME", "") or "").strip()
                    or (e.get("OPENROUTER_MODEL", "") or "").strip()
                    or "google/gemini-2.5-flash"
                )
        else:
            for name in _KEY_NAMES:
                val = (e.get(name, "") or "").strip()
                if val:
                    api_key = val
                    break

            model_name = (
                (e.get("GEMINI_MODEL", "") or "").strip()
                or (e.get("MODEL_NAME", "") or "").strip()
                or "gemini-2.5-flash"
            )

        # Build the specific fallback reason even when live ends up off.
        label = _provider_label(provider)
        key_optional = provider in _LOCAL_PROVIDERS
        if not live_enabled and not api_key and not key_optional:
            reason = f"live {label} not enabled and no API key provided"
        elif not live_enabled:
            reason = f"live {label} not enabled (ENABLE_LIVE_MODEL != true)"
        elif not api_key and not key_optional:
            reason = f"no {label} API key provided"
        elif provider in _OPENAI_COMPATIBLE_PROVIDERS and not api_base_url:
            reason = "no OpenAI-compatible API base URL provided"
            api_key = ""
        else:
            reason = ""

        return cls(
            provider=provider,
            live_enabled=live_enabled,
            api_key=api_key,
            model_name=model_name,
            api_base_url=api_base_url,
            fallback_reason=reason,
        )

    def require_key(self) -> str:
        """Return the API key, or raise a clear error explaining fallback."""
        if self.api_key:
            return self.api_key
        raise RuntimeError(
            f"Live {self.provider} requested but no key is configured. "
            "Set the provider API key server-side, or leave live mode unset "
            "to use rule-based fallback."
        )
