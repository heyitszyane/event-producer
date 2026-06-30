"""Orchestrator agent — returns structured proposed actions.

P7B: The orchestrator produces actionable proposals from event context,
NOT direct mutations. All proposals are returned as ProposedAction objects
with explicit type, payload, and requires_confirmation/requires_approval_gate
flags. The human must click Apply before any state change occurs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from event_producer.models.schemas import (
    OrchestratorChatResponse,
    ProposedAction,
)

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore


class OrchestratorAgent:
    """Produces structured proposed actions based on event context.

    The orchestrator analyzes the event state (scope, budget, schedule) and
    the user's message to return actionable proposals. All proposals are
    advisory only — no state mutation occurs until the user explicitly applies
    them via the API.
    """

    def __init__(self, event_store: EventStore) -> None:
        """Initialize the orchestrator with required provider interfaces.

        Args:
            event_store: Abstract event store interface for reading event state.
        """
        self._event_store = event_store

    def run(self, message: str, context: dict) -> OrchestratorChatResponse:
        """Generate proposed actions from the message and event context.

        This is the P7B chat entry point. It returns proposals that the user
        can apply or dismiss. Proposals NEVER mutate state directly.

        Args:
            message: The user's chat message.
            context: Current event context with:
                - event_id: str
                - event_spec: dict
                - scope_items: list[ScopeItem] dicts
                - budget_summary: dict or None

        Returns:
            OrchestratorChatResponse with reply and proposed actions.
        """
        scope_items = context.get("scope_items", [])
        budget_summary = context.get("budget_summary", {})

        # Compute headroom if available
        headroom = Decimal("0")
        if budget_summary:
            headroom = Decimal(str(budget_summary.get("headroom", 0)))

        # Analyze message and generate proposals
        proposals: list[ProposedAction] = []
        reply = self._generate_reply(message, scope_items, headroom)

        # Simple heuristic-based proposal generation (rule-based fallback)
        msg_lower = message.lower()

        # Budget-aware suggestions
        if "premium" in msg_lower or "upgrade" in msg_lower:
            if headroom > Decimal("1000"):
                # Suggest premium upgrades within budget
                premium_suggestions = self._suggest_premium_upgrades(scope_items, headroom)
                proposals.extend(premium_suggestions)
                reply += f"\n\nFound {len(premium_suggestions)} premium upgrade option(s) within budget headroom."
            else:
                reply += "\n\nHeadroom is low — consider a cut first before upgrades."

        if "cut" in msg_lower or "reduce" in msg_lower or "save" in msg_lower:
            cut_suggestions = self._suggest_cuts(scope_items)
            proposals.extend(cut_suggestions)
            reply += f"\n\nFound {len(cut_suggestions)} cut/reduction suggestion(s)."

        return OrchestratorChatResponse(
            reply=reply,
            proposals=proposals,
            model_mode="rule_based_fallback",
            fallback_reason=None,
        )

    def _generate_reply(self, message: str, scope_items: list, headroom: Decimal) -> str:
        """Generate a human-readable reply to the chat message."""
        item_count = len(scope_items)
        return (
            f"Analyzing your request: '{message}'. "
            f"Event has {item_count} scope items and ${headroom:,.0f} headroom."
        )

    def _suggest_premium_upgrades(
        self, scope_items: list, headroom: Decimal
    ) -> list[ProposedAction]:
        """Suggest premium upgrades within available headroom."""
        proposals: list[ProposedAction] = []
        max_suggestion = min(headroom, Decimal("5000"))  # Cap at $5k or headroom

        # Suggest premium catering upgrade (example)
        if max_suggestion >= Decimal("1500"):
            proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
            proposals.append(
                ProposedAction(
                    id=proposal_id,
                    type="add_scope_item",
                    title="Premium catering upgrade",
                    rationale=f"Adds elevated catering within available headroom of ${headroom:,.0f}",
                    payload={
                        "name": "Premium Catering",
                        "description": "Upgraded menu with premium options and bar service",
                        "category": "catering",
                        "tier": "should",
                        "estimated_cost": str(max_suggestion),
                        "currency": "USD",
                        "qty": "1",
                        "selected": True,
                    },
                    requires_confirmation=True,
                    requires_approval_gate=False,
                    model_mode="rule_based_fallback",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        return proposals

    def _suggest_cuts(self, scope_items: list) -> list[ProposedAction]:
        """Suggest items that could be cut or reduced."""
        proposals: list[ProposedAction] = []

        for item in scope_items:
            cost = Decimal(str(item.get("estimated_cost", 0)))
            if cost > Decimal("1000"):
                proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
                proposals.append(
                    ProposedAction(
                        id=proposal_id,
                        type="toggle_scope_item",
                        title=f"Exclude {item.get('name', 'item')}",
                        rationale=f"Removes ${cost:,.0f} by de-selecting this optional item",
                        payload={
                            "name": item.get("name"),
                            "selected": False,
                        },
                        requires_confirmation=True,
                        requires_approval_gate=False,
                        model_mode="rule_based_fallback",
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
                if len(proposals) >= 2:
                    break  # Max 2 cut suggestions

        return proposals
