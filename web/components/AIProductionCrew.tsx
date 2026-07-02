import type { AgentMode, AgentTraceStep, ModelModeSummary } from '../types/agentic'
import { MODE_LABEL, MODE_CLASS } from '../types/agentic'
import { BriefIntake } from '../types/agentic'
import { humanizeSummary } from '../lib/humanize'

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

function taskSummaries(step: AgentTraceStep): string[] {
  const summaries = [step.output_summary, step.input_summary, step.label]
    .filter((value): value is string => Boolean(value && value.trim()))
    .map(humanizeSummary)
    .filter((value) => Boolean(value.trim()))
  if (step.model_mode === 'deterministic_engine') {
    return summaries.slice(0, 1)
  }
  return summaries.slice(0, 3)
}

export default function AIProductionCrew({
  trace,
  modelModeSummary,
  briefIntake,
  budgetSummary,
  scheduleCount = 0,
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
              Runtime: {MODE_LABEL[modelModeSummary.brief_intake as AgentMode]} Brief Intake
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.creative_concept as AgentMode] ?? 'badge--muted'}`}>
              Runtime: {MODE_LABEL[modelModeSummary.creative_concept as AgentMode]} Creative
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.budget_manager as AgentMode] ?? 'badge--muted'}`}>
              Runtime: {MODE_LABEL[modelModeSummary.budget_manager as AgentMode]} Budget
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.production_manager as AgentMode] ?? 'badge--muted'}`}>
              Runtime: {MODE_LABEL[modelModeSummary.production_manager as AgentMode]} Schedule
            </span>
            <span className={`badge ${MODE_CLASS[modelModeSummary.vendor_coordinator as AgentMode] ?? 'badge--muted'}`}>
              Runtime: {MODE_LABEL[modelModeSummary.vendor_coordinator as AgentMode]} Vendor
            </span>
          </div>
        )}
      </div>
      <p className="runtime-helper">
        Runtime shows whether this output came from a live model provider, rule-based fallback, a deterministic engine, a human approval gate, or a scripted fixture.
      </p>

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
                    Runtime: {MODE_LABEL[step.model_mode]}
                  </span>
                )}
              </div>
              <ul className="agent-task-summaries">
                {(taskSummaries(step).length ? taskSummaries(step) : ['No recent task recorded yet.']).map((summary) => (
                  <li key={summary}>{summary}</li>
                ))}
              </ul>
              {step.status === 'warning' && briefIntake?.market_realism_warnings?.length ? (
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--status-warn)', margin: 0 }}>
                  <strong>Warning:</strong> {briefIntake.market_realism_warnings[0]}
                </p>
              ) : null}
              {step.approval_required && (
                <span className="badge badge--warn" style={{ marginTop: 'var(--space-2)' }}>
                  Approval Required
                </span>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
