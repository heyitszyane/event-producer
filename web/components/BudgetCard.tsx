import { humanizeKey } from '../lib/humanize'

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
}

function formatCurrency(value: string | undefined | null): string {
  if (value === undefined || value === null) return '$0.00'
  const num = parseFloat(value)
  if (isNaN(num)) return '$0.00'
  const isNegative = num < 0
  const abs = Math.abs(num)
  const formatted = abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return isNegative ? `-$${formatted}` : `$${formatted}`
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
}: {
  label: string
  value: number
  max: number
  overBy?: number
  color?: string
}) {
  const pct = max > 0 ? Math.min(Math.max((value / max) * 100, 0), 100) : 0
  return (
    <div className="budget-health-row">
      <div className="budget-health-row__meta">
        <span>{label}</span>
        <strong>{formatCurrency(String(value))}</strong>
        {overBy && overBy > 0 ? <em>OVER BY {formatCurrency(String(overBy))}</em> : null}
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

export default function BudgetCard({ budget, warnings = [] }: BudgetCardProps) {
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

  return (
    <section className="card" id="budget" aria-labelledby="budget-heading">
      <div className="card__header">
        <h2 id="budget-heading">Budget</h2>
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
          <BudgetHealthRow label="Budget Cap" value={budgetCap} max={budgetCap} />
          <BudgetHealthRow label="Spendable after reserve" value={spendable} max={budgetCap} color="var(--status-info)" />
          <BudgetHealthRow
            label="Included Scope Spend"
            value={selectedSpend}
            max={budgetCap}
            color={selectedSpend > spendable ? 'var(--status-critical)' : 'var(--status-ok)'}
          />
          <BudgetHealthRow
            label="Full Requested Scope"
            value={fullRequested}
            max={budgetCap}
            overBy={requestedOverBy}
            color="var(--status-warn)"
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

        {/* Tier inclusion pills */}
        {Object.keys(budget.tier_inclusion || {}).length > 0 && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Tier Inclusion
            </h3>
            <div className="cluster" style={{ gap: 'var(--space-2)' }}>
              {TIER_ORDER.map((tier) => {
                const included = budget.tier_inclusion[tier]
                const color = TIER_COLORS[tier] || 'var(--text-tertiary)'
                return (
                  <span
                    key={tier}
                    className={`tier-pill ${included ? 'tier-pill--included' : ''}`}
                    style={{
                      color: included ? color : 'var(--text-tertiary)',
                      borderColor: included ? color : 'var(--border-subtle)',
                      background: included ? color.replace(')', ' 0.12)').replace('rgb', 'rgba').replace('#', '') : 'transparent',
                    }}
                  >
                    {TIER_LABELS[tier]}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Variance section (collapsible) */}
        {budget.variance && (
          <details style={{ marginTop: 'var(--space-3)' }}>
            <summary style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              Variance Details
            </summary>
            <div style={{ marginTop: 'var(--space-2)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)' }}>
              <div>
                <span className="metric__label">Running Burn</span>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {formatCurrency(budget.variance.running_burn)}
                </div>
              </div>
              <div>
                <span className="metric__label">Projected Over/Under</span>
                <div style={{
                  fontSize: 'var(--text-md)',
                  fontWeight: 700,
                  color: parseFloat(budget.variance.projected_over_under || '0') < 0 ? 'var(--status-critical)' : 'var(--status-ok)'
                }}>
                  {formatCurrency(budget.variance.projected_over_under)}
                </div>
              </div>
              <div>
                <span className="metric__label">Projected Total</span>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {formatCurrency(budget.variance.projected_total)}
                </div>
              </div>
              <div>
                <span className="metric__label">Burn Rate</span>
                <div style={{ fontSize: 'var(--text-md)', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {formatPercent(budget.variance.burn_rate)}
                </div>
              </div>
            </div>
          </details>
        )}
      </div>
    </section>
  )
}
