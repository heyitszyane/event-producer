"""Action-gate enforcement — structural security boundary.

No financial or state-changing action executes without a human Approval.
This is enforced in code, not in prompts. The gate is structural:
even if the LLM is fooled by an injection, no action fires without
an Approval object with status "approved".
"""

from __future__ import annotations

from event_producer.models.schemas import Approval


# Actions that require human approval
_GATED_ACTIONS: frozenset[str] = frozenset({
    "change_payment_details",
    "mark_paid",
    "reschedule",
    "change_scope",
    "send_vendor_message",
    "approve_budget",
    "lock_scope",
    "release_funds",
})


def requires_approval(action: str) -> bool:
    """Check if an action requires human approval."""
    return action in _GATED_ACTIONS


def enforce(action: str, approval: Approval | None) -> None:
    """Enforce the action-gate.

    Args:
        action: The action being attempted.
        approval: The Approval object, or None.

    Raises:
        PermissionError: If the action requires approval and no valid
            approval is provided.
    """
    if not requires_approval(action):
        return  # Non-gated action — no approval needed

    if approval is None:
        raise PermissionError(
            f"Action '{action}' requires human approval but no Approval was provided."
        )
    if approval.status != "approved":
        raise PermissionError(
            f"Action '{action}' requires human approval but Approval status is "
            f"'{approval.status}' (expected 'approved')."
        )
    if not approval.approved_by:
        raise PermissionError(
            f"Action '{action}' requires human approval but Approval has no approver."
        )
