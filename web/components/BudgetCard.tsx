import { humanizeKey } from '../lib/humanize'
import InfoHint from './InfoHint'

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
  contingency_pct: string
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
  budget: BudgetSummary | null
  warnings?: string[]
  currency?: string
}

function makeFormatCurrency(currency: string) {
  const code = (currency || 'USD').toUpperCase()
  return (value: string | number | undefined | null): string => {
    if (value === undefined || value === null) return `${code} 0.00`
    const num = typeof value === 'number' ? value : parseFloat(value)
    if (isNaN(num)) return `${code} 0.00`
    const isNegative = num < 0
    const abs = Math.abs(num)
    const formatted = abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return isNegative ? `-${code} ${formatted}` : `${code} ${formatted}`
  }
}

function formatPercent(value: string | undefined | null): string {
  if (value === undefined || value === null) return '0.0%'
  const num = parseFloat(value)
  if (isNaN(num)) return '0.0%'
  return `${num.toFixed(1)}%`
}

const TIER_ORDER = ['must', 'should', 'could', 'wow'] as const
const TIER_COLORS: Record<string, string> = {
  must: 'var(--tier-must)',
  should: 'var(--tier-should)',
  could: 'var(--tier-could)',
  wow: 'var(--tier-wow)',
}
const TIER_LABELS: Record<string, string> = {
  must: 'Essential',
  should: 'Recommended',
  could: 'Optional',
  wow: 'Stretch',
}

function numeric(value: string | undefined | null): number {
  const num = parseFloat(String(value ?? '0'))
  return Number.isFinite(num) ? num : 0
}

function BudgetHealthRow({
  label,
  value,
  max,
  overBy,
  color,
  format,
}: {
  label: string
  value: number
  max: number
  overBy?: number
  color?: string
  format: (value: string | number) => string
}) {
  const pct = max > 0 ? Math.min(Math.max((value / max) * 100, 0), 100) : 0
  return (
    <div className="budget-health-row">
      <div className="budget-health-row__meta">
        <span>{label}</span>
        <strong>{format(value)}</strong>
        {overBy && overBy > 0 ? <em>OVER BY {format(overBy)}</em> : null}
      </div>
      <div className="budget-health-row__track">
        <div
          className="budget-health-row__fill"
          style={{ width: `${pct}%`, ...(color ? { background: color } : {}) }}
        />
      </div>
    </div>
  )
}

// Palette used to distinguish category spend bars.
const CATEGORY_BAR_COLORS = [
  'var(--tier-should)',
  'var(--tier-must)',
  'var(--tier-could)',
  'var(--tier-wow)',
  'var(--status-info)',
  'var(--status-warn)',
]

