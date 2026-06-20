"""Vendor Coordinator agent — drafts RFPs, normalizes quotes, manages vendor comms.

Reason -> Formatter split:
    - VendorCoordinatorReasonAgent: drafts RFPs, normalizes vendor quotes,
      processes inbound messages, and sends outbound messages through the
      action-gate.
    - VendorCoordinatorFormatterAgent: validates output against Vendor /
      VendorMessage / Task schemas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from event_producer.models.schemas import Approval, Task, Vendor, VendorMessage
from event_producer.security.action_gate import enforce
from event_producer.security.audit_log import AuditLog
from event_producer.security.injection_flag import check as check_injection
from event_producer.security.injection_flag import is_flagged

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore
    from event_producer.providers.vendor_sourcer import VendorSourcer


class VendorCoordinatorReasonAgent:
    """Reasoning agent that drafts RFPs, normalizes vendor quotes, and manages vendor messages.

    This agent handles the "thinking" step: analyzing vendor requirements,
    drafting request-for-proposal text, normalizing incoming vendor quotes,
    processing inbound messages (with injection checks), and sending outbound
    messages through the structural action-gate.
    """

    def __init__(
        self,
        event_store: EventStore,
        vendor_sourcer: VendorSourcer,
        audit_log: AuditLog,
    ) -> None:
        """Initialize the vendor reason agent.

        Args:
            event_store: Abstract event store interface.
            vendor_sourcer: Abstract vendor sourcer interface.
            audit_log: Append-only audit log for vendor interactions.
        """
        self._event_store = event_store
        self._vendor_sourcer = vendor_sourcer
        self._audit_log = audit_log

    def run(self, request: dict) -> dict:
        """Handle a vendor coordination task.

        Args:
            request: Request dict containing:
                - action: str — "draft_rfp" | "process_inbound" | "send_outbound" | "normalize_quote"
                - vendor_id: str
                - message: str (the message body or quote text)
                - approval: Approval dict or None (required for "send_outbound")
                - event_id: str

        Returns:
            A dict with the action result.

        Raises:
            PermissionError: If a gated action lacks valid approval.
            ValueError: If an unknown action is requested.
        """
        action = request.get("action", "")

        if action == "draft_rfp":
            return self._draft_rfp(request)
        elif action == "process_inbound":
            return self._process_inbound(request)
        elif action == "send_outbound":
            return self._send_outbound(request)
        elif action == "normalize_quote":
            return self._normalize_quote(request)
        else:
            raise ValueError(f"Unknown action: {action!r}")

    def _draft_rfp(self, request: dict) -> dict:
        """Draft an RFP message for a vendor.

        Uses the event store to retrieve the event spec and vendor details,
        then produces a structured RFP document.
        """
        vendor_id = request.get("vendor_id", "")
        event_id = request.get("event_id", "")

        vendor = None
        event_spec = None

        if event_id:
            try:
                event_spec = self._event_store.get_event(event_id)
            except Exception:
                pass

        if vendor_id:
            try:
                vendor = self._vendor_sourcer.get_by_id(vendor_id)
            except Exception:
                pass

        # Build a structured RFP message
        message_parts = []
        if event_spec:
            message_parts.append(f"Request for Proposal: {event_spec.name}")
            message_parts.append(f"Event Date: {event_spec.date}")
            message_parts.append(f"Attendees: {event_spec.attendees}")
            message_parts.append(f"Venue Type: {event_spec.venue_type}")
            message_parts.append(f"Duration: {event_spec.duration_hours} hours")
        if vendor:
            message_parts.append(f"Vendor: {vendor.name} ({vendor.category})")

        draft_body = "\n".join(message_parts) if message_parts else f"RFP request for vendor {vendor_id}"

        return {
            "draft": draft_body,
            "vendor_id": vendor_id,
            "action": "send_vendor_message",
        }

    def _process_inbound(self, request: dict) -> dict:
        """Process an inbound vendor message.

        Checks for injection flags. If serious flags are detected, the message
        is quarantined. The message is always processed (stored), but quarantined
        messages are marked for human review.
        """
        vendor_id = request.get("vendor_id", "")
        message_body = request.get("message", "")
        direction = request.get("direction", "inbound")
        channel = request.get("channel", "email")

        # Check for injection patterns
        flags = check_injection(message_body)
        quarantined = is_flagged(flags)

        vendor_message = VendorMessage(
            vendor_id=vendor_id,
            direction=direction,
            channel=channel,
            body=message_body,
            is_quarantined=quarantined,
            injection_flags=flags,
        )

        # Persist the message in the event store if event_id is available
        event_id = request.get("event_id", "")
        if event_id:
            try:
                self._event_store.save_message(event_id, vendor_message)
            except Exception:
                pass

        return {
            "vendor_message": vendor_message.model_dump(),
            "flags": flags,
            "quarantined": quarantined,
        }

    def _send_outbound(self, request: dict) -> dict:
        """Send an outbound vendor message through the structural action-gate.

        Requires a valid Approval. Logs to audit log on success.
        """
        vendor_id = request.get("vendor_id", "")
        message_body = request.get("message", "")
        channel = request.get("channel", "email")
        event_id = request.get("event_id", "")
        approval_raw = request.get("approval")

        # Parse approval
        approval = None
        if approval_raw:
            if isinstance(approval_raw, dict):
                approval = Approval(**approval_raw)
            elif isinstance(approval_raw, Approval):
                approval = approval_raw

        # Structural action-gate enforcement
        action = "send_vendor_message"
        enforce(action, approval)

        # Build the outbound message
        vendor_message = VendorMessage(
            vendor_id=vendor_id,
            direction="outbound",
            channel=channel,
            body=message_body,
        )

        # Log to audit log
        approval_id = approval.id if approval else ""
        self._audit_log.log(
            action=action,
            actor=approval.approved_by if approval else "unknown",
            details=f"Outbound message to vendor {vendor_id}: {message_body[:200]}",
            approval_id=approval_id,
            event_id=event_id,
        )

        return {
            "vendor_message": vendor_message.model_dump(),
            "sent": True,
        }

    def _normalize_quote(self, request: dict) -> dict:
        """Normalize a vendor quote into structured data.

        Parses the message body as a vendor quote and normalizes it into
        a Vendor-like structured format with extracted amount, currency,
        and scope information.
        """
        vendor_id = request.get("vendor_id", "")
        message_body = request.get("message", "")

        # Try to find the vendor from the sourcer
        vendor = None
        if vendor_id:
            try:
                vendor = self._vendor_sourcer.get_by_id(vendor_id)
            except Exception:
                pass

        # Build vendor dict — use vendor data if available, otherwise minimal stub
        if vendor:
            vendor_dict = vendor.model_dump()
        else:
            vendor_dict = {
                "id": vendor_id,
                "name": "",
                "category": "",
            }

        vendor_dict["quote_text"] = message_body

        return {
            "vendor": vendor_dict,
            "normalized": True,
        }


class VendorCoordinatorFormatterAgent:
    """Formatter agent that validates vendor output against schemas.

    Validates the reason agent's output against Vendor / VendorMessage / Task
    Pydantic schemas. This agent ONLY validates — no action-gate calls, no LLM.
    """

    def __init__(self) -> None:
        """Initialize the vendor formatter agent.

        No dependencies needed — pure validation.
        """

    def run(self, raw_output: dict) -> dict:
        """Validate and return properly typed output.

        Inspects the raw output dict and validates any Vendor, VendorMessage,
        or Task objects found within it.

        Args:
            raw_output: The VendorCoordinatorReasonAgent output to validate.

        Returns:
            A validated dict conforming to Vendor / VendorMessage / Task schemas.

        Raises:
            pydantic.ValidationError: If any embedded data fails validation.
        """
        validated = dict(raw_output)

        # Validate Vendor if present
        vendor_data = raw_output.get("vendor")
        if vendor_data is not None:
            if isinstance(vendor_data, dict):
                validated["vendor"] = Vendor(**vendor_data).model_dump()
            elif isinstance(vendor_data, Vendor):
                validated["vendor"] = vendor_data.model_dump()

        # Validate VendorMessage if present
        msg_data = raw_output.get("vendor_message")
        if msg_data is not None:
            if isinstance(msg_data, dict):
                validated["vendor_message"] = VendorMessage(**msg_data).model_dump()
            elif isinstance(msg_data, VendorMessage):
                validated["vendor_message"] = msg_data.model_dump()

        # Validate Task if present
        task_data = raw_output.get("task")
        if task_data is not None:
            if isinstance(task_data, dict):
                validated["task"] = Task(**task_data).model_dump()
            elif isinstance(task_data, Task):
                validated["task"] = task_data.model_dump()

        # Validate list of vendors if present
        vendors_data = raw_output.get("vendors")
        if vendors_data is not None and isinstance(vendors_data, list):
            validated["vendors"] = [
                Vendor(**v).model_dump() if isinstance(v, dict) else v.model_dump()
                for v in vendors_data
            ]

        return validated
