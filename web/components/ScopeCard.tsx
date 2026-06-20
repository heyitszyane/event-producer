import React from 'react'

export interface ScopeItem {
  name: string
  description: string
  category: string
  tier: 'must' | 'should' | 'could' | 'wow'
  estimated_cost: string
  currency: string
  qty: string
  selected: boolean
}

interface ScopeCardProps {
  items: ScopeItem[]
}

const tierColors: Record<ScopeItem['tier'], string> = {
  must: '#16a34a',
  should: '#2563eb',
  could: '#ea580c',
  wow: '#9333ea',
}

const tierBgColors: Record<ScopeItem['tier'], string> = {
  must: '#dcfce7',
  should: '#dbeafe',
  could: '#ffedd5',
  wow: '#f3e8ff',
}

export default function ScopeCard({ items }: ScopeCardProps) {
  if (!items || items.length === 0) {
    return (
      <div style={cardStyle}>
        <h2 style={headingStyle}>Scope</h2>
        <p style={emptyStyle}>No scope items</p>
      </div>
    )
  }

  return (
    <div style={cardStyle}>
      <h2 style={headingStyle}>Scope</h2>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>Name</th>
            <th style={thStyle}>Category</th>
            <th style={thStyle}>Tier</th>
            <th style={thStyle}>Qty</th>
            <th style={thStyle}>Cost</th>
            <th style={thStyle}>Selected</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx}>
              <td style={tdStyle}>{item.name}</td>
              <td style={tdStyle}>{item.category}</td>
              <td style={tdStyle}>
                <span
                  style={{
                    ...badgeStyle,
                    backgroundColor: tierBgColors[item.tier],
                    color: tierColors[item.tier],
                  }}
                >
                  {item.tier}
                </span>
              </td>
              <td style={tdStyle}>{String(item.qty)}</td>
              <td style={tdStyle}>
                {item.currency} {String(item.estimated_cost)}
              </td>
              <td style={tdStyle}>{item.selected ? 'Yes' : 'No'}</td>
            </tr>
          ))}
        </tbody>
      </table>
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

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: 13,
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 6px',
  borderBottom: '2px solid #e5e7eb',
  color: '#374151',
  fontWeight: 600,
}

const tdStyle: React.CSSProperties = {
  padding: '8px 6px',
  borderBottom: '1px solid #f3f4f6',
  color: '#374151',
}

const badgeStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: 12,
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
}
