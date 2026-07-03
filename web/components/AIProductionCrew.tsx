import type { AgentMode, AgentTraceStep, BriefIntake, ModelModeSummary } from '../types/agentic'
import { MODE_CLASS } from '../types/agentic'
import { humanizeSummary } from '../lib/humanize'

interface AIProductionCrewProps {
  trace: AgentTraceStep[]
  modelModeSummary?: ModelModeSummary
  briefIntake?: BriefIntake | null
  budgetSummary?: { headroom?: string; over_budget?: boolean } | null
  scheduleCount?: number
  onPromptChipClick?: (prompt: string) => void
}

const STATUS_LABEL: Record<AgentTraceStep['status'], string> = {
  complete: 'Complete',
  warning: 'Warning',
  blocked: 'Blocked',
  pending_approval: 'Pending approval',
  error: 'Error',
}

function compactModeLabel(mode?: AgentMode): string {
  if (!mode) return 'Pending'
  if (mode === 'gemini_live' || mode === 'openai_compatible_live') return 'Live'
  if (mode === 'rule_based_fallback') return 'Fallback'
  if (mode === 'deterministic_engine') return 'Engine'
  if (mode === 'human_approval_gate') return 'Gated'
  if (mode === 'scripted_fixture') return 'Fixture'
  return 'Off'
}

function taskSummaries(step: AgentTraceStep): string[] {
  const summaries = [step.output_summary, step.input_summary, step.label]
    .filter((value): value is string => Boolean(value && value.trim()))
    .map(humanizeSummary)
    .filter((value) => Boolean(value.trim()))
  if (step.model_mode === 'deterministic_engine') {
    return summaries.slice(0, 1)
  }
  return summaries.slice(0, 2)
}

export default function AIProductionCrew({
  trace,
  briefIntake,
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
      </div>
      <details className="runtime-helper">
        <summary>Runtime legend</summary>
        <p>Live means a model provider answered; fallback is rule-based; engine is deterministic code; gated waits for human approval.</p>
      </details>

      <div className="agent-crew-grid">
        {trace.map((step) => {
          const modeClass = step.model_mode ? MODE_CLASS[step.model_mode] ?? 'badge--muted' : 'badge--muted'
          return (
            <div
              key={step.id}
              className={`agent-crew-card agent-crew-card--${step.status.replace('_', '-')}`}
              aria-label={`${step.role} - ${STATUS_LABEL[step.status] || 'Complete'}`}
            >
              <div className="agent-crew-card__mode-row">
                <span className={`badge ${modeClass}`}>
                  {compactModeLabel(step.model_mode)}
                </span>
              </div>
              <strong className="agent-crew-card__role">{step.role}</strong>
              <ul className="agent-task-summaries">
                {(taskSummaries(step).length ? taskSummaries(step) : ['No recent task recorded yet.']).map((summary) => (
                  <li key={summary}>{summary}</li>
                ))}
              </ul>
              {step.fallback_reason && (
                <div className="block block--warn agent-crew-card__fallback">
                  Fallback: {step.fallback_reason}
                </div>
              )}
              {step.status === 'warning' && briefIntake?.market_realism_warnings?.length ? (
                <p className="agent-crew-card__warning">
                  <strong>Warning:</strong> {briefIntake.market_realism_warnings[0]}
                </p>
              ) : null}
              {(step.model_name || step.prompt_version) && (
                <details className="agent-crew-card__technical">
                  <summary>Technical detail</summary>
                  {step.model_name && <p>Model: {step.model_name}</p>}
                  {step.prompt_version && <p>Prompt: {step.prompt_version}</p>}
                </details>
              )}
              {step.approval_required && (
                <span className="badge badge--warn agent-crew-card__approval">
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
