"""Provider router — picks Gemini live vs rule-based fallback for the app.

Single decision point: ``build_agent_model(env)`` returns the provider that makes
structured generating calls. Keeping the decision here (next to ``ModelEnv``)
means agents stay free of env logic, and tests can inject any provider
implementing ``AgentModelProvider`` without monkeypatching module imports.
"""

from __future__ import annotations

from event_producer.providers.agent_model import AgentModelProvider
from event_producer.providers.fallback_model import RuleBasedFallbackModel
from event_producer.providers.model_env import ModelEnv


def build_agent_model(
    env: ModelEnv | None = None,
) -> AgentModelProvider:
    """Return the best available provider for the resolved environment.

    When live Gemini is genuinely callable (toggle on AND key present) we
    return the lazy ``GeminiModel``. Otherwise we return the deterministic
    fallback. The caller can always inspect ``env.effective_mode`` / ``env.
    fallback_reason`` for trace honesty.
    """
    resolved = env or ModelEnv.from_env()

    if resolved.live_enabled and resolved.api_key:
        # Imported here so fallback/test paths never import google-genai.
        from event_producer.providers.gemini_model import GeminiModel

        return GeminiModel(resolved)

    return RuleBasedFallbackModel()
