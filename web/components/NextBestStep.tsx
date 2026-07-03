import type { NextBestStep as NextBestStepData, NextStepAction } from '../types/agentic'

interface NextBestStepProps {
  nextStep?: NextBestStepData | null
  onNavigate: (target: string) => void
}

function actionButtonClass(action: NextStepAction): string {
  return action.kind === 'primary' ? 'btn btn--primary' : 'btn btn--ghost'
}

export default function NextBestStep({ nextStep, onNavigate }: NextBestStepProps) {
  if (!nextStep) {
    return (
      <section className="war-panel next-step-panel">
        <div className="war-panel__header">
          <div>
            <span className="war-eyebrow">Next best step</span>
            <h2>Start with event basics</h2>
          </div>
          <span className="badge badge--muted">Awaiting casefile</span>
        </div>
        <p className="body-copy">Create or open a casefile to see the next action.</p>
      </section>
    )
  }

  const actions = [nextStep.primary, ...(nextStep.secondary || []).slice(0, 2)]

  return (
    <section className="war-panel next-step-panel">
      <div className="war-panel__header">
        <div>
          <span className="war-eyebrow">Next best step</span>
          <h2>{nextStep.primary.label}</h2>
        </div>
        <span className="badge badge--info">{nextStep.state.replace(/_/g, ' ')}</span>
      </div>
      {nextStep.rationale && <p className="body-copy">{nextStep.rationale}</p>}
      <div className="next-step-actions">
        {actions.map((action) => (
          <button
            key={action.id}
            type="button"
            className={actionButtonClass(action)}
            disabled={action.disabled}
            onClick={() => onNavigate(action.target)}
            title={action.reason || action.label}
          >
            {action.label}
          </button>
        ))}
      </div>
      {nextStep.primary.reason && <p className="small next-step-reason">{nextStep.primary.reason}</p>}
    </section>
  )
}
