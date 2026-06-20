import React from 'react'

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

const severityColors: Record<RiskFlag['severity'], { bg: string; text: string; badge: string }> = {
  info: { bg: '#eff6ff', text: '#1e40af', badge: '#2563eb' },
  warning: { bg: '#fffbeb', text: '#92400e', badge: '#d97706' },
  critical: { bg: '#fef2f2', text: '#991b1b', badge: '#dc2626' },
}

export default function RiskCard({ risks }: RiskCardProps) {
  if (!risks || risks.length === 0) {
    return (
      <div style={cardStyle}>
        <h2 style={headingStyle}>Risks</h2>
        <p style={emptyStyle}>No risks identified</p>
      </div>
    )
  }

  const sortedRisks = [...risks].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 }
    return order[a.severity] - order[b.severity]
  })

  return (
    <div style={cardStyle}>
      <h2 style={headingStyle}>Risks</h2>

      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {sortedRisks.map((risk) => {
          const colors = severityColors[risk.severity]

          return (
            <div
              key={risk.id}
              style={{
                ...riskItemStyle,
                backgroundColor: colors.bg,
                borderLeft: `4px solid ${colors.badge}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ ...severityBadgeStyle, backgroundColor: colors.badge }}>
                  {risk.severity}
                </span>
                <span
                  style={{
                    ...badgeStyle,
                    color: risk.resolved ? '#16a34a' : colors.text,
                    backgroundColor: risk.resolved ? '#dcfce7' : 'transparent',
                    border: `1px solid ${risk.resolved ? '#16a34a' : colors.text}`,
                  }}
                >
                  {risk.resolved ? 'resolved' : 'open'}
                </span>
              </div>
              <p style={messageStyle}>{risk.message}</p>
              <div style={metaStyle}>
                Category: {risk.category}
                {risk.related_items && risk.related_items.length > 0 && (
                  <span> &middot; Related: {risk.related_items.join(', ')}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
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

const headingStyle: React.CSSProperties = {
  margin: '0 0 12px 0',
  fontSize: 18,
  fontWeight: 600,
  color: '#111827',
}

const emptyStyle: React.CSSProperties = {
  color: '#6b7280',
  fontSize: 14,
  margin: 0,
}

const riskItemStyle: React.CSSProperties = {
  padding: '10px 12px',
  borderRadius: 6,
  marginBottom: 6,
}

const severityBadgeStyle: React.CSSProperties = {
  display: 'inline-block',
  color: '#ffffff',
  fontSize: 10,
  padding: '2px 8px',
  borderRadius: 4,
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
}

const badgeStyle: React.CSSProperties = {
  display: 'inline-block',
  fontSize: 11,
  padding: '2px 8px',
  borderRadius: 4,
  fontWeight: 600,
}

const messageStyle: React.CSSProperties = {
  margin: '8px 0 4px',
  fontSize: 13,
  color: '#111827',
}

const metaStyle: React.CSSProperties = {
  fontSize: 11,
  color: '#6b7280',
}
