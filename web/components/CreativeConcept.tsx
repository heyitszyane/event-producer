import type { CreativeConcept as CreativeConceptData } from '../types/agentic'
import { MODE_LABEL, MODE_CLASS } from '../types/agentic'

interface Props {
  concept: CreativeConceptData | null
}

const TIER_CLASS: Record<string, string> = {
  must: 'chip--must',
  should: 'chip--should',
  could: 'chip--could',
  wow: 'chip--wow',
}

const PRESSURE_CLASS: Record<string, string> = {
  low: 'muted',
  medium: 'text-secondary',
  high: 'text-warn',
}

function IdeaCard({ idea }: { idea: { title: string; description: string; tier: string; estimated_complexity: string; budget_pressure: string; why_it_fits: string } }) {
  return (
    <div className="card card--inset idea-card">
      <div className="idea-card__head">
        <span className="idea-card__title">{idea.title}</span>
        <span className={`chip ${TIER_CLASS[idea.tier] ?? ''}`}>{idea.tier}</span>
      </div>
      <p className="idea-card__desc">{idea.description}</p>
      <div className="idea-card__meta">
        <span>complexity: {idea.estimated_complexity}</span>
        <span>budget pressure: {idea.budget_pressure}</span>
      </div>
      <p className="idea-card__why">{idea.why_it_fits}</p>
    </div>
  )
}

interface SugCardProps {
  s: {
    title: string
    description: string
    category: string
    action_hint: string
    rationale: string
    estimated_cost?: string | null
    tier?: string
  }
  onAddToScope?: (s: { title: string; description: string; category: string; estimated_cost?: string | null; tier?: string }) => void
}

function SugCard({ s, onAddToScope }: SugCardProps) {
  return (
    <div className="card card--inset sug-card">
      <div className="sug-card__head">
        <span className="sug-card__title">{s.title}</span>
        <span className="chip chip--muted">{s.action_hint}</span>
        <span className="chip">{s.category}</span>
      </div>
      <p className="sug-card__desc">{s.description}</p>
      {s.estimated_cost && (
        <p className="sug-card__cost">Estimated: ${s.estimated_cost}</p>
      )}
      <p className="sug-card__why">{s.rationale}</p>
      {onAddToScope && s.action_hint === 'add' && (
        <button
          onClick={() => onAddToScope(s)}
          className="btn btn--primary btn--sm"
          style={{ marginTop: 'var(--space-2)' }}
        >
          Add to scope
        </button>
      )}
    </div>
  )
}

interface CreativeConceptProps extends Props {
  onAddToScope?: (s: { title: string; description: string; category: string; estimated_cost?: string | null; tier?: string }) => void
}

export default function CreativeConcept({ concept, onAddToScope }: CreativeConceptProps) {
  if (!concept) {
    return (
      <section
        className="card"
        id="creative"
        aria-labelledby="creative-heading"
      >
        <div className="card__header">
          <h2 id="creative-heading">Creative concept</h2>
        </div>
        <div className="empty-state">
          Run an event to see the creative direction here.
        </div>
      </section>
    )
  }

  const mode = concept.model_mode
  const titles = concept.event_title_options ?? []
  const ideas = concept.creative_ideas ?? []
  const additions = concept.suggested_additions ?? []
  const cuts = concept.suggested_cuts_or_reductions ?? []

  return (
    <section className="card" id="creative" aria-labelledby="creative-heading">
      <div className="card__header">
        <h2 id="creative-heading">Creative concept</h2>
        <div className="card__header-badges">
          {mode && (
            <span className={`badge ${MODE_CLASS[mode] ?? 'badge--muted'}`}>
              {MODE_LABEL[mode]}
            </span>
          )}
          <span className="badge badge--muted">advisory</span>
        </div>
      </div>

      {titles.length > 0 && (
        <div className="block">
          <h3 className="block__title">Event title options</h3>
          <ul className="bullets">
            {titles.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      {concept.concept_summary && (
        <div className="block">
          <h3 className="block__title">Concept summary</h3>
          <p>{concept.concept_summary}</p>
        </div>
      )}

      {concept.experience_principles && concept.experience_principles.length > 0 && (
        <div className="block">
          <h3 className="block__title">Experience principles</h3>
          <ul className="bullets">
            {concept.experience_principles.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {ideas.length > 0 && (
        <div className="block">
          <h3 className="block__title">Creative ideas</h3>
          <div className="ideas">
            {ideas.map((i) => (
              <IdeaCard key={i.title} idea={i} />
            ))}
          </div>
        </div>
      )}

      {additions.length > 0 && (
        <div className="block">
          <h3 className="block__title">Suggested additions</h3>
          <div className="sugs">
            {additions.map((s) => (
              <SugCard
                key={`add-${s.title}`}
                s={s}
                onAddToScope={onAddToScope}
              />
            ))}
          </div>
        </div>
      )}

      {cuts.length > 0 && (
        <div className="block block--warn">
          <h3 className="block__title">Suggested cuts / reductions</h3>
          <div className="sugs">
            {cuts.map((s) => (
              <SugCard key={`cut-${s.title}`} s={s} />
            ))}
          </div>
        </div>
      )}

      {concept.budget_sensitive_notes && concept.budget_sensitive_notes.length > 0 && (
        <div className="block">
          <h3 className="block__title">Budget-sensitive notes</h3>
          <ul className="bullets">
            {concept.budget_sensitive_notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}

      {concept.production_risks && concept.production_risks.length > 0 && (
        <div className="block">
          <h3 className="block__title">Production risks</h3>
          <ul className="bullets">
            {concept.production_risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {concept.sponsor_or_partner_hooks && concept.sponsor_or_partner_hooks.length > 0 && (
        <div className="block">
          <h3 className="block__title">Sponsor / partner hooks</h3>
          <ul className="bullets">
            {concept.sponsor_or_partner_hooks.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
