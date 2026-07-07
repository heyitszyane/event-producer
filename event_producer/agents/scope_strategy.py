"""Scope Strategy Agent — advisory live/fallback scoping layer.

This agent reasons about event scope tradeoffs before the deterministic Budget
Engine and CPM Scheduler run. It never mutates scope, computes final totals, or
executes vendor/state-changing actions.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from event_producer.agents.cards import assemble_system_prompt
from event_producer.models.schemas import (
    AgentMode,
    ScopeStrategyRecommendation,
    ScopeStrategyResult,
)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "scope_strategy_v1.md"


def _load_prompt() -> str:
    return assemble_system_prompt("scope_strategy", _PROMPT_PATH.read_text(encoding="utf-8"))


class ScopeStrategyFormatterAgent:
    """Coerce provider output into a valid ``ScopeStrategyResult``."""

    def run(
        self,
        *,
        provider_text: str | None,
        request: dict[str, Any],
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> ScopeStrategyResult:
        parsed = self._try_parse(provider_text)
        if parsed is not None:
            parsed["model_mode"] = model_mode
            if fallback_reason:
                parsed["fallback_reason"] = fallback_reason
            try:
                return ScopeStrategyResult(**parsed)
            except (TypeError, ValueError):
                # Wrong-shape live output -> deterministic fallback below
                # instead of crashing. (ValidationError subclasses ValueError.)
                fallback_reason = fallback_reason or "live output did not match the expected schema"

        return self._fallback_from_request(
            request=request,
            model_mode=model_mode,
            fallback_reason=fallback_reason,
        )

    @staticmethod
    def _try_parse(text: str | None) -> dict | None:
        if not text:
            return None
        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.S)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _fallback_from_request(
        *,
        request: dict[str, Any],
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> ScopeStrategyResult:
        resolved = request.get("resolved_constraints") or {}
        scope_items = list(request.get("scope_items") or [])
        creative = request.get("creative_concept") or {}
        attendees = resolved.get("attendees")
        budget_cap = _decimal_or_none(resolved.get("budget_cap"))
        per_head = None
        if budget_cap is not None and attendees:
            try:
                per_head = budget_cap / Decimal(str(attendees))
            except (InvalidOperation, ZeroDivisionError):
                per_head = None

        selected = [item for item in scope_items if item.get("selected", True)]
        musts = [item.get("name", "Must-have scope") for item in selected if item.get("tier") == "must"]
        shoulds = [item.get("name", "Should-have scope") for item in selected if item.get("tier") == "should"]

        budget_pressure: Literal["low", "medium", "high"] = (
            "high" if per_head is not None and per_head < Decimal("60") else "medium"
        )
        tradeoffs = [
            "Protect must-have guest experience and compliance items before premium flourishes.",
            "Treat wow-tier additions as optional until the Budget Engine confirms headroom.",
        ]
        recommendations: list[ScopeStrategyRecommendation] = [
            ScopeStrategyRecommendation(
                title="Protect core operating scope",
                recommendation_type="keep",
                category="operations",
                tier="must",
                rationale=(
                    "Venue, basic staffing, and minimum food/beverage coverage keep the event executable."
                ),
                budget_pressure="low",
                operational_risk="high",
            ),
            ScopeStrategyRecommendation(
                title="Retier premium moments after budget check",
                recommendation_type="retier",
                category="experience",
                tier="could",
                rationale=(
                    "Creative ideas should stay advisory until deterministic costing proves available headroom."
                ),
                budget_pressure=budget_pressure,
                operational_risk="medium",
            ),
        ]
        if per_head is not None and per_head < Decimal("50"):
            tradeoffs.append(
                f"Per-head budget is about ${int(per_head)}; reduce premium scope before cutting safety or core hospitality."
            )
            recommendations.append(
                ScopeStrategyRecommendation(
                    title="Reduce discretionary production",
                    recommendation_type="reduce",
                    category="production",
                    tier="could",
                    rationale="The per-head cap is tight, so discretionary scenic or entertainment spend should flex first.",
                    budget_pressure="high",
                    operational_risk="low",
                )
            )
        if creative.get("suggested_additions"):
            recommendations.append(
                ScopeStrategyRecommendation(
                    title="Stage creative additions as optional",
                    recommendation_type="clarify",
                    category="creative",
                    tier="could",
                    rationale="Creative additions should become user-confirmed scope items only after cost and schedule checks.",
                    budget_pressure=budget_pressure,
                    operational_risk="medium",
                )
            )

        must_logic = []
        if musts:
            must_logic.append(f"Keep must-tier items locked first: {', '.join(musts[:4])}.")
        if shoulds:
            must_logic.append(f"Should-tier items can flex after must coverage: {', '.join(shoulds[:4])}.")
        if not must_logic:
            must_logic.append("Confirm the minimum viable guest journey before approving optional upgrades.")

        return ScopeStrategyResult(
            strategy_summary=(
                "Prioritize executable guest basics, keep creative upgrades advisory, "
                "and let the Budget Engine/Scheduler validate final feasibility."
            ),
            must_have_logic=must_logic,
            tradeoffs=tradeoffs,
            recommendations=recommendations,
            questions_for_user=[
                "Which matters more if tradeoffs are needed: guest comfort, production polish, or headcount?",
            ],
            model_mode=model_mode,
            fallback_reason=fallback_reason,
        )


class ScopeStrategyReasonAgent:
    """Build a strategy request and call the configured model provider."""

    def __init__(self, provider, prompt_version: str = "scope_strategy.v1") -> None:
        self._provider = provider
        self._prompt = _load_prompt()
        self._prompt_version = prompt_version

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        user_prompt = json.dumps(request, default=str, sort_keys=True)
        res = self._provider.generate_structured(
            agent_name="scope_strategy",
            prompt_version=self._prompt_version,
            system_prompt=self._prompt,
            user_prompt=user_prompt,
            schema=ScopeStrategyResult,
        )
        return {
            "provider_text": (json.dumps(res.parsed.model_dump()) if res.parsed else res.raw_text),
            "model_mode": res.model_mode,
            "model_name": res.model_name,
            "prompt_version": self._prompt_version,
            "fallback_reason": res.fallback_reason,
            "error": res.error,
        }


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return None
