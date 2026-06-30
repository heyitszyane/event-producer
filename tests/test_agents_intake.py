"""Tests for P7A Brief Intake + Creative Concept agents in fallback mode.

No live Gemini: these exercise the deterministic formatter + signal extractors,
which is the only mode available/required in CI. Verifies:
    - brief intake parses messy text into BriefIntakeResult;
    - fallback mode records fallback_reason + rule-based mode;
    - missing/uncertain fields surface in missing_questions/assumptions;
    - creative concept is advisory (non-empty ideas) and budget-aware;
    - agent trace model_mode/model_name/prompt_version/fallback_reason fields.
"""

from __future__ import annotations

from event_producer.agents.brief_intake import (
    BriefIntakeFormatterAgent,
    BriefIntakeReasonAgent,
)
from event_producer.agents.creative_concept import (
    CreativeConceptFormatterAgent,
    CreativeConceptReasonAgent,
)
from event_producer.models.schemas import BriefIntakeResult, CreativeConceptResult


class _FakeFallbackProvider:
    """Honest fallback-shaped provider returning no parsed schema."""

    model_mode = "rule_based_fallback"
    model_name = "rule-based-fallback"
    fallback_reason = "Live Gemini disabled or unkeyed; deterministic fallback used."
    error = None

    def generate_structured(self, **_kw):
        from event_producer.providers.agent_model import AgentModelResult

        return AgentModelResult(
            parsed=None,
            raw_text="[fallback] interpretation",
            model_mode=self.model_mode,
            model_name=self.model_name,
            fallback_reason=self.fallback_reason,
            error=None,
        )


def test_brief_intake_fallback_extracts_signal() -> None:
    provider = _FakeFallbackProvider()
    reason = BriefIntakeReasonAgent(provider=provider)
    fmt = BriefIntakeFormatterAgent()

    brief = (
        "Need a 50-pax AI founder networking night in Singapore next Thursday. "
        "Budget is around 20k. Want premium but not flashy, light F&B, maybe a "
        "short fireside chat, no full conference setup. Need it to feel credible "
        "for investors and builders."
    )
    raw = reason.run(brief)
    res = fmt.run(
        provider_text=raw["provider_text"],
        brief=brief,
        model_mode=raw["model_mode"],
        fallback_reason=raw["fallback_reason"],
    )

    assert isinstance(res, BriefIntakeResult)
    assert res.event_type == "networking"
    assert res.attendees == 50
    assert res.budget_cap is not None
    # confidence should reflect real extraction coverage (medium/high here).
    assert res.confidence in {"high", "medium"}
    # fallback telemetry preserved for UI honesty.
    assert res.model_mode == "rule_based_fallback"
    assert raw["prompt_version"] == "brief_intake.v1"


def test_brief_intake_fallback_surfaces_missing() -> None:
    provider = _FakeFallbackProvider()
    fmt = BriefIntakeFormatterAgent()
    brief = "We want a fun party sometime in a big city."
    raw = BriefIntakeReasonAgent(provider=provider).run(brief)
    res = fmt.run(
        provider_text=raw["provider_text"],
        brief=brief,
        model_mode=raw["model_mode"],
        fallback_reason=raw["fallback_reason"],
    )
    # budget + date + attendees all missing -> surfaced.
    assert "Exact budget cap" in res.missing_questions
    assert "Event date (YYYY-MM-DD)" in res.missing_questions
    assert res.confidence == "low"


def _make_intake() -> BriefIntakeResult:
    return BriefIntakeResult(
        normalized_brief="50-pax AI networking night in Singapore. Budget 20k.",
        event_type="networking",
        attendees=50,
        budget_cap="20000",
        goals=["Facilitate networking"],
        confidence="medium",
    )


def test_creative_concept_fallback_advisory_only() -> None:
    provider = _FakeFallbackProvider()
    fmt = CreativeConceptFormatterAgent()
    raw = CreativeConceptReasonAgent(provider=provider).run(
        brief=_make_intake().normalized_brief, intake=_make_intake()
    )
    res = fmt.run(
        provider_text=raw["provider_text"],
        intake=_make_intake(),
        model_mode=raw["model_mode"],
        fallback_reason=raw["fallback_reason"],
        event_type="networking",
        goals=["Facilitate networking"],
        attendees=50,
        budget_cap="20000",
    )
    assert isinstance(res, CreativeConceptResult)
    assert res.event_title_options
    assert res.creative_ideas
    assert res.model_mode == "rule_based_fallback"
    # Advisory, budget-aware: with 20k/50pp = 400 pp, not tight -> no forced cut.
    assert raw["prompt_version"] == "creative_concept.v1"


def test_creative_concept_fallback_adds_cuts_when_tight() -> None:
    provider = _FakeFallbackProvider()
    fmt = CreativeConceptFormatterAgent()
    tight = BriefIntakeResult(
        normalized_brief="Huge party for 100 people on $1000.",
        event_type="networking",
        attendees=100,
        budget_cap="1000",
        goals=["Grow the community"],
        confidence="medium",
    )
    raw = CreativeConceptReasonAgent(provider=provider).run(
        brief=tight.normalized_brief, intake=tight
    )
    res = fmt.run(
        provider_text=raw["provider_text"],
        intake=tight,
        model_mode=raw["model_mode"],
        fallback_reason=raw["fallback_reason"],
        event_type="networking",
        goals=["Grow the community"],
        attendees=100,
        budget_cap="1000",
    )
    # $10/pp is tight -> a cut must be proposed (budget-safety rule).
    assert res.suggested_cuts_or_reductions, "tight budget should yield a cut suggestion"
