import { useEffect, useState } from 'react'

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

  const fetchApprovals = async () => {
    try {
      const res = await fetch('/api/approvals')
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
    try {
      const res = await fetch(`/api/approvals/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  return (
    <div style={cardStyle}>
      <div style={headerRowStyle}>
        <h2 style={headingStyle}>Approval Inbox</h2>
        <span style={demoBadgeStyle}>DEMO / STUB</span>
      </div>

      {loading && <p style={mutedStyle}>Loading...</p>}

      {error && (
        <div style={errorStyle}>Error: {error}</div>
      )}

      {!loading && !error && approvals.length === 0 && (
        <p style={mutedStyle}>No pending approvals.</p>
      )}

      {approvals.map((ap) => (
        <div key={ap.id} style={itemStyle}>
          <div style={itemHeaderStyle}>
            <span style={actionStyle}>{ap.action}</span>
            <span style={statusBadgeStyle(ap.status)}>{ap.status}</span>
          </div>
          <div style={metaStyle}>
            Requested by: {ap.requested_by} &middot; ID: {ap.id}
          </div>
          {ap.notes && (
            <div style={notesStyle}>Notes: {ap.notes}</div>
          )}
          {ap.status === 'pending' && (
            <div style={buttonRowStyle}>
              <button
                onClick={() => handleAction(ap.id, 'approve')}
                disabled={acting === ap.id}
                style={approveBtnStyle}
              >
                {acting === ap.id ? 'Processing...' : 'Approve'}
              </button>
              <button
                onClick={() => handleAction(ap.id, 'reject')}
                disabled={acting === ap.id}
                style={rejectBtnStyle}
              >
                {acting === ap.id ? 'Processing...' : 'Reject'}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 16,
  marginBottom: 16,
  backgroundColor: '#ffffff',
}

const headerRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 12,
}

const headingStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: '#111827',
}

const demoBadgeStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: 1,
  color: '#92400e',
  backgroundColor: '#fef3c7',
  padding: '2px 8px',
  borderRadius: 4,
  border: '1px solid #fbbf24',
}

const mutedStyle: React.CSSProperties = {
  color: '#6b7280',
  fontSize: 14,
  margin: 0,
}

const errorStyle: React.CSSProperties = {
  color: '#dc2626',
  fontSize: 14,
  marginBottom: 12,
  padding: 8,
  backgroundColor: '#fef2f2',
  borderRadius: 4,
  border: '1px solid #fecaca',
}

const itemStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 6,
  padding: 12,
  marginBottom: 10,
  backgroundColor: '#f9fafb',
}

const itemHeaderStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  marginBottom: 4,
}

const actionStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 14,
  color: '#111827',
}

function statusBadgeStyle(status: string): React.CSSProperties {
  const colors: Record<string, { bg: string; fg: string; border: string }> = {
    pending: { bg: '#fef3c7', fg: '#92400e', border: '#fbbf24' },
    approved: { bg: '#dcfce7', fg: '#166534', border: '#4ade80' },
    rejected: { bg: '#fee2e2', fg: '#991b1b', border: '#f87171' },
  }
  const c = colors[status] || colors.pending
  return {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    backgroundColor: c.bg,
    color: c.fg,
    border: `1px solid ${c.border}`,
  }
}

const metaStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#6b7280',
  marginBottom: 8,
}

const notesStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#374151',
  marginBottom: 8,
  fontStyle: 'italic',
}

const buttonRowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  marginTop: 4,
}

const approveBtnStyle: React.CSSProperties = {
  padding: '6px 16px',
  fontSize: 13,
  fontWeight: 600,
  color: '#ffffff',
  backgroundColor: '#16a34a',
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
}

const rejectBtnStyle: React.CSSProperties = {
  padding: '6px 16px',
  fontSize: 13,
  fontWeight: 600,
  color: '#ffffff',
  backgroundColor: '#dc2626',
  border: 'none',
  borderRadius: 4,
  cursor: 'pointer',
}
