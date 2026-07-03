import type { AgentMode } from '../types/agentic'

export interface AgentTraceStep {
  id: string
  role: string
  label: string
  status: 'complete' | 'warning' | 'blocked' | 'pending_approval' | 'error'
  input_summary: string
  output_summary: string
  artifacts: string[]
  deterministic_core: string | null
  approval_required: boolean
  // P7A: model-mode telemetry (optional so older payloads still render)
  model_mode?: AgentMode
  model_name?: string | null
  prompt_version?: string | null
  fallback_reason?: string | null
  confidence?: string | null
}

interface AgentCrewTraceProps {
  steps: AgentTraceStep[]
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

export default function AgentCrewTrace({ steps }: AgentCrewTraceProps) {
  if (!steps || steps.length === 0) {
    return (
      <section className="card" id="agent-crew" aria-labelledby="agent-crew-heading">
        <div className="card__header">
          <h2 id="agent-crew-heading">Agent Crew Trace</h2>
        </div>
        <div className="empty-state">
          No agent trace available &mdash; Run the event to generate.
        </div>
      </section>
    )
  }

  return (
    <section className="card" id="agent-crew" aria-labelledby="agent-crew-heading">
      <div className="card__header">
        <h2 id="agent-crew-heading">Agent Crew Trace</h2>
        <span className="badge badge--info">{steps.length} steps</span>
      </div>

      <div className="agent-crew-trace">
        {steps.map((step, idx) => {
          const statusCfg = STATUS_CONFIG[step.status] || STATUS_CONFIG.complete
          const isLast = idx === steps.length - 1

          return (
            <div key={step.id || idx} className="agent-step">
              {/* Timeline connector */}
              <div className="agent-step__timeline">
                <div
                  className="agent-step__dot"
                  style={{
                    backgroundColor: statusCfg.bg,
                    borderColor: statusCfg.border,
                  }}
                />
                {!isLast && <div className="agent-step__line" />}
              </div>

              {/* Step content */}
              <div
                className="agent-step__card"
                style={{ borderLeftColor: statusCfg.border }}
              >
                {/* Header row: role + status */}
                <div className="agent-step__header">
                  <div className="agent-step__role">
                    <span className="agent-step__role-name">{step.role}</span>
                    {step.deterministic_core && (
                      <span className="agent-step__core">
                        ⚙ {step.deterministic_core}
                      </span>
                    )}
                  </div>
                  <span
                    className="badge agent-step__status"
                    style={{
                      backgroundColor: statusCfg.bg,
                      color: statusCfg.fg,
                      borderColor: `color-mix(in srgb, ${statusCfg.fg} 50%, transparent)`,
                    }}
                  >
                    {statusCfg.label}
                  </span>
                </div>

                {/* Label */}
                <div className="agent-step__label">{step.label}</div>

                {/* I/O summaries */}
                <div className="agent-step__summaries">
                  <div className="agent-step__summary">
                    <span className="agent-step__summary-label">In</span>
                    <span className="agent-step__summary-text">{step.input_summary}</span>
                  </div>
                  <div className="agent-step__summary">
                    <span className="agent-step__summary-label">Out</span>
                    <span className="agent-step__summary-text">{step.output_summary}</span>
                  </div>
                </div>

                {/* Artifacts + approval flag */}
                <div className="agent-step__meta">
                  {step.artifacts.length > 0 && (
                    <div className="agent-step__artifacts">
                      {step.artifacts.map((a) => (
                        <span key={a} className="agent-step__artifact">{a}</span>
                      ))}
                    </div>
                  )}
                  {step.approval_required && (
                    <span className="agent-step__approval-badge">
                      🔒 Approval Required
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
