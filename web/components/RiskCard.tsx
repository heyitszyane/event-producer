import { useState } from 'react'

export interface RiskFlag {
  id: string
  category: string
  severity: 'info' | 'warning' | 'critical'
  message: string
  related_items: string[]
  resolved: boolean
}

interface RiskCardProps {
  risks: RiskFlag[]
}

const severityBorder: Record<RiskFlag['severity'], string> = {
  info: 'var(--status-info)',
  warning: 'var(--status-warn)',
  critical: 'var(--status-critical)',
}

const severityBg: Record<RiskFlag['severity'], string> = {
  info: 'var(--status-info-bg)',
  warning: 'var(--status-warn-bg)',
  critical: 'var(--status-critical-bg)',
}

const SEVERITY_ORDER: Record<RiskFlag['severity'], number> = {
  critical: 0,
  warning: 1,
  info: 2,
}

export default function RiskCard({ risks }: RiskCardProps) {
  const [showResolved, setShowResolved] = useState(false)

  if (!risks || risks.length === 0) {
    return (
      <section className="card" id="risks" aria-labelledby="risks-heading">
        <div className="card__header">
          <h2 id="risks-heading">Risks & Gaps</h2>
        </div>
        <div className="empty-state">
          No risks identified &mdash; Run the event to generate.
        </div>
      </section>
    )
  }

  const sortedRisks = [...risks].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
  const openRisks = sortedRisks.filter((r) => !r.resolved)
  const resolvedRisks = sortedRisks.filter((r) => r.resolved)

  const criticalCount = openRisks.filter((r) => r.severity === 'critical').length
  const warningCount = openRisks.filter((r) => r.severity === 'warning').length
  const infoCount = openRisks.filter((r) => r.severity === 'info').length

  return (
    <section className="card" id="risks" aria-labelledby="risks-heading">
      <div className="card__header">
        <h2 id="risks-heading">Risks & Gaps</h2>
        <div className="cluster" style={{ gap: 'var(--space-1)' }}>
          {criticalCount > 0 && <span className="badge badge--critical">{criticalCount} critical</span>}
          {warningCount > 0 && <span className="badge badge--warn">{warningCount} warning</span>}
          {infoCount > 0 && <span className="badge badge--info">{infoCount} info</span>}
        </div>
      </div>

      <div style={{ maxHeight: 280, overflowY: 'auto' }}>
        {/* Open risks */}
        {openRisks.map((risk) => (
          <div
            key={risk.id}
            style={{
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: 'var(--space-2)',
              backgroundColor: severityBg[risk.severity],
              borderLeft: `3px solid ${severityBorder[risk.severity]}`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span className={`badge badge--${risk.severity}`}>
                {risk.severity}
              </span>
            </div>
            <p style={{ margin: 'var(--space-1) 0', fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
              {risk.message}
            </p>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
              {risk.category}
              {risk.related_items && risk.related_items.length > 0 && (
                <span> &middot; {risk.related_items.join(', ')}</span>
              )}
            </div>
          </div>
        ))}

        {/* Resolved risks (collapsible) */}
        {resolvedRisks.length > 0 && (
          <>
            <button
              onClick={() => setShowResolved((prev) => !prev)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-tertiary)',
                fontSize: 'var(--text-xs)',
                cursor: 'pointer',
                padding: 0,
                marginTop: 'var(--space-2)',
              }}
              aria-expanded={showResolved}
            >
              {showResolved ? 'Hide' : 'Show'} {resolvedRisks.length} resolved risk{resolvedRisks.length !== 1 ? 's' : ''}
            </button>

            {showResolved && resolvedRisks.map((risk) => (
              <div
                key={risk.id}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 'var(--space-2)',
                  borderLeft: '3px solid var(--border-subtle)',
                }}
              >
                <span className="badge badge--ok">{risk.severity}</span>
                <p style={{
                  margin: 'var(--space-1) 0',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--text-tertiary)',
                  textDecoration: 'line-through',
                }}>
                  {risk.message}
                </p>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                  {risk.category}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </section>
  )
}
