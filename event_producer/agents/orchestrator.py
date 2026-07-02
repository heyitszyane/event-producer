"""Live-backed orchestrator agent that returns safe proposed actions.

The orchestrator is the user-facing "Ask the AI Producer" surface. It may
reason over the current event casefile and propose actions, but it never
mutates state directly. Proposal application remains an explicit API action.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from event_producer.models.schemas import (
    AgentMode,
    OrchestratorAgentResult,
    OrchestratorChatResponse,
    ProposedAction,
)

if TYPE_CHECKING:
    from event_producer.providers.agent_model import AgentModelProvider
    from event_producer.providers.event_store import EventStore

_PROMPT_PATH = Path(__file__).parent / "prompts" / "orchestrator_v1.md"
_ALLOWED_ACTION_TYPES = {
    "add_scope_item",
    "update_scope_item",
    "delete_scope_item",
    "retier_scope_item",
    "toggle_scope_item",
    "add_risk_flag",
    "request_clarification",
    "create_approval",
}
_APPROVAL_GATED_ACTION_TYPES = {"create_approval"}
_STATEFUL_ACTION_TYPES = {
    "add_scope_item",
    "update_scope_item",
    "delete_scope_item",
    "retier_scope_item",
    "toggle_scope_item",
    "add_risk_flag",
    "create_approval",
}
_VENDOR_PAYMENT_WORDS = (
    "vendor",
    "payment",
    "invoice",
    "pay",
    "deposit",
    "contract",
    "rfp",
    "email",
    "message",
    "send",
    "book",
)


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


class OrchestratorAgent:
    """Produces live or fallback proposed actions without direct mutation."""

    def __init__(self, event_store: EventStore, provider: AgentModelProvider) -> None:
        self._event_store = event_store
        self._provider = provider
        self._prompt = _load_prompt()
        self._prompt_version = "orchestrator.v1"

    def run(self, message: str, context: dict[str, Any]) -> OrchestratorChatResponse:
        """Generate proposed actions from the message and event context."""
        compact_context = self._compact_context(context)
        user_prompt = json.dumps(
            {
                "user_request": message,
                "casefile": compact_context,
            },
            default=str,
            sort_keys=True,
        )

        res = self._provider.generate_structured(
            agent_name="orchestrator",
            prompt_version=self._prompt_version,
            system_prompt=self._prompt,
            user_prompt=user_prompt,
            schema=OrchestratorAgentResult,
        )

        if isinstance(res.parsed, OrchestratorAgentResult):
            proposals = self._sanitize_proposals(
                res.parsed.proposals,
                model_mode=_coerce_model_mode(res.model_mode),
            )
            return OrchestratorChatResponse(
                reply=res.parsed.reply.strip() or "I reviewed the casefile and proposed the safest next steps.",
                proposals=proposals,
                model_mode=_coerce_model_mode(res.model_mode),
                fallback_reason=None,
            )

        fallback = self._heuristic_fallback(
            message=message,
            context=compact_context,
            fallback_reason=res.fallback_reason or res.error or "live orchestrator provider unavailable",
        )
        return fallback

    def _compact_context(self, context: dict[str, Any]) -> dict[str, Any]:
        event_spec = context.get("event_spec") or {}
        scope_items = list(context.get("scope_items") or [])
        selected_scope = [item for item in scope_items if item.get("selected", True)]
        budget = context.get("budget_summary") or {}
        schedule = context.get("schedule_result") or {}
        approvals = list(context.get("approvals") or [])
        risk_flags = list(context.get("risk_flags") or [])

        return {
            "event_id": context.get("event_id"),
            "event_spec": {
                "name": event_spec.get("name"),
                "event_type": event_spec.get("event_type"),
                "attendees": event_spec.get("attendees"),
                "date": event_spec.get("date"),
                "venue_type": event_spec.get("venue_type"),
                "budget_cap": event_spec.get("budget_cap"),
            },
            "selected_scope_items": [
                {
                    "name": item.get("name"),
                    "category": item.get("category"),
                    "tier": item.get("tier"),
                    "qty": str(item.get("qty", "1")),
                    "estimated_cost": str(item.get("estimated_cost", "0")),
                }
                for item in selected_scope[:12]
            ],
            "budget": {
                "headroom": str(budget.get("headroom", "0")),
                "over_budget": bool(budget.get("over_budget", False)),
                "tier_rollups": budget.get("tier_rollups", {}),
            },
            "schedule": {
                "task_count": len(schedule.get("ordered_tasks") or []),
                "critical_path": schedule.get("critical_path") or [],
            },
            "pending_approvals_count": len(
                [a for a in approvals if a.get("status") == "pending"]
            ),
            "risks": [
                flag.get("message") or flag.get("title") or str(flag)
                for flag in risk_flags[:6]
            ],
        }

    def _sanitize_proposals(
        self,
        proposals: list[Any],
        *,
        model_mode: AgentMode,
    ) -> list[ProposedAction]:
        sanitized: list[ProposedAction] = []
        for raw in proposals[:5]:
            proposal = raw.model_dump() if isinstance(raw, ProposedAction) else dict(raw or {})
            action_type = str(proposal.get("type") or "")
            if action_type not in _ALLOWED_ACTION_TYPES:
                continue

            payload = dict(proposal.get("payload") or {})
            requires_gate = bool(proposal.get("requires_approval_gate"))
            if action_type in _APPROVAL_GATED_ACTION_TYPES or self._payload_needs_gate(payload):
                requires_gate = True

            try:
                sanitized.append(
                    ProposedAction(
                        id=str(proposal.get("id") or "").strip() or f"prop_{uuid.uuid4().hex[:8]}",
                        type=cast(Any, action_type),
                        title=str(proposal.get("title") or "").strip()[:160]
                        or _default_title(action_type),
                        rationale=str(proposal.get("rationale") or "").strip()[:600]
                        or "Recommended by the AI Producer after reviewing the casefile.",
                        payload=self._sanitize_payload(action_type, payload),
                        requires_confirmation=True,
                        requires_approval_gate=requires_gate
                        or action_type in _STATEFUL_ACTION_TYPES and action_type == "create_approval",
                        model_mode=model_mode,
                        created_at=str(proposal.get("created_at") or "")
                        or datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception:
                continue
        return sanitized

    def _sanitize_payload(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action_type == "add_scope_item":
            return {
                "name": str(payload.get("name") or "Proposed scope item")[:120],
                "description": str(payload.get("description") or "")[:500],
                "category": str(payload.get("category") or "other")[:80],
                "tier": _coerce_tier(payload.get("tier")),
                "estimated_cost": str(payload.get("estimated_cost") or "0"),
                "currency": str(payload.get("currency") or "USD")[:3].upper(),
                "qty": str(payload.get("qty") or "1"),
                "selected": bool(payload.get("selected", True)),
            }
        if action_type in {"toggle_scope_item", "delete_scope_item"}:
            return {
                "name": str(payload.get("name") or "")[:120],
                "selected": bool(payload.get("selected", False)),
            }
        if action_type in {"retier_scope_item", "update_scope_item"}:
            safe_payload = {k: v for k, v in payload.items() if k in {"name", "tier", "description", "category", "selected"}}
            if "tier" in safe_payload:
                safe_payload["tier"] = _coerce_tier(safe_payload["tier"])
            return safe_payload
        if action_type == "add_risk_flag":
            return {
                "message": str(payload.get("message") or payload.get("title") or "Review operational risk")[:400],
                "severity": str(payload.get("severity") or "medium")[:40],
            }
        if action_type == "request_clarification":
            return {"question": str(payload.get("question") or "Can you clarify the priority?")[:400]}
        if action_type == "create_approval":
            return {
                "action": str(payload.get("action") or "review_approval_gated_action")[:120],
                "notes": str(payload.get("notes") or payload.get("message") or "")[:600],
            }
        return {}

    def _payload_needs_gate(self, payload: dict[str, Any]) -> bool:
        text = json.dumps(payload, default=str).lower()
        return any(word in text for word in _VENDOR_PAYMENT_WORDS)

    def _heuristic_fallback(
        self,
        *,
        message: str,
        context: dict[str, Any],
        fallback_reason: str,
    ) -> OrchestratorChatResponse:
        scope_items = context.get("selected_scope_items", [])
        budget = context.get("budget", {})
        headroom = _decimal(budget.get("headroom"))
        proposals: list[ProposedAction] = []
        reply = self._generate_reply(message, scope_items, headroom)

        msg_lower = message.lower()
        if "premium" in msg_lower or "upgrade" in msg_lower:
            if headroom > Decimal("1000"):
                premium_suggestions = self._suggest_premium_upgrades(headroom)
                proposals.extend(premium_suggestions)
                reply += f"\n\nFound {len(premium_suggestions)} premium upgrade option(s) within budget headroom."
            else:
                reply += "\n\nHeadroom is low, so I would cut or retier before adding premium scope."

        if "cut" in msg_lower or "reduce" in msg_lower or "save" in msg_lower:
            cut_suggestions = self._suggest_cuts(scope_items)
            proposals.extend(cut_suggestions)
            reply += f"\n\nFound {len(cut_suggestions)} cut/reduction suggestion(s)."

        return OrchestratorChatResponse(
            reply=reply,
            proposals=proposals,
            model_mode="rule_based_fallback",
            fallback_reason=fallback_reason,
        )

    def _generate_reply(self, message: str, scope_items: list[dict[str, Any]], headroom: Decimal) -> str:
        item_count = len(scope_items)
        return (
            f"Analyzing your request: '{message}'. "
            f"Event has {item_count} selected scope items and ${headroom:,.0f} headroom."
        )

    def _suggest_premium_upgrades(self, headroom: Decimal) -> list[ProposedAction]:
        max_suggestion = min(headroom, Decimal("5000"))
        if max_suggestion < Decimal("1500"):
            return []
        return [
            ProposedAction(
                id=f"prop_{uuid.uuid4().hex[:8]}",
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
        ]

    def _suggest_cuts(self, scope_items: list[dict[str, Any]]) -> list[ProposedAction]:
        proposals: list[ProposedAction] = []
        for item in scope_items:
            cost = _decimal(item.get("estimated_cost")) * _decimal(item.get("qty") or "1")
            if cost > Decimal("1000"):
                proposals.append(
                    ProposedAction(
                        id=f"prop_{uuid.uuid4().hex[:8]}",
                        type="toggle_scope_item",
                        title=f"Exclude {item.get('name', 'item')}",
                        rationale=f"Removes about ${cost:,.0f} by de-selecting this optional item",
                        payload={"name": item.get("name"), "selected": False},
                        requires_confirmation=True,
                        requires_approval_gate=False,
                        model_mode="rule_based_fallback",
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
                if len(proposals) >= 2:
                    break
        return proposals


def _coerce_model_mode(value: str) -> AgentMode:
    allowed = {
        "gemini_live",
        "openai_compatible_live",
        "rule_based_fallback",
        "deterministic_engine",
        "scripted_fixture",
        "human_approval_gate",
        "not_enabled",
    }
    return value if value in allowed else "rule_based_fallback"  # type: ignore[return-value]


def _coerce_tier(value: Any) -> str:
    return str(value) if str(value) in {"must", "should", "could", "wow"} else "could"


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _default_title(action_type: str) -> str:
    return action_type.replace("_", " ").title()
