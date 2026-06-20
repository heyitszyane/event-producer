import React from 'react'

export interface BudgetSummary {
  lines: Array<{
    label: string
    qty: string
    unit_cost: string
    currency: string
    category: string
    tier: string
  }>
  category_rollups: Record<string, string>
  tier_rollups: Record<string, string>
  budget_cap: string
  contingency_reserve: string
  spendable: string
  included_totals: string
  headroom: string
  tier_inclusion: Record<string, boolean>
  over_budget: boolean
  under_budget: boolean
  variance?: {
    receipt_vs_plan: Record<string, string>
    running_burn: string
    projected_total: string
    projected_over_under: string
    burn_rate: string
  }
}

interface BudgetCardProps {
  budget: BudgetSummary
}

function formatAmount(value: string | undefined): string {
  if (value === undefined || value === null) return '0.00'
  return value
}

export default function BudgetCard({ budget }: BudgetCardProps) {
  if (!budget) {
    return (
      <div style={cardStyle}>
        <h2 style={headingStyle}>Budget</h2>
        <p style={emptyStyle}>No budget data</p>
      </div>
    )
  }

  const statusColor = budget.over_budget
    ? '#dc2626'
    : budget.under_budget
      ? '#16a34a'
      : '#374151'

  const statusBg = budget.over_budget
    ? '#fef2f2'
    : budget.under_budget
      ? '#f0fdf4'
      : '#f9fafb'

  return (
    <div style={cardStyle}>
      <h2 style={headingStyle}>Budget</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <div>
          <span style={labelStyle}>Budget Cap</span>
          <div style={valueStyle}>{formatAmount(budget.budget_cap)}</div>
        </div>
        <div>
          <span style={labelStyle}>Spendable</span>
          <div style={valueStyle}>{formatAmount(budget.spendable)}</div>
        </div>
        <div>
          <span style={labelStyle}>Contingency Reserve</span>
          <div style={valueStyle}>{formatAmount(budget.contingency_reserve)}</div>
        </div>
        <div>
          <span style={labelStyle}>Headroom</span>
          <div style={{ ...valueStyle, color: budget.headroom?.startsWith?.('-') ? '#dc2626' : '#16a34a' }}>
            {formatAmount(budget.headroom)}
          </div>
        </div>
      </div>

      <div
        style={{
          ...statusStyle,
          backgroundColor: statusBg,
          color: statusColor,
        }}
      >
        {budget.over_budget
          ? 'OVER BUDGET'
          : budget.under_budget
            ? 'UNDER BUDGET'
            : 'ON TARGET'}
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

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 11,
  color: '#6b7280',
  textTransform: 'uppercase',
  fontWeight: 600,
  marginBottom: 2,
}

const valueStyle: React.CSSProperties = {
  fontSize: 18,
  fontWeight: 700,
  color: '#111827',
}

const statusStyle: React.CSSProperties = {
  padding: '8px 12px',
  borderRadius: 6,
  textAlign: 'center',
  fontWeight: 700,
  fontSize: 13,
  letterSpacing: 0.5,
}
