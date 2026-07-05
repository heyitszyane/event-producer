"""Vendor Coordinator agent — drafts RFPs, normalizes quotes, manages vendor comms.

Reason -> Formatter split:
    - VendorCoordinatorReasonAgent: drafts RFPs, normalizes vendor quotes,
      processes inbound messages, and sends outbound messages through the
      action-gate.
    - VendorCoordinatorFormatterAgent: validates output against Vendor /
      VendorMessage / Task schemas.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

from event_producer.agents.cards import assemble_system_prompt
from event_producer.models.schemas import (
    AgentMode,
    Approval,
    Task,
    Vendor,
    VendorDraftResult,
    VendorMessage,
)
from event_producer.security.action_gate import enforce
from event_producer.security.audit_log import AuditLog
from event_producer.security.injection_flag import check as check_injection
from event_producer.security.injection_flag import is_flagged

if TYPE_CHECKING:
    from event_producer.providers.agent_model import AgentModelProvider
    from event_producer.providers.event_store import EventStore
    from event_producer.providers.vendor_sourcer import VendorSourcer

_PROMPT_PATH = Path(__file__).parent / "prompts" / "vendor_draft_v1.md"


def _load_prompt() -> str:
    return assemble_system_prompt("vendor_copy", _PROMPT_PATH.read_text(encoding="utf-8"))


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
        provider: AgentModelProvider | None = None,
        prompt_version: str = "vendor_draft.v1",
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
        self._provider = provider
        self._prompt = _load_prompt()
        self._prompt_version = prompt_version

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
        if event_spec is None and request.get("event_spec"):
            event_spec = request.get("event_spec")

        if vendor_id:
            try:
                vendor = self._vendor_sourcer.get_by_id(vendor_id)
            except Exception:
                pass

        context = self._draft_context(request, event_spec=event_spec, vendor=vendor)
        if self._provider is not None:
            res = self._provider.generate_structured(
                agent_name="vendor_draft",
                prompt_version=self._prompt_version,
                system_prompt=self._prompt,
                user_prompt=json.dumps(context, default=str, sort_keys=True),
                schema=VendorDraftResult,
            )
            draft_result = VendorDraftFormatterAgent().run(
                provider_text=(res.parsed.model_dump_json() if res.parsed else res.raw_text),
                request=context,
                model_mode=cast(AgentMode, res.model_mode),
                fallback_reason=res.fallback_reason,
            )
            return {
                "draft": draft_result.body,
                "vendor_id": vendor_id,
                "action": "send_vendor_message",
                "vendor_draft": draft_result.model_dump(),
                "model_mode": draft_result.model_mode,
                "model_name": res.model_name,
                "prompt_version": self._prompt_version,
                "fallback_reason": draft_result.fallback_reason,
            }

        draft_result = VendorDraftFormatterAgent().fallback_from_request(
            request=context,
            model_mode="rule_based_fallback",
            fallback_reason="Live vendor draft provider not configured.",
        )
        return {
            "draft": draft_result.body,
            "vendor_id": vendor_id,
            "action": "send_vendor_message",
            "vendor_draft": draft_result.model_dump(),
            "model_mode": draft_result.model_mode,
            "model_name": None,
            "prompt_version": self._prompt_version,
            "fallback_reason": draft_result.fallback_reason,
        }

    def _draft_context(self, request: dict, *, event_spec, vendor) -> dict:
        scope_items = request.get("scope_items") or []
        selected_scope = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in scope_items
            if (item.get("selected", True) if isinstance(item, dict) else getattr(item, "selected", True))
        ]
        schedule_context = request.get("schedule_context") or {}
        vendor_category = request.get("vendor_category") or (vendor.category if vendor else "")
        return {
            "event_spec": (
                event_spec.model_dump()
                if hasattr(event_spec, "model_dump")
                else event_spec
            ) if event_spec else None,
            "selected_scope": selected_scope[:12],
            "schedule_context": schedule_context,
            "vendor": vendor.model_dump() if vendor else None,
            "vendor_category": vendor_category,
            "approval_required": True,
            "safety_rules": [
                "Draft only; prepare copy for review before external use.",
                "Human approval is required before vendor-facing use.",
                "No payment instructions.",
            ],
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


class VendorDraftFormatterAgent:
    """Coerce provider output into a valid ``VendorDraftResult``."""

    def run(
        self,
        *,
        provider_text: str | None,
        request: dict,
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> VendorDraftResult:
        parsed = self._try_parse(provider_text)
        if parsed is not None:
            parsed["model_mode"] = model_mode
            if fallback_reason:
                parsed["fallback_reason"] = fallback_reason
            result = VendorDraftResult(**parsed)
            return self._scrub_payment_instructions(result)

        return self.fallback_from_request(
            request=request,
            model_mode=model_mode,
            fallback_reason=fallback_reason,
        )

    def fallback_from_request(
        self,
        *,
        request: dict,
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> VendorDraftResult:
        event_spec = request.get("event_spec") or {}
        vendor = request.get("vendor") or {}
        vendor_name = vendor.get("name") or "Vendor team"
        category = request.get("vendor_category") or vendor.get("category") or "event services"
        event_name = event_spec.get("name") or "the event"
        event_date = event_spec.get("date") or "the target date"
        attendees = event_spec.get("attendees") or "the expected"

        body = (
            f"Hello {vendor_name},\n\n"
            f"Request for Proposal: We are preparing {event_name} on {event_date} for {attendees} attendees "
            f"and would like a proposal for {category} support.\n\n"
            "Please confirm availability, recommended scope, lead time, itemized quote, "
            "and any operational constraints we should account for.\n\n"
            "This is draft copy only. It requires human review before external use, and "
            "no booking or payment is confirmed by this message.\n\n"
            "Thank you."
        )
        return VendorDraftResult(
            subject=f"RFP request for {event_name}",
            body=body,
            ask_summary=f"Request availability and quote details for {category}.",
            required_vendor_response_fields=[
                "availability",
                "itemized_quote",
                "lead_time",
                "operational_constraints",
            ],
            approval_diff=(
                f"Draft RFP copy for {vendor_name} covering {category}; external use waits for human review."
            ),
            risk_notes=[
                "Human approval required before vendor-facing use.",
                "No payment instructions included.",
            ],
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
    def _scrub_payment_instructions(result: VendorDraftResult) -> VendorDraftResult:
        body = re.sub(
            r"(?im)^.*\b(?:iban|wire|bank account|payment link|pay now|routing number)\b.*$",
            "[Payment instruction removed: human approval wall requires separate review.]",
            result.body,
        )
        risk_notes = list(result.risk_notes)
        if body != result.body:
            risk_notes.append("LLM-supplied payment instruction was removed from the draft.")
        return result.model_copy(update={"body": body, "risk_notes": risk_notes})


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
