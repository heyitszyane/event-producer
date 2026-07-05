"""Agent skill-card registry loader.

Each markdown file under ``agents/cards/`` is one agent skill card: a YAML
frontmatter contract (role, kind, capabilities, inputs/outputs, structural
boundaries, runtime wiring) plus a markdown instruction body. The directory
of files is the registry — this module parses and validates it so the API
can serve the crew contracts to the frontend (``GET /agents``) and tests can
reject cards that drift from the runtime.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CARDS_DIR = Path(__file__).parent / "cards"

# Contract fields every card must declare (see cards/README.md).
REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "title",
    "kind",
    "order",
    "card_version",
    "purpose",
    "capabilities",
    "input",
    "output",
    "boundaries",
    "runtime",
    "ui",
)

ALLOWED_KINDS: frozenset[str] = frozenset(
    {"llm_agent", "rule_based_agent", "deterministic_engine", "structural_gate"}
)

# Artifact names the casefile store actually writes; a card claiming any
# other artifact is dishonest and rejected.
KNOWN_ARTIFACTS: frozenset[str] = frozenset(
    {
        "brief-intake",
        "creative-concept",
        "scope-strategy",
        "budget-summary",
        "run-sheet",
        "vendor-copy",
        "risk-review",
    }
)

# SpecialistAgentId values accepted by run_specialist_agent.
DIRECT_AGENT_IDS: frozenset[str] = frozenset(
    {"creative_concept", "scope_strategy", "vendor_copy", "risk_review"}
)


class AgentCardError(ValueError):
    """Raised when an agent card is malformed or contradicts the runtime."""


def _parse_card(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AgentCardError(f"{path.name}: missing YAML frontmatter block")
    try:
        end = text.index("\n---", 4)
    except ValueError as exc:
        raise AgentCardError(f"{path.name}: unterminated frontmatter block") from exc

    front = yaml.safe_load(text[4:end])
    if not isinstance(front, dict):
        raise AgentCardError(f"{path.name}: frontmatter is not a mapping")

    missing = [field for field in REQUIRED_FIELDS if field not in front]
    if missing:
        raise AgentCardError(f"{path.name}: missing contract fields {missing}")
    if front["kind"] not in ALLOWED_KINDS:
        raise AgentCardError(f"{path.name}: unknown kind {front['kind']!r}")

    artifact = (front.get("output") or {}).get("artifact")
    if artifact is not None and artifact not in KNOWN_ARTIFACTS:
        raise AgentCardError(f"{path.name}: unknown output artifact {artifact!r}")

    direct_id = (front.get("runtime") or {}).get("direct_agent_id")
    if direct_id is not None and direct_id not in DIRECT_AGENT_IDS:
        raise AgentCardError(f"{path.name}: unknown direct_agent_id {direct_id!r}")

    # llm_agent cards must point at a real versioned prompt file; non-LLM
    # kinds must not claim model routing.
    routing = front.get("model_routing")
    if front["kind"] == "llm_agent":
        prompt_rel = (routing or {}).get("prompt")
        if not prompt_rel:
            raise AgentCardError(f"{path.name}: llm_agent card missing model_routing.prompt")
        if not (Path(__file__).parent / prompt_rel).is_file():
            raise AgentCardError(f"{path.name}: prompt file {prompt_rel!r} does not exist")
    elif routing is not None:
        raise AgentCardError(f"{path.name}: non-LLM card must not declare model_routing")

    front["instructions"] = text[end + 4 :].lstrip("-").strip()
    front["source_file"] = f"event_producer/agents/cards/{path.name}"
    return front


@lru_cache(maxsize=1)
def _load_cards_cached() -> tuple[dict[str, Any], ...]:
    cards = [
        _parse_card(path)
        for path in sorted(_CARDS_DIR.glob("*.md"))
        if path.name != "README.md"
    ]
    names = [card["name"] for card in cards]
    if len(names) != len(set(names)):
        raise AgentCardError(f"duplicate card names in registry: {sorted(names)}")
    cards.sort(key=lambda card: int(card["order"]))
    return tuple(cards)


def load_agent_cards() -> list[dict[str, Any]]:
    """Return the validated crew registry, ordered for display."""
    # Copies keep callers from mutating the cached contracts.
    return [dict(card) for card in _load_cards_cached()]
