"""P7P — load-bearing skill cards: the registry drives live prompt assembly.

Every LLM agent's reason step appends its registry card's instruction body
to the versioned prompt through the single ``assemble_system_prompt`` seam.
These tests pin that the doctrine served by ``GET /agents`` is the same
doctrine the live model actually receives.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from event_producer.agents import (
    brief_intake,
    creative_concept,
    orchestrator,
    scope_strategy,
    vendor_coordinator,
)
from event_producer.agents.cards import (
    AgentCardError,
    assemble_system_prompt,
    get_agent_card,
)
from event_producer.providers.agent_model import AgentModelResult

# (agent module, registry card name) for every LLM reason step in the build.
LLM_AGENT_MODULES = [
    (orchestrator, "orchestrator"),
    (brief_intake, "brief_intake"),
    (creative_concept, "creative_concept"),
    (scope_strategy, "scope_strategy"),
    (vendor_coordinator, "vendor_copy"),
]


@pytest.mark.parametrize(("module", "card_name"), LLM_AGENT_MODULES)
def test_assembled_prompt_contains_versioned_prompt_and_card_body(module, card_name):
    card = get_agent_card(card_name)
    base = module._PROMPT_PATH.read_text(encoding="utf-8")
    prompt = module._load_prompt()
    assert base.rstrip() in prompt, f"{card_name}: versioned prompt missing"
    assert card["instructions"] in prompt, f"{card_name}: card body not load-bearing"
    assert f"Card: {card['name']} v{card['card_version']}" in prompt


def test_unknown_card_name_is_rejected():
    with pytest.raises(AgentCardError):
        assemble_system_prompt("not_a_card", "base prompt")


class _CapturingProvider:
    """Records every generate_structured call so tests can inspect prompts."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return AgentModelResult(
            parsed=None,
            raw_text=None,
            model_mode="rule_based_fallback",
            model_name="capture-stub",
            fallback_reason="capture stub",
        )


def test_live_reason_step_receives_card_doctrine():
    """End-to-end: the provider call carries the card body, not just the file."""
    provider = _CapturingProvider()
    agent = creative_concept.CreativeConceptReasonAgent(provider)
    intake = SimpleNamespace(
        normalized_brief="A 100-person networking evening with a hard budget cap.",
        event_type="networking",
        attendees=100,
        budget_cap="10000",
        location="Berlin",
        goals=["community"],
    )
    agent.run(brief="A 100-person networking evening.", intake=intake)

    assert len(provider.calls) == 1
    system_prompt = provider.calls[0]["system_prompt"]
    card = get_agent_card("creative_concept")
    assert card["instructions"] in system_prompt
