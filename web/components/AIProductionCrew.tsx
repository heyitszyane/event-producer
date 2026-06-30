import type { AgentMode, AgentTraceStep, ModelModeSummary } from '../types/agentic'
import { MODE_LABEL, MODE_CLASS } from '../types/agentic'
import { BriefIntake } from '../types/agentic'

interface AIProductionCrewProps {
  trace: AgentTraceStep[]
  modelModeSummary?: ModelModeSummary
  briefIntake?: BriefIntake | null
  budgetSummary?: { headroom?: string; over_budget?: boolean } | null
  scheduleCount?: number
  onPromptChipClick?: (prompt: string) => void
}

const STATUS_CONFIG: Record<
  AgentTraceStep['status'],
  { label: string; bg: string; fg: string; border: string }
> = {
  complete: {
    label: 'Complete',
    bg: 'var(--status-ok-bg)',
    fg: 'var(--status-ok)',
    border: 'var(--status-ok)',
  },
  warning: {
    label: 'Warning',
    bg: 'var(--status-warn-bg)',
    fg: 'var(--status-warn)',
    border: 'var(--status-warn)',
  },
  blocked: {
    label: 'Blocked',
    bg: 'var(--status-critical-bg)',
    fg: 'var(--status-critical)',
    border: 'var(--status-critical)',
  },
  pending_approval: {
    label: 'Pending Approval',
    bg: 'var(--status-warn-bg)',
    fg: 'var(--status-warn)',
    border: 'var(--status-warn)',
  },
  error: {
    label: 'Error',
    bg: 'var(--status-critical-bg)',
    fg: 'var(--status-critical)',
    border: 'var(--status-critical)',
  },
}

// P7D prompt chips for quick interaction
const PROMPT_CHIPS = [
  "Make this feel more premium",
  "Suggest cuts to stay under budget",
  "Add low-cost networking mechanics",
  "Flag unrealistic assumptions",
  "Rebalance scope under budget",
  "Suggest vendor/service additions",
  "Make this more brand/photo-ready",
]

export default function AIProductionCrew({
  trace,
  modelModeSummary,
  briefIntake,
  budgetSummary,
  scheduleCount = 0,
  onPromptChipClick,
}: AIProductionCrewProps) {
  if (!trace || trace.length === 0) {
    return (
      <section className="card" id="ai-crew" aria-labelledby="ai-crew-heading">
        <div className="card__header">
          <h2 id="ai-crew-heading">AI Production Crew</h2>
        </div>
        <div className="empty-state">
          Run the event to see the AI production crew in action.
        </div>
      </section>
    )
  }

  return (
    <section className="card" id="ai-crew" aria-labelledby="ai-crew-heading">
      <div className="card__header">
        <h2 id="ai-crew-heading">AI Production Crew</h2>
        {modelModeSummary && (
          <div className="card__header-badges" style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
            <span className={`badge ${MODE_CLASS[modelModeSummary.brief_intake as AgentMode] ?? 'badge--muted'}`}>
              {MODE_LABEL[modelModeSummary.brief_intake as AgentMode]} Brief Intake
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.creative_concept as AgentMode] ?? 'badge--muted'}`}>
              {MODE_LABEL[modelModeSummary.creative_concept as AgentMode]} Creative
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.budget_manager as AgentMode] ?? 'badge--muted'}`}>
              {MODE_LABEL[modelModeSummary.budget_manager as AgentMode]} Budget
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.production_manager as AgentMode] ?? 'badge--muted'}`}>
              {MODE_LABEL[modelModeSummary.production_manager as AgentMode]} Schedule
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.vendor_coordinator as AgentMode] ?? 'badge--muted'}`}>
              {MODE_LABEL[modelModeSummary.vendor_coordinator as AgentMode]} Vendor
            </span>
          </div>
        )}
      </div>

      <div className="agent-crew-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-3)' }}>
        {trace.map((step) => {
          const statusCfg = STATUS_CONFIG[step.status] || STATUS_CONFIG.complete
          return (
            <div
              key={step.id}
              className="agent-crew-card"
              style={{
                border: `1px solid ${statusCfg.border}`,
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-3)',
                background: 'var(--surface-secondary)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-2)' }}>
                <strong style={{ fontSize: 'var(--text-sm)' }}>{step.role}</strong>
                {step.model_mode && (
                  <span className={`badge ${MODE_CLASS[step.model_mode] ?? 'badge--muted'}`} style={{ fontSize: 'var(--text-xs)' }}>
                    {MODE_LABEL[step.model_mode]}
                  </span>
                )}
              </div>
              <p style={{ fontSize: 'var(--text-sm)', margin: '0 0 var(--space-2)', opacity: 0.9 }}>
                {step.label}
              </p>
              {step.output_summary && (
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: 0 }}>
                  {step.output_summary}
                </p>
              )}
              {step.approval_required && (
                <span className="badge badge--warning" style={{ marginTop: 'var(--space-2)' }}>
                  🔒 Approval Required
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* P7D: Prompt chips for quick interaction */}
      {onPromptChipClick && (
        <div className="prompt-chips" style={{ marginTop: 'var(--space-4)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-2)' }}>Quick suggestions:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
            {PROMPT_CHIPS.map((chip) => (
              <button
                key={chip}
                onClick={() => onPromptChipClick(chip)}
                className="btn btn--ghost btn--sm"
                style={{ fontSize: 'var(--text-xs)' }}
                type="button"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}