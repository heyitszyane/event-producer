"""Vendor Notebook — persistent per-vendor workspace over the casefile store.

One ``vendor-notebook`` artifact per casefile holds every vendor record with
its embedded append-only log and current draft. This is planning metadata for
a solo producer's chase list: workflow status, payment status (user-recorded,
never executed), and a history of drafts/replies/notes. Nothing here sends a
message or moves money — external use stays manual and human-reviewed.

Vendor-supplied text (logged replies) is screened by the injection flagger on
entry; flagged entries are withheld from any LLM prompt context
(data-not-instruction boundary).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Literal

from event_producer.models.schemas import (
    VendorDraftRecord,
    VendorLogEntry,
    VendorLogEntryType,
    VendorPaymentStatus,
    VendorRecord,
    VendorWorkflowStatus,
)
from event_producer.security.injection_flag import check as check_injection
from event_producer.storage.local_casefiles import utc_now

if TYPE_CHECKING:
    from event_producer.models.schemas import CasefileArtifact
    from event_producer.storage.local_casefiles import LocalCasefileStore

ARTIFACT_NAME = "vendor-notebook"

# Older stages auto-advance to later ones; a producer can always set any
# status manually via PATCH.
_WORKFLOW_ORDER: tuple[VendorWorkflowStatus, ...] = (
    "not_started",
    "draft_needed",
    "draft_ready",
    "copied_for_manual_send",
    "manually_sent",
    "awaiting_reply",
    "follow_up_needed",
    "quote_received",
    "contract_pending",
    "confirmed",
    "settled",
)

# Keep per-vendor logs bounded so the artifact stays small and prompt context
# stays cheap; the casefile timeline remains the unbounded audit trail.
_MAX_LOG_ENTRIES = 200

_PAYMENT_FIELDS = (
    "payment_status",
    "quoted_amount",
    "deposit_amount",
    "final_balance_amount",
    "payment_due_date",
    "payment_notes",
)


class VendorNotFoundError(KeyError):
    """Raised when a vendor id is not in the casefile's notebook."""


def _advance(current: VendorWorkflowStatus, target: VendorWorkflowStatus) -> VendorWorkflowStatus:
    """Move workflow forward to ``target`` only if it is a later stage."""
    if _WORKFLOW_ORDER.index(target) > _WORKFLOW_ORDER.index(current):
        return target
    return current


