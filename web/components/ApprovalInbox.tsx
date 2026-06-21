import { useEffect, useState } from 'react'

// In production, set NEXT_PUBLIC_API_BASE_URL to the Cloud Run backend URL.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

interface Approval {
  id: string
  action: string
  requested_by: string
  status: string
  approved_by?: string
  timestamp?: string
  notes?: string
}

export default function ApprovalInbox() {
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [acting, setActing] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [confirming, setConfirming] = useState<{ id: string; action: 'approve' | 'reject' } | null>(null)

  const fetchApprovals = async () => {
    try {
      const res = await fetch(`${API_BASE}/approvals`, {
        headers: { 'X-Demo-User': 'demo-user' },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: Approval[] = await res.json()
      setApprovals(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [])

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
      await fetchApprovals()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setActing(null)
    }
  }

  const pendingCount = approvals.filter((a) => a.status === 'pending').length

  return (
    <section className="card" id="approvals" aria-labelledby="approvals-heading">
      <div className="card__header">
        <h2 id="approvals-heading">Approvals</h2>
        {pendingCount > 0 && (
          <span className="badge badge--warn">{pendingCount} pending</span>
        )}
      </div>

      {/* Collapsed: count line */}
      {!expanded && (
        <button
          onClick={() => setExpanded(true)}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-secondary)',
            fontSize: 'var(--text-sm)',
            cursor: 'pointer',
            padding: 0,
          }}
          aria-expanded={expanded}
        >
          {pendingCount > 0
            ? `${pendingCount} pending approvals`
            : approvals.length > 0
              ? `${approvals.length} processed`
              : 'No Approvals'}{' '}
          &middot; Expand
        </button>
      )}

      {/* Expanded: full list */}
      {expanded && (
        <>
          <button
            onClick={() => setExpanded(false)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-tertiary)',
              fontSize: 'var(--text-xs)',
              cursor: 'pointer',
              padding: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            Collapse
          </button>

          {loading && <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', margin: 0 }}>Loading...</p>}

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

          {!loading && !error && approvals.length === 0 && (
            <div className="empty-state">No approvals.</div>
          )}

          {approvals.map((ap) => (
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
