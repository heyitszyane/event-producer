"""Agent model provider seam.

This is the moat between the agents and any concrete model backend. Agents call
the ``AgentModelProvider`` protocol; the concrete implementation is chosen by
the composition root based on ``ModelEnv``. This keeps agents swappable across
live model providers, rule-based fallback, or mocked/test providers without
touching agent logic.

Design invariants:
    - The protocol returns a structured ``AgentModelResult``; it never raises
      for normal model degradation — callers record ``error`` / a fallback
      reason instead.
    - Providers never perform budget math or mutate event state directly.
    - Budget and schedule "truth" lives in the deterministic engines.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class LiveModelProviderError(RuntimeError):
    """Typed strict-live failure raised by live provider calls."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        effective_mode: str,
        model_name: str | None,
        agent_name: str | None,
        prompt_version: str | None,
        http_status: int | None = None,
        response_shape_keys: list[str] | None = None,
        fallback_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.effective_mode = effective_mode
        self.model_name = model_name
        self.agent_name = agent_name
        self.prompt_version = prompt_version
        self.http_status = http_status
        self.response_shape_keys = response_shape_keys or []
        self.fallback_reason = fallback_reason


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
    provider: str | None = None
    effective_mode: str | None = None
    agent_name: str | None = None
    prompt_version: str | None = None
    ok: bool = False
    latency_ms: int | None = None
    http_status: int | None = None
    response_shape_keys: list[str] = []
    response_preview: str | None = None

    def diagnostic_dump(self) -> dict[str, Any]:
        """Return non-secret provider diagnostics suitable for API responses."""
        return {
            "provider": self.provider,
            "effective_mode": self.effective_mode or self.model_mode,
            "model_name": self.model_name,
            "agent_name": self.agent_name,
            "prompt_version": self.prompt_version,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "http_status": self.http_status,
            "response_shape_keys": self.response_shape_keys,
            "fallback_reason": self.fallback_reason,
            "error": self.error,
            "response_preview": self.response_preview or self.raw_text,
        }


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
