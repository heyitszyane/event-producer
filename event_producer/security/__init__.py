"""Security package — action-gate, injection detection, and audit logging."""

from event_producer.security.action_gate import enforce, requires_approval
from event_producer.security.audit_log import AuditLog, AuditEntry, log, get_entries
from event_producer.security.injection_flag import check, is_flagged

__all__ = [
    "enforce",
    "requires_approval",
    "check",
    "is_flagged",
    "AuditLog",
    "AuditEntry",
    "log",
    "get_entries",
]
