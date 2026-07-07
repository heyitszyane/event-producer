"""Creative Concept Agent — proposes event direction + ideas (advisory).

Reason -> Formatter split (matches existing agent style):

- CreativeConceptReasonAgent: resolves env/provider, builds the v1 creative
  prompt on top of the already-normalized brief + intake, calls the provider.
- CreativeConceptFormatterAgent: coerces any provider output into a valid
  ``CreativeConceptResult``. In fallback mode it derives event-specific,
  honest proposals from the intake (never fabricating numbers) and records the
  ``model_mode`` / ``fallback_reason`` honestly.

P7A rule: proposals only. This agent does NOT mutate scope/budget/schedule.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from event_producer.agents.cards import assemble_system_prompt
from event_producer.models.schemas import (
    AgentMode,
    CreativeConceptResult,
    CreativeIdea,
    CreativeScopeSuggestion,
)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "creative_concept_v1.md"


def _load_prompt() -> str:
    return assemble_system_prompt("creative_concept", _PROMPT_PATH.read_text(encoding="utf-8"))


class CreativeConceptFormatterAgent:
    """Coerce provider output into a valid ``CreativeConceptResult``."""

    def run(
        self,
        *,
        provider_text: str | None,
        intake,  # BriefIntakeResult
        model_mode: AgentMode,
        fallback_reason: str | None,
        event_type: str,
        goals: list[str],
        attendees: int | None,
        budget_cap: str | None,
    ) -> CreativeConceptResult:
        parsed = self._try_parse(provider_text)
        if parsed is not None:
            parsed["model_mode"] = model_mode
            if fallback_reason:
                parsed["fallback_reason"] = fallback_reason
            try:
                return CreativeConceptResult(**parsed)
            except (TypeError, ValueError):
                # Wrong-shape live output -> deterministic fallback below
                # instead of crashing. (ValidationError subclasses ValueError.)
                fallback_reason = fallback_reason or "live output did not match the expected schema"

        return self._fallback_from_intake(
            intake=intake,
            event_type=event_type,
            goals=goals,
            attendees=attendees,
            budget_cap=budget_cap,
            model_mode=model_mode,
            fallback_reason=fallback_reason,
        )

    # -- helpers ------------------------------------------------------------

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
    def _fallback_from_intake(
        *,
        intake,  # BriefIntakeResult
        event_type: str,
        goals: list[str],
        attendees: int | None,
        budget_cap: str | None,
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> CreativeConceptResult:
        titles = [
            f"{event_type.replace('_', ' ').title()} Night" if event_type else "Event Night",
            "An Evening With Builders",
            "Connect & Exchange",
        ]

        ideas: list[CreativeIdea] = [
            CreativeIdea(
                title="Curated Networking Circles",
                description="Small, guided conversation rounds so every attendee meets peers outside their usual bubble.",
                tier="should",
                estimated_complexity="medium",
                budget_pressure="low",
                why_it_fits="Matches a networking tone without expensive production.",
            ),
            CreativeIdea(
                title="Short Fireside Chat",
                description="One 15-minute, low-production conversation with a founder or local operator.",
                tier="could",
                estimated_complexity="low",
                budget_pressure="low",
                why_it_fits="High credibility builder; minimal AV and staging.",
            ),
            CreativeIdea(
                title="Subtle Brand Moments",
                description="Quiet, on-brand wayfinding and moments instead of loud signage.",
                tier="could",
                estimated_complexity="medium",
                budget_pressure="medium",
                why_it_fits="Fits a premium-but-not-flashy tone.",
            ),
        ]

        additions = [
            CreativeScopeSuggestion(
                title="Light Welcome Drink",
                description="A concise bar moment that raises the perceived quality of the evening.",
                category="catering",
                tier="should",
                estimated_cost=None,
                budget_pressure="medium",
                action_hint="add",
                rationale="Strong guest-experience signal for a modest, bounded spend.",
            ),
        ]
        if event_type in ("product_launch",):
            additions.append(
                CreativeScopeSuggestion(
                    title="On-stage Demo Slot",
                    description="A 5-minute slot for the product story.",
                    category="program",
                    tier="could",
                    estimated_cost=None,
                    budget_pressure="medium",
                    action_hint="add",
                    rationale="Directly supports a product-launch goal.",
                )
            )

        # Budget-safety: when budget looks tight, propose a cut instead of
        # only additions. We base "tight" on a per-head heuristic.
        cuts: list[CreativeScopeSuggestion] = []
        per_head: float | None = None
        if budget_cap and attendees:
            try:
                per_head = float(budget_cap.replace(",", "")) / max(int(attendees), 1)
            except ValueError:
                per_head = None
        if per_head is not None and per_head < 50:
            cuts.append(
                CreativeScopeSuggestion(
                    title="Reduce to One Premier Moment",
                    description="Consolidate premium spend into a single high-signal experience rather than several modest ones.",
                    category="production",
                    tier="could",
                    estimated_cost=None,
                    budget_pressure="high",
                    action_hint="cut",
                    rationale=f"Per-head budget (~${int(per_head)} pp) is tight; focus spend.",
                )
            )

        risks = ["Confirm date lock before committing vendor lead times."]
        if per_head is not None and per_head < 30:
            risks.append("Very tight per-head budget limits contingency options.")
        if attendees and attendees > 120:
            risks.append("Higher headcount amplifies staffing and egress risk.")

        return CreativeConceptResult(
            event_title_options=titles,
            concept_summary=(
                f"A focused {event_type.replace('_', ' ') if event_type else 'gathering'} "
                f"built around: {', '.join(goals) if goals else 'community and connections'}."
            ),
            experience_principles=[
                "Keep production serve the conversation, not compete with it.",
                "Premium feel through restraint, not through volume.",
                "One memorable centerpiece beats several forgettable ones.",
            ],
            creative_ideas=ideas,
            suggested_additions=additions,
            suggested_cuts_or_reductions=cuts,
            budget_sensitive_notes=(
                [f"Per-head budget is ~${int(per_head)}; prioritize 'should'+'must' tiers."]
                if per_head is not None and per_head < 60
                else []
            ),
            production_risks=risks,
            sponsor_or_partner_hooks=[
                "A quiet title-sponsor brand moment can underwrite the premium feel.",
            ],
            model_mode=model_mode,
        )


class CreativeConceptReasonAgent:
    """Turns a normalized brief + intake into a creative concept via the provider."""

    def __init__(self, provider, prompt_version: str = "creative_concept.v1") -> None:
        self._provider = provider
        self._prompt = _load_prompt()
        self._prompt_version = prompt_version

    def run(self, *, brief: str, intake) -> dict:
        user_msg = (
            "Normalized brief:\n"
            f"{intake.normalized_brief}\n\n"
            f"Extracted event_type: {intake.event_type or '(unknown)'}\n"
            f"Attendees (if any): {intake.attendees}\n"
            f"Budget cap (if any): {intake.budget_cap}\n"
            f"Location (if any): {intake.location}\n"
            f"Goals: {', '.join(intake.goals) if intake.goals else '(none)'}\n\n"
            "Propose a creative direction and event-specific ideas."
        )
        res = self._provider.generate_structured(
            agent_name="creative_concept",
            prompt_version=self._prompt_version,
            system_prompt=self._prompt,
            user_prompt=user_msg,
            schema=CreativeConceptResult,
        )
        return {
            "provider_text": (json.dumps(res.parsed.model_dump()) if res.parsed else res.raw_text),
            "model_mode": res.model_mode,
            "model_name": res.model_name,
            "prompt_version": self._prompt_version,
            "fallback_reason": res.fallback_reason,
            "error": res.error,
        }
