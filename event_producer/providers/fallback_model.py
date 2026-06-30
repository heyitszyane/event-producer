"""Deterministic, dependency-free fallback model provider.

Used whenever live Gemini is unavailable, unkeyed, or disabled. It NEVER claims
to be Gemini: it reports ``model_mode="rule_based_fallback"`` and is honest
about that on the agent trace. Output is derived deterministically from the
user prompt so public clones demonstrate the product without API keys.

This provider intentionally does no network calls and imports nothing heavy,
which keeps fallback/test mode hermetic. It does NOT attempt to fabricate a
parsed Pydantic schema (that would fake structured output); instead the agent's
formatter step produces the schema from the brief-aware signal it returns.
"""

from __future__ import annotations

from event_producer.providers.agent_model import AgentModelResult


class RuleBasedFallbackModel:
    """Deterministic fallback provider (not a Gemini stand-in).

    Returns ``parsed=None`` always — we do not synthesize a fake structured
    schema — plus a deterministic ``raw_text`` signal the consuming agent can
    surface. Callers render the fallback mode honestly on the trace.
    """

    def __init__(self, model_name: str = "rule-based-fallback") -> None:
        self._model_name = model_name

    def generate_structured(
        self,
        *,
        agent_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        schema: type,
    ) -> AgentModelResult:
        head = (user_prompt or "").strip().replace("\n", " ")[:180]
        raw = (
            f"[fallback:{agent_name}] Deterministic interpretation of "
            f"{len(user_prompt)} chars; no live model called. "
            f"Signal: \"…{head}…\"."
        )
        return AgentModelResult(
            parsed=None,
            raw_text=raw,
            model_mode="rule_based_fallback",
            model_name=self._model_name,
            fallback_reason=(
                "Live Gemini disabled or unkeyed; deterministic fallback used."
            ),
            error=None,
        )

    def summarize(self, agent_name: str, user_prompt: str) -> str:
        head = (user_prompt or "").strip().replace("\n", " ")[:200]
        return (
            f"Interpreted brief ({agent_name}): \"…{head}…\" "
            f"(fallback: no live model)."
        )
