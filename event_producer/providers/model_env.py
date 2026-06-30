"""Environment-driven model/provider configuration (server-side only).

Reads provider toggles and secrets from process environment. Never imported by,
or exposed to, the frontend. The orchestration rule is:

    ENABLE_LIVE_GEMINI=true  AND  (GEMINI_API_KEY or GOOGLE_API_KEY) present
        -> caller may attempt live Gemini
    otherwise
        -> rule-based fallback is used, with a recorded fallback_reason.

The structured parse is delegated to the concrete provider; this module only
resolves the mode gate and the key, so that unit tests can assert mode
decisions deterministically with monkeypatched env.
"""

from __future__ import annotations

import os

# Legacy alias accepted so older setups keep working. Checked in order of
# precedence: GEMINI_API_KEY first, then GOOGLE_API_KEY.
_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


class ModelEnv:
    """Resolved, immutable view of the provider configuration.

    Attributes:
        live_enabled: True only when the ENABLE_LIVE_GEMINI toggle is exactly
            the string "true" (case-insensitive).
        api_key: The best-available server-side API key, or "" when none set.
        model_name: The model id the Gemini provider should request.
        effective_mode: "gemini_live" when live actually callable,
            else "rule_based_fallback".
        fallback_reason: Why live mode is NOT being used. Empty when live is
            genuinely callable, so callers can record it on the trace step.
    """

    def __init__(
        self,
        live_enabled: bool,
        api_key: str,
        model_name: str,
        fallback_reason: str,
    ) -> None:
        self.live_enabled = live_enabled
        self.api_key = api_key
        self.model_name = model_name

        if live_enabled and api_key:
            self.effective_mode: str = "gemini_live"
            self.fallback_reason: str = ""
        else:
            self.effective_mode = "rule_based_fallback"
            # Prefer the most specific reason.
            self.fallback_reason = fallback_reason or (
                "live Gemini not enabled" if not live_enabled
                else "no Gemini API key provided" if not api_key
                else "live Gemini not enabled and no key"
            )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ModelEnv":
        """Resolve configuration from ``env`` (defaults to ``os.environ``)."""
        e = os.environ if env is None else env

        live_raw = (e.get("ENABLE_LIVE_GEMINI", "") or "").strip().lower()
        live_enabled = live_raw == "true"

        api_key = ""
        for name in _KEY_NAMES:
            val = (e.get(name, "") or "").strip()
            if val:
                api_key = val
                break

        model_name = (e.get("GEMINI_MODEL", "") or "").strip() or "gemini-2.5-flash"

        # Build the specific fallback reason even when live ends up off.
        if not live_enabled and not api_key:
            reason = "live Gemini not enabled and no Gemini API key provided"
        elif not live_enabled:
            reason = "live Gemini not enabled (ENABLE_LIVE_GEMINI != true)"
        elif not api_key:
            reason = "no Gemini API key provided (set GEMINI_API_KEY or GOOGLE_API_KEY)"
        else:
            reason = ""

        return cls(
            live_enabled=live_enabled,
            api_key=api_key,
            model_name=model_name,
            fallback_reason=reason,
        )

    def require_key(self) -> str:
        """Return the API key, or raise a clear error explaining fallback."""
        if self.api_key:
            return self.api_key
        raise RuntimeError(
            "Live Gemini requested but no key is configured. "
            "Set GEMINI_API_KEY or GOOGLE_API_KEY server-side, or leave "
            "ENABLE_LIVE_GEMINI unset to use rule-based fallback."
        )
