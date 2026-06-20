"""Injection flagging — advisory detection of prompt injection attempts.

This module provides heuristic detection of potential prompt injection
in vendor messages. It is ADVISORY ONLY — it flags content for human
review but never blocks actions by itself. The structural action-gate
is the actual security boundary.
"""

from __future__ import annotations

import re

# Patterns that may indicate injection attempts
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Direct instruction overrides
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "instruction_override"),
    (r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", "instruction_override"),
    (r"forget\s+(everything|all|what)", "instruction_override"),
    # System prompt leaks
    (r"system\s*prompt", "system_prompt"),
    (r"you\s+are\s+now\s+a?\s+", "role_change"),
    # Payment detail changes (subtle injection)
    (r"(new\s+)?(iban|account\s+number|routing\s+number|swift\s+code)\s*(is|has\s+been|updated|changed)", "payment_change"),
    (r"remittance\s+details?\s+(have\s+been\s+)?updated", "payment_change"),
    (r"bank\s+details?\s+(have\s+)?changed", "payment_change"),
    # Urgency / authority pressure
    (r"urgent.*wire\s+transfer", "urgency_pressure"),
    (r"ceo\s+(said|wants|ordered)", "authority_pressure"),
    (r"confidential.*do\s+not\s+share", "secrecy_pressure"),
    # Marked instruction boundaries
    (r"<\s*/\s*instruction\s*>", "boundary_marker"),
    (r"<\s*instruction\s*>", "boundary_marker"),
    # Credential requests
    (r"(send|provide|share)\s+(your|the)\s+(api\s+key|password|token|credential)", "credential_request"),
]


def check(text: str) -> list[str]:
    """Check text for potential injection patterns.

    Args:
        text: The text to check (e.g., vendor message body).

    Returns:
        List of injection flag categories found. Empty list means no flags.
    """
    flags: list[str] = []
    text_lower = text.lower()
    for pattern, category in _INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            if category not in flags:
                flags.append(category)
    return flags


def is_flagged(flags: list[str]) -> bool:
    """Check if any flags indicate a serious injection attempt.

    Args:
        flags: List of injection flag categories.

    Returns:
        True if any serious flags are present.
    """
    serious = {"instruction_override", "role_change", "payment_change", "credential_request"}
    return bool(serious.intersection(flags))
