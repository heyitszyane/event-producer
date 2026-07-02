import type { AgentMode, ScopeStrategy as ScopeStrategyData } from '../types/agentic'
import { MODE_CLASS, MODE_LABEL } from '../types/agentic'
import { displayLabel } from '../lib/humanize'

interface ScopeStrategyProps {
  strategy?: ScopeStrategyData | null
}

export default function ScopeStrategy({ strategy }: ScopeStrategyProps) {
  if (!strategy) {
    return (
      <section className="card" id="scope-strategy" aria-labelledby="scope-strategy-heading">
        <div className="card__header">
          <h2 id="scope-strategy-heading">Scope Strategy</h2>
          <span className="badge badge--muted">Awaiting run</span>
        </div>
        <div className="empty-state">Run the event to see scope tradeoffs and recommendation logic.</div>
      </section>
    )
  }

  const mode = strategy.model_mode as AgentMode | undefined
  const recommendations = strategy.recommendations ?? []

  return (
    <section className="card" id="scope-strategy" aria-labelledby="scope-strategy-heading">
      <div className="card__header">
        <h2 id="scope-strategy-heading">Scope Strategy</h2>
        <div className="cluster">
          {mode && <span className={`badge ${MODE_CLASS[mode] ?? 'badge--muted'}`}>{MODE_LABEL[mode]}</span>}
          <span className="badge badge--info">{recommendations.length} recommendation{recommendations.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      {strategy.fallback_reason && (
        <div className="block block--warn">Fallback: {strategy.fallback_reason}</div>
      )}

      <p className="body-copy">{strategy.strategy_summary || 'No strategy summary returned.'}</p>

      {(strategy.tradeoffs ?? []).length > 0 && (
        <div className="war-inset">
          <div className="war-inset__topline">
            <strong>Tradeoffs</strong>
          </div>
          <ul className="bullets">
            {(strategy.tradeoffs ?? []).map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}
          </ul>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="proposal-ledger">
          {recommendations.slice(0, 4).map((rec) => (
            <div key={`${rec.recommendation_type}-${rec.title}`} className="war-inset">
              <div className="war-inset__topline">
                <strong>{rec.title}</strong>
                <div className="cluster">
                  <span className="badge badge--info">{displayLabel(rec.recommendation_type)}</span>
                  <span className="badge badge--muted">{displayLabel(rec.tier)}</span>
                </div>
              </div>
              <p>{rec.rationale}</p>
              <div className="cluster">
                <span className={rec.budget_pressure === 'high' ? 'badge badge--warn' : 'badge badge--muted'}>
                  Budget {rec.budget_pressure}
                </span>
                <span className={rec.operational_risk === 'high' ? 'badge badge--warn' : 'badge badge--muted'}>
                  Ops risk {rec.operational_risk}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