class VendorNotebook:
    """Load/mutate the vendor-notebook artifact through the casefile store."""

    def __init__(self, store: LocalCasefileStore) -> None:
        self._store = store

    # -- reads ---------------------------------------------------------------

    def list_vendors(self, event_id: str) -> list[VendorRecord]:
        # Ensure the casefile exists (raises FileNotFoundError otherwise).
        self._store.get_casefile(event_id)
        try:
            payload = self._store.read_artifact(event_id, ARTIFACT_NAME)
        except FileNotFoundError:
            return []
        vendors = payload.get("vendors", []) if isinstance(payload, dict) else []
        return [VendorRecord(**vendor) for vendor in vendors]

    def get_vendor(self, event_id: str, vendor_id: str) -> VendorRecord:
        for vendor in self.list_vendors(event_id):
            if vendor.id == vendor_id:
                return vendor
        raise VendorNotFoundError(vendor_id)

    def prompt_context_for(self, event_id: str, vendor_id: str, *, max_log_entries: int = 10) -> dict[str, Any]:
        """Selected-vendor context for an LLM call — never other vendors' logs.

        Injection-flagged log bodies are withheld from the prompt and replaced
        with an explicit marker, so vendor text stays data, not instruction.
        """
        vendor = self.get_vendor(event_id, vendor_id)
        recent: list[dict[str, Any]] = []
        for entry in vendor.log[-max_log_entries:]:
            body = entry.body
            if entry.injection_flags:
                body = (
                    "[vendor-supplied text withheld from prompt; injection flags: "
                    f"{', '.join(entry.injection_flags)}]"
                )
            recent.append(
                {
                    "timestamp": entry.timestamp,
                    "type": entry.type,
                    "title": entry.title,
                    "body": body,
                    "actor": entry.actor,
                }
            )
        profile = vendor.model_dump(mode="json", exclude={"log", "draft"})
        return {
            "vendor_profile": profile,
            "recent_vendor_log": recent,
            "current_draft": vendor.draft.model_dump(mode="json") if vendor.draft else None,
        }

    # -- mutations -----------------------------------------------------------

    def add_vendor(self, event_id: str, fields: dict[str, Any]) -> VendorRecord:
        vendors = self.list_vendors(event_id)
        now = utc_now()
        vendor = VendorRecord(
            id=f"vendor_{uuid.uuid4().hex[:10]}",
            created_at=now,
            updated_at=now,
            **fields,
        )
        vendor.log.append(
            self._entry(
                vendor.id,
                "status_updated",
                title=f"Vendor added to notebook ({vendor.category})",
                actor="user",
                workflow_status=vendor.workflow_status,
            )
        )
        vendors.append(vendor)
        self._save(event_id, vendors)
        self._store.append_timeline(
            event_id, "vendor_added", {"vendor_id": vendor.id, "name": vendor.name}
        )
        return vendor

    def update_vendor(self, event_id: str, vendor_id: str, updates: dict[str, Any]) -> VendorRecord:
        """Apply a partial update; log meaningful status/payment changes."""
        vendors = self.list_vendors(event_id)
        vendor = self._find(vendors, vendor_id)
        now = utc_now()

        changed = {
            key: value
            for key, value in updates.items()
            if value is not None and getattr(vendor, key) != value
        }
        for key, value in changed.items():
            setattr(vendor, key, value)

        if "workflow_status" in changed:
            if vendor.workflow_status == "settled" and not vendor.settled_at:
                vendor.settled_at = now
                vendor.log.append(
                    self._entry(
                        vendor.id,
                        "settled",
                        title="Vendor marked settled",
                        workflow_status=vendor.workflow_status,
                        payment_status=vendor.payment_status,
                    )
                )
            else:
                vendor.log.append(
                    self._entry(
                        vendor.id,
                        "status_updated",
                        title=f"Workflow status set to {vendor.workflow_status.replace('_', ' ')}",
                        workflow_status=vendor.workflow_status,
                    )
                )
        payment_changes = [key for key in changed if key in _PAYMENT_FIELDS]
        if payment_changes:
            if changed.get("payment_status") == "deposit_paid" and not vendor.deposit_paid_at:
                vendor.deposit_paid_at = now
            vendor.log.append(
                self._entry(
                    vendor.id,
                    "payment_updated",
                    title="Payment details updated ("
                    + ", ".join(key.replace("_", " ") for key in payment_changes)
                    + ")",
                    payment_status=vendor.payment_status,
                )
            )

        if changed:
            vendor.updated_at = now
            self._save(event_id, vendors)
        return vendor

    def delete_vendor(self, event_id: str, vendor_id: str) -> None:
        vendors = self.list_vendors(event_id)
        vendor = self._find(vendors, vendor_id)
        vendors.remove(vendor)
        self._save(event_id, vendors)
        self._store.append_timeline(
            event_id, "vendor_removed", {"vendor_id": vendor_id, "name": vendor.name}
        )

    def append_log(
        self,
        event_id: str,
        vendor_id: str,
        *,
        type: VendorLogEntryType,
        title: str,
        body: str = "",
        actor: Literal["user", "agent", "system"] = "user",
    ) -> VendorLogEntry:
        """Append a log entry. Vendor-supplied text is injection-screened."""
        vendors = self.list_vendors(event_id)
        vendor = self._find(vendors, vendor_id)
        entry = self._entry(vendor_id, type, title=title, body=body, actor=actor)
        if type == "vendor_response_logged":
            # Vendor text is untrusted data; screen it on entry so prompt
            # assembly can withhold flagged bodies later.
            entry.injection_flags = check_injection(body)
        vendor.log.append(entry)
        vendor.updated_at = entry.timestamp
        self._save(event_id, vendors)
        return entry

    def save_draft(
        self,
        event_id: str,
        vendor_id: str,
        draft: VendorDraftRecord,
        *,
        generated: bool = False,
        actor: Literal["user", "agent", "system"] = "user",
    ) -> VendorRecord:
        """Set the vendor's current draft (user edit or agent generation)."""
        vendors = self.list_vendors(event_id)
        vendor = self._find(vendors, vendor_id)
        now = utc_now()
        draft.updated_at = now
        follow_up = generated and vendor.draft is not None and (
            vendor.draft.copy_status == "manually_sent"
        )
        vendor.draft = draft
        entry_type: VendorLogEntryType
        if generated:
            entry_type = "follow_up_generated" if follow_up else "draft_generated"
            title = f"{'Follow-up' if follow_up else 'Draft'} generated: {draft.subject or '(no subject)'}"
        else:
            entry_type = "draft_edited"
            title = f"Draft edited: {draft.subject or '(no subject)'}"
        vendor.log.append(self._entry(vendor_id, entry_type, title=title, actor=actor))
        vendor.workflow_status = _advance(vendor.workflow_status, "draft_ready")
        vendor.updated_at = now
        self._save(event_id, vendors)
        return vendor

    def mark_draft_copied(self, event_id: str, vendor_id: str) -> VendorRecord:
        vendors = self.list_vendors(event_id)
        vendor = self._find(vendors, vendor_id)
        if vendor.draft is None:
            raise VendorNotFoundError(f"{vendor_id} has no draft to mark copied")
        now = utc_now()
        vendor.draft.copied_at = now
        if vendor.draft.copy_status == "not_copied":
            vendor.draft.copy_status = "copied"
        vendor.log.append(
            self._entry(vendor_id, "draft_copied", title="Draft copied for manual send")
        )
        vendor.workflow_status = _advance(vendor.workflow_status, "copied_for_manual_send")
        vendor.updated_at = now
        self._save(event_id, vendors)
        return vendor

    def mark_draft_manually_sent(self, event_id: str, vendor_id: str) -> VendorRecord:
        """Record that the user sent the draft outside the app. Sends nothing."""
        vendors = self.list_vendors(event_id)
        vendor = self._find(vendors, vendor_id)
        if vendor.draft is None:
            raise VendorNotFoundError(f"{vendor_id} has no draft to mark sent")
        now = utc_now()
        vendor.draft.manually_sent_at = now
        vendor.draft.copy_status = "manually_sent"
        vendor.log.append(
            self._entry(
                vendor_id,
                "manual_send_marked",
                title="Marked manually sent outside the app",
            )
        )
        vendor.workflow_status = _advance(vendor.workflow_status, "awaiting_reply")
        vendor.updated_at = now
        self._save(event_id, vendors)
        return vendor

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _entry(
        vendor_id: str,
        type: VendorLogEntryType,
        *,
        title: str,
        body: str = "",
        actor: Literal["user", "agent", "system"] = "user",
        workflow_status: VendorWorkflowStatus | None = None,
        payment_status: VendorPaymentStatus | None = None,
    ) -> VendorLogEntry:
        return VendorLogEntry(
            id=f"log_{uuid.uuid4().hex[:10]}",
            vendor_id=vendor_id,
            timestamp=utc_now(),
            type=type,
            title=title,
            body=body,
            actor=actor,
            workflow_status=workflow_status,
            payment_status=payment_status,
        )

    @staticmethod
    def _find(vendors: list[VendorRecord], vendor_id: str) -> VendorRecord:
        for vendor in vendors:
            if vendor.id == vendor_id:
                return vendor
        raise VendorNotFoundError(vendor_id)

    def _save(self, event_id: str, vendors: list[VendorRecord]) -> CasefileArtifact:
        for vendor in vendors:
            if len(vendor.log) > _MAX_LOG_ENTRIES:
                vendor.log = vendor.log[-_MAX_LOG_ENTRIES:]
        payload = {
            "event_id": event_id,
            "updated_at": utc_now(),
            "vendors": [vendor.model_dump(mode="json") for vendor in vendors],
        }
        return self._store.write_artifact(event_id, ARTIFACT_NAME, payload)
