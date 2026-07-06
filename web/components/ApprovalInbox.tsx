import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { displayLabel } from '../lib/humanize'
import InfoHint from './InfoHint'

export interface Approval {
  id: string
  action: string
  requested_by: string
  status: string
  approved_by?: string
  timestamp?: string
  notes?: string
}

// The vendor-facing draft that a pending "send_vendor_message" approval gates.
// Rendered read-only so the human actually reviews the copy before approving.
export interface ApprovalVendorDraft {
  subject?: string
  body?: string
  draft?: string
}

interface ApprovalInboxProps {
  approvals: Approval[]
  eventId?: string
  defaultExpanded?: boolean
  vendorDraft?: ApprovalVendorDraft | null
}

function isVendorMessageAction(action: string): boolean {
  return /send_vendor_message|vendor/i.test(action)
}

export default function ApprovalInbox({ approvals, eventId, defaultExpanded = false, vendorDraft = null }: ApprovalInboxProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const [acting, setActing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<{ id: string; action: 'approve' | 'reject' } | null>(null)
  const [localApprovals, setLocalApprovals] = useState<Approval[]>(approvals)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  useEffect(() => {
    setLocalApprovals(approvals)
  }, [approvals])

  const pendingCount = localApprovals.filter((a) => a.status === 'pending').length

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    setActing(id)
    setError(null)
    setStatusMessage(null)
    setConfirming(null)
    try {
      const path = eventId ? `/event/${eventId}/approvals/${id}` : `/approvals/${id}`
      const res = await apiFetch(path, {
        method: 'POST',
        body: JSON.stringify({ action }),
      })
      const updated: Approval = await res.json()
      setLocalApprovals((prev) =>
        prev.map((a) => (a.id === id ? updated : a))
      )
      setStatusMessage(`${displayLabel(updated.action)} ${updated.status}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setActing(null)
    }
  }

  return (
    <section className="card card--security" id="approvals" aria-labelledby="approvals-heading">
      <div className="card__header">
        <h2 id="approvals-heading">
          <span aria-hidden="true">🔒</span> Approvals{' '}
          <InfoHint text="The structural action gate: vendor-facing and financial actions stop here until a human approves or rejects them. Enforced in code, not in prompts." />
        </h2>
        {pendingCount > 0 && (
          <span className="badge badge--warn">{pendingCount} pending</span>
        )}
      </div>

      {/* Structural action gate banner */}
      <div className="security-gate-banner">
        <span className="security-gate-banner__icon" aria-hidden="true">🛡</span>
        <span className="security-gate-banner__text">
          Structural Action Gate — Vendor-facing actions require human approval
        </span>
      </div>

      <p className="body-copy approval-lead">
        This is the human-in-the-loop gate. Anything that would reach a vendor,
        move money, or change saved state is held here until you approve or reject
        it — the app never sends or spends on its own. Each run queues its vendor
        draft here for your sign-off before external use.
      </p>

      {/* Collapsed: count line */}
      {!expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="approval-expand-btn"
          aria-expanded={expanded}
        >
          {pendingCount > 0
            ? `${pendingCount} pending approval${pendingCount !== 1 ? 's' : ''}`
            : localApprovals.length > 0
              ? `${localApprovals.length} processed`
              : 'No approvals'}{' '}
          &middot; Expand
        </button>
      )}

      {/* Expanded: full list */}
      {expanded && (
        <>
          <button
            onClick={() => setExpanded(false)}
            className="approval-collapse-btn"
          >
            Collapse
          </button>

          {error && (
            <div className="error-bar" role="alert">
              <span>{error}</span>
              <button
                onClick={() => setError(null)}
                style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 'var(--text-md)', lineHeight: 1 }}
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}

          <div className="sr-only" aria-live="polite">
            {statusMessage || error || ''}
          </div>

          {localApprovals.length === 0 && (
            <div className="empty-state">
              Nothing waiting for approval. When the crew drafts a vendor message or
              proposes a state change, it appears here for you to approve or reject.
            </div>
          )}

          {localApprovals.map((ap) => (
            <div key={ap.id} className="approval-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                  {displayLabel(ap.action)}
                </span>
                <span className={`badge ${
                  ap.status === 'approved' ? 'badge--ok' :
                  ap.status === 'rejected' ? 'badge--critical' :
                  'badge--warn'
                }`}>
                  {displayLabel(ap.status)}
                </span>
              </div>

              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                Requested by: {ap.requested_by} &middot; Approval ID: {ap.id}
                {ap.approved_by && ap.status !== 'pending' && (
                  <span> &middot; by {ap.approved_by}</span>
                )}
              </div>

              {ap.notes && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)', fontStyle: 'italic' }}>
                  {ap.notes}
                </div>
              )}

              {isVendorMessageAction(ap.action) && vendorDraft && (vendorDraft.subject || vendorDraft.body || vendorDraft.draft) && (
                <div className="approval-draft">
                  <span className="approval-draft__label">Draft held for your review — this is the exact copy that stays unsent until you approve it.</span>
                  {vendorDraft.subject && (
                    <div className="approval-draft__subject"><strong>Subject:</strong> {vendorDraft.subject}</div>
                  )}
                  <pre className="approval-draft__body">{vendorDraft.body || vendorDraft.draft}</pre>
                </div>
              )}

              {ap.status === 'pending' && (
                <div className="approval-gate-reason">
                  <span aria-hidden="true">⛔</span> Vendor-facing action blocked until approved by human
                </div>
              )}

              {ap.status === 'pending' && !confirming && (
                <div className="approval-actions">
                  <button
                    onClick={() => setConfirming({ id: ap.id, action: 'approve' })}
                    disabled={acting === ap.id}
                    className="btn btn--approve btn--sm"
                    aria-label={`Approve: ${displayLabel(ap.action)}`}
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => setConfirming({ id: ap.id, action: 'reject' })}
                    disabled={acting === ap.id}
                    className="btn btn--reject btn--sm"
                    aria-label={`Reject: ${displayLabel(ap.action)}`}
                  >
                    Reject
                  </button>
                </div>
              )}

              {ap.status === 'pending' && confirming && confirming.id === ap.id && (
                <div className="confirm-inline">
                  <span>
                    Confirm {confirming.action}: <strong>{displayLabel(ap.action)}</strong>?
                  </span>
                  <button
                    onClick={() => handleAction(ap.id, confirming.action)}
                    disabled={acting === ap.id}
                    className={`btn btn--${confirming.action === 'approve' ? 'approve' : 'reject'} btn--sm`}
                  >
                    {acting === ap.id ? 'Processing...' : 'Confirm'}
                  </button>
                  <button
                    onClick={() => setConfirming(null)}
                    className="btn btn--sm"
                    style={{ background: 'var(--surface-primary)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </section>
  )
}
