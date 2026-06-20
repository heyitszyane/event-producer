"""Orchestrator agent — top-level coordinator.

The orchestrator routes incoming messages to the appropriate specialized
agent. It never plans, codes, or judges its own work — it delegates to
the planner/generator/evaluator pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore


class OrchestratorAgent:
    """Top-level coordinator that routes messages to specialized agents.

    The orchestrator owns no domain logic itself. It inspects the incoming
    message and context, then returns a routing decision indicating which
    agent should handle the request.
    """

    def __init__(self, event_store: EventStore) -> None:
        """Initialize the orchestrator with required provider interfaces.

        Args:
            event_store: Abstract event store interface for reading/writing
                event state.
        """
        self._event_store = event_store

    def route(self, message: str, context: dict) -> dict:
        """Route a message to the appropriate agent.

        Args:
            message: The incoming message text from the user.
            context: Current event context (event_id, state, etc.).

        Returns:
            A routing decision dict with keys:
                - agent: str — the target agent name
                - confidence: float — routing confidence score (0.0 to 1.0)
        """
        # TODO: implement routing logic (LLM-based classification)
        return {"agent": "unknown", "confidence": 0.0}
