"""Agent model provider seam.

This is the moat between the agents and any concrete model backend. Agents call
the ``AgentModelProvider`` protocol; the concrete implementation is chosen by
the composition root based on ``ModelEnv``. This keeps agents swappable across
live Gemini, rule-based fallback, or mocked/test providers without touching
agent logic.

Design invariants:
    - The protocol returns a structured ``AgentModelResult``; it never raises
      for normal model degradation — callers record ``error`` / a fallback
      reason instead.
    - Providers never perform budget math or mutate event state directly.
    - Budget and schedule "truth" lives in the deterministic engines.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

class AgentModelResult(BaseModel):
    """Result of a single ``generate_structured`` call across any provider.

    ``parsed`` is the target Pydantic schema when the provider succeeded, else
    ``None``. ``raw_text`` is preserved (when available) so fallbacks and
    diagnostics can show what the model produced.
    """

    model_config = {"extra": "forbid"}

    parsed: BaseModel | None = None  # populated on success; None on any failure
    raw_text: str | None = None
    model_mode: str = "rule_based_fallback"
    model_name: str | None = None
    fallback_reason: str | None = None
    error: str | None = None


@runtime_checkable
class AgentModelProvider(Protocol):
    """The single seam agents use to generate structured output.

    Implementations MUST parse into ``schema``. On any failure to do so
    (degraded model output, schema mismatch, transport error), they return an
    ``AgentModelResult`` with ``parsed=None`` and ``error``/``fallback_reason``
    populated rather than raising. Raising is reserved for programmer errors.
    """

    def generate_structured(
        self,
        *,
        agent_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> AgentModelResult:
        """Generate an instance of ``schema`` from the given prompts."""