export default function BudgetCard({ budget, warnings = [], currency = 'USD' }: BudgetCardProps) {
  const formatCurrency = makeFormatCurrency(currency)
  if (!budget) {
    return (
      <section className="card" id="budget" aria-labelledby="budget-heading">
        <div className="card__header">
          <h2 id="budget-heading">Budget</h2>
        </div>
        <div className="empty-state">
          No budget data &mdash; Run the event to generate.
        </div>
      </section>
    )
  }

  const headroomNum = parseFloat(budget.headroom || '0')
  const headroomColor = headroomNum < 0 ? 'var(--status-critical)' : 'var(--status-ok)'
  const hasRealismRisk = warnings.length > 0

  const statusBadge = budget.over_budget
    ? { label: 'Over budget', variant: 'badge--critical' as const }
    : hasRealismRisk
      ? { label: 'At risk — full brief likely exceeds cap', variant: 'badge--warn' as const }
    : budget.under_budget
      ? { label: 'On track', variant: 'badge--ok' as const }
      : { label: 'On target', variant: 'badge--info' as const }

  const categories = Object.entries(budget.category_rollups || {})
  const maxCategoryVal = Math.max(...categories.map(([, v]) => parseFloat(v || '0')), 1)
  const budgetCap = numeric(budget.budget_cap)
  const spendable = numeric(budget.spendable)
  const selectedSpend = numeric(budget.included_totals)
  const fullRequested = Math.max(
    selectedSpend,
    budget.lines.reduce((sum, line) => sum + (numeric(line.qty) * numeric(line.unit_cost)), 0)
  )
  const requestedOverBy = Math.max(fullRequested - budgetCap, 0)

  // Per-tier rollup straight from the reconciled lines: how many items sit in
  // each priority tier, what they cost, and whether the engine included them.
  const tierBreakdown = TIER_ORDER.map((tier) => {
    const lines = budget.lines.filter((line) => line.tier === tier)
    const total = lines.reduce((sum, line) => sum + numeric(line.qty) * numeric(line.unit_cost), 0)
    return {
      tier,
      count: lines.length,
      total,
      included: budget.tier_inclusion?.[tier] ?? false,
    }
  }).filter((row) => row.count > 0)

  return (
    <section className="card" id="budget" aria-labelledby="budget-heading">
      <div className="card__header">
        <h2 id="budget-heading">
          Budget{' '}
          <InfoHint text="Deterministic budget engine output: every line reconciles to zero against the cap, with contingency reserved before discretionary spend. The model never computes these numbers." />
        </h2>
        <span className={`badge ${statusBadge.variant}`}>{statusBadge.label}</span>
      </div>

      {/* Three metric blocks */}
      <div className="card__body">
        {warnings.length > 0 && (
          <div className="block block--warn" style={{ marginBottom: 'var(--space-3)' }}>
            <h3 className="block__title">Budget realism risk</h3>
            <ul className="bullets">
              {warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
          <div className="metric">
            <span className="metric__value" aria-label={`Budget cap: ${formatCurrency(budget.budget_cap)}`}>
              {formatCurrency(budget.budget_cap)}
            </span>
            <span className="metric__label">Budget Cap</span>
          </div>
          <div className="metric">
            <span className="metric__value" aria-label={`Spendable: ${formatCurrency(budget.spendable)}`}>
              {formatCurrency(budget.spendable)}
            </span>
            <span className="metric__label">Spendable</span>
          </div>
          <div className="metric">
            <span
              className="metric__value"
              style={{ color: headroomColor }}
              aria-label={`Headroom: ${formatCurrency(budget.headroom)}`}
            >
              {formatCurrency(budget.headroom)}
            </span>
            <span className="metric__label">Headroom</span>
          </div>
        </div>

        <div className="budget-health">
          <BudgetHealthRow label="Budget Cap" value={budgetCap} max={budgetCap} format={formatCurrency} />
          <BudgetHealthRow
            label={`Contingency reserve (${formatPercent(budget.contingency_pct)})`}
            value={numeric(budget.contingency_reserve)}
            max={budgetCap}
            color="var(--status-warn)"
            format={formatCurrency}
          />
          <BudgetHealthRow label="Spendable after reserve" value={spendable} max={budgetCap} color="var(--status-info)" format={formatCurrency} />
          <BudgetHealthRow
            label="Included Scope Spend"
            value={selectedSpend}
            max={budgetCap}
            color={selectedSpend > spendable ? 'var(--status-critical)' : 'var(--status-ok)'}
            format={formatCurrency}
          />
          <BudgetHealthRow
            label="Full Requested Scope"
            value={fullRequested}
            max={budgetCap}
            overBy={requestedOverBy}
            color="var(--status-warn)"
            format={formatCurrency}
          />
        </div>

        {/* Category rollup bars */}
        {categories.length > 0 && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Category Spend
            </h3>
            {categories.map(([cat, val], idx) => {
              const numVal = parseFloat(val || '0')
              const pct = (numVal / maxCategoryVal) * 100
              return (
                <div key={cat} className="rollup-bar">
                  <span className="rollup-bar__label">{humanizeKey(cat)}</span>
                  <div className="rollup-bar__track">
                    <div
                      className="rollup-bar__fill"
                      style={{ width: `${pct}%`, background: CATEGORY_BAR_COLORS[idx % CATEGORY_BAR_COLORS.length] }}
                    />
                  </div>
                  <span className="rollup-bar__value">{formatCurrency(val)}</span>
                </div>
              )
            })}
          </div>
        )}

        {/* Tier breakdown — what each priority tier costs and whether the
            budget engine could fit it into the spendable pool. */}
        {tierBreakdown.length > 0 && (
          <div style={{ marginBottom: 'var(--space-2)' }}>
            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Tier Inclusion
            </h3>
            <table className="data-table budget-tier-table">
              <thead>
                <tr>
                  <th scope="col">Tier</th>
                  <th scope="col">Items</th>
                  <th scope="col">Tier total</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {tierBreakdown.map((row) => (
                  <tr key={row.tier}>
                    <td data-label="Tier">
                      <span className="tier-dot" style={{ background: TIER_COLORS[row.tier] || 'var(--text-tertiary)' }} aria-hidden="true" />
                      {TIER_LABELS[row.tier]}
                    </td>
                    <td data-label="Items">{row.count}</td>
                    <td data-label="Tier total">{formatCurrency(row.total)}</td>
                    <td data-label="Status">
                      <span className={`badge ${row.included ? 'badge--ok' : 'badge--muted'}`}>
                        {row.tier === 'must'
                          ? 'Always included'
                          : row.included
                            ? 'Included'
                            : 'Excluded — over spendable'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
