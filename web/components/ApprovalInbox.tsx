import { useState } from 'react'

export interface Approval {
  id: string
  action: string
  requested_by: string
  status: string
  approved_by?: string
  timestamp?: string
  notes?: string
}

interface ApprovalInboxProps {
  approvals: Approval[]
  defaultExpanded?: boolean
}

export default function ApprovalInbox({ approvals, defaultExpanded = false }: ApprovalInboxProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const [acting, setActing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<{ id: string; action: 'approve' | 'reject' } | null>(null)
  const [localApprovals, setLocalApprovals] = useState<Approval[]>(approvals)

  // Sync when props change (new run)
  if (approvals !== localApprovals && approvals.length > 0) {
    setLocalApprovals(approvals)
  }

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'
  const pendingCount = localApprovals.filter((a) => a.status === 'pending').length

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    setActing(id)
    setError(null)
    setConfirming(null)
    try {
      const res = await fetch(`${API_BASE}/approvals/${id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Demo-User': 'demo-user',
        },
        body: JSON.stringify({ action }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      // Update local state
      setLocalApprovals((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: action === 'approve' ? 'approved' : 'rejected' } : a))
      )
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
          🔒 Approvals
        </h2>
        {pendingCount > 0 && (
          <span className="badge badge--warn">{pendingCount} pending</span>
        )}
      </div>

      {/* Structural action gate banner */}
      <div className="security-gate-banner">
        <span className="security-gate-banner__icon">🛡</span>
        <span className="security-gate-banner__text">
          Structural Action Gate — Vendor-facing actions require human approval
        </span>
      </div>

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
            <div className="error-bar">
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

          {localApprovals.length === 0 && (
            <div className="empty-state">No approvals.</div>
          )}

          {localApprovals.map((ap) => (
            <div key={ap.id} className="approval-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                  {ap.action}
                </span>
                <span className={`badge ${
                  ap.status === 'approved' ? 'badge--ok' :
                  ap.status === 'rejected' ? 'badge--critical' :
                  'badge--warn'
                }`}>
                  {ap.status}
                </span>
              </div>

              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                Requested by: {ap.requested_by} &middot; ID: {ap.id}
                {ap.approved_by && ap.status !== 'pending' && (
                  <span> &middot; by {ap.approved_by}</span>
                )}
              </div>

              {ap.notes && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)', fontStyle: 'italic' }}>
                  {ap.notes}
                </div>
              )}

              {ap.status === 'pending' && (
                <div className="approval-gate-reason">
                  ⛔ Vendor-facing action blocked until approved by human
                </div>
              )}

              {ap.status === 'pending' && !confirming && (
                <div className="approval-actions">
                  <button
                    onClick={() => setConfirming({ id: ap.id, action: 'approve' })}
                    disabled={acting === ap.id}
                    className="btn btn--approve btn--sm"
                    aria-label={`Approve: ${ap.action}`}
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => setConfirming({ id: ap.id, action: 'reject' })}
                    disabled={acting === ap.id}
                    className="btn btn--reject btn--sm"
                    aria-label={`Reject: ${ap.action}`}
                  >
                    Reject
                  </button>
                </div>
              )}

              {ap.status === 'pending' && confirming && confirming.id === ap.id && (
                <div className="confirm-inline">
                  <span>
                    Confirm {confirming.action}: <strong>{ap.action}</strong>?
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
