"""Audit log — immutable append-only trail for all gated actions.

Every vendor interaction, approval, and security-relevant event is logged.
The log is append-only: entries cannot be modified or deleted once written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AuditEntry:
    """A single immutable audit log entry."""
    timestamp: str
    action: str
    actor: str
    details: str = ""
    approval_id: str = ""
    event_id: str = ""


class AuditLog:
    """Append-only audit log.

    Stores entries in memory. In production, this would be backed by
    Firestore or another persistent store.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def log(
        self,
        action: str,
        actor: str,
        details: str = "",
        approval_id: str = "",
        event_id: str = "",
    ) -> AuditEntry:
        """Append an entry to the audit log.

        Args:
            action: The action being logged.
            actor: Who performed the action.
            details: Optional details.
            approval_id: Optional approval ID.
            event_id: Optional event ID.

        Returns:
            The created AuditEntry.
        """
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            actor=actor,
            details=details,
            approval_id=approval_id,
            event_id=event_id,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        """Return all entries as an immutable tuple."""
        return tuple(self._entries)

    def get_by_action(self, action: str) -> list[AuditEntry]:
        """Get all entries for a specific action."""
        return [e for e in self._entries if e.action == action]

    def get_by_event(self, event_id: str) -> list[AuditEntry]:
        """Get all entries for a specific event."""
        return [e for e in self._entries if e.event_id == event_id]


# Module-level singleton for convenience
_default_log = AuditLog()


def log(
    action: str,
    actor: str,
    details: str = "",
    approval_id: str = "",
    event_id: str = "",
) -> AuditEntry:
    """Log to the default audit log."""
    return _default_log.log(action, actor, details, approval_id, event_id)


def get_entries() -> tuple[AuditEntry, ...]:
    """Return all entries from the default audit log."""
    return _default_log.entries
