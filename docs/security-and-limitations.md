# Event Producer Security and Limitations

## Security model

Event Producer uses a human-in-the-loop security model. It intentionally avoids
autonomous external action.

### Structural approval wall

Gated actions require a valid approval object before execution. Examples
include:

- sending a vendor message;
- changing payment details;
- marking a vendor paid;
- changing scope;
- approving budget;
- locking scope;
- releasing funds.

If approval is missing, rejected, pending, or has no approver, the action fails.

### Data-not-instruction boundary

Vendor replies are untrusted data. When a user logs a vendor response:

1. the text is screened for instruction override, payment-change pressure,
   credential requests, urgency pressure, or boundary markers;
2. flags are stored on the log entry;
3. flagged reply text is withheld from later agent prompt context;
4. the agent receives an explicit marker that vendor-supplied text was withheld.

This prevents a vendor reply from becoming agent instruction.

### Draft-only vendor workflow

The Vendor Notebook prepares copy and records manual workflow status. It does
not send email, Telegram, WhatsApp, or payments.

User-facing semantics should remain:

- draft;
- copy;
- mark manually sent;
- log reply;
- review before external use.

Avoid claiming live outbound messaging.

## What is implemented

- Local saved casefiles.
- Structured event facts and conflict notices.
- Agent Mission Control with direct specialist-agent actions.
- Runtime-loaded skill-card registry.
- Deterministic Budget Engine.
- Deterministic Run Sheet Engine.
- Vendor Notebook with per-vendor logs and drafts.
- Injection-screened vendor replies.
- Structural approval wall.
- Optional live provider seam and fallback mode.

## What is not implemented

- Production authentication.
- Multi-user tenancy.
- Production cloud database.
- Live vendor directory lookup.
- Live email / Telegram / WhatsApp sending.
- Autonomous vendor negotiation.
- Payment execution.
- Receipt OCR.
- Live FX feed.
- Calendar writeback.
- Full global location database.

## Why these limits are acceptable

The capstone goal is to demonstrate agentic engineering, not to ship production
vendor operations. The implemented system shows the important architecture
pattern: agents are useful inside a bounded workspace, while deterministic code
and human approval gates protect the operational truth.
