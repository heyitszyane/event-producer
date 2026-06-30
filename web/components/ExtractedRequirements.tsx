import type { BriefIntake, BriefIntakeSourceMap, RequirementSource } from '../types/agentic'
import { MODE_LABEL, MODE_CLASS } from '../types/agentic'

interface Props {
  intake: BriefIntake | null
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="chip">{children}</span>
}

function ListOrMissing({ items, empty }: { items?: string[]; empty: string }) {
  if (!items || items.length === 0) {
    return <span className="muted">{empty}</span>
  }
  return (
    <ul className="bullets">
      {items.map((it) => (
        <li key={it}>{it}</li>
      ))}
    </ul>
  )
}

function SourceBadge({ source }: { source?: RequirementSource }) {
  if (!source || source === 'brief_extracted') return null
  const labels: Record<Exclude<RequirementSource, 'brief_extracted'>, string> = {
    manual_override: 'Manual override',
    fallback_default: 'Fallback default',
    missing: 'Missing',
  }
  const classes: Record<Exclude<RequirementSource, 'brief_extracted'>, string> = {
    manual_override: 'badge--warning',
    fallback_default: 'badge--info',
    missing: 'badge--muted',
  }
  return (
    <span className={`badge ${classes[source as Exclude<RequirementSource, 'brief_extracted'>]}`} style={{ marginLeft: 'var(--space-1)', fontSize: 'var(--text-xs)' }}>
      {labels[source as Exclude<RequirementSource, 'brief_extracted'>]}
    </span>
  )
}

function field(label: string, value: string | number | null | undefined, source?: RequirementSource) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="kv">
      <span className="kv__label">{label}</span>
      <span className="kv__value">
        {String(value)}
        <SourceBadge source={source} />
      </span>
    </div>
  )
}

export default function ExtractedRequirements({ intake }: Props) {
  if (!intake) {
    return (
      <section
        className="card"
        id="extracted"
        aria-labelledby="extracted-heading"
      >
        <div className="card__header">
          <h2 id="extracted-heading">Extracted requirements</h2>
        </div>
        <div className="empty-state">
          Run an event to see the brief interpreted here.
        </div>
      </section>
    )
  }

  const mode = intake.model_mode
  const warnings = intake.market_realism_warnings ?? []
  const missing = intake.missing_questions ?? []
  const contradictions = intake.contradictions ?? []

  return (
    <section
      className="card"
      id="extracted"
      aria-labelledby="extracted-heading"
    >
      <div className="card__header">
        <h2 id="extracted-heading">Extracted requirements</h2>
        <div className="card__header-badges">
          {mode && (
            <span className={`badge ${MODE_CLASS[mode] ?? 'badge--muted'}`}>
              {MODE_LABEL[mode]}
            </span>
          )}
          {intake.confidence && (
            <span className="badge badge--info">
              confidence: {intake.confidence}
            </span>
          )}
        </div>
      </div>

      {/* P7D: field provenance — show where each value came from */}
      <div className="kvs">
        {field('Event type', intake.event_type, intake.source_map?.event_type)}
        {field('Attendees', intake.attendees, intake.source_map?.attendees)}
        {field('Budget cap', intake.budget_cap, intake.source_map?.budget_cap)}
        {field('Venue type', intake.venue_type, intake.source_map?.venue_type)}
        {field('Date', intake.date, intake.source_map?.date)}
        {field('Location', intake.location, intake.source_map?.location)}
        {field('Tone', intake.tone)}
        {field('Audience', intake.audience_profile)}
      </div>

      {intake.goals && intake.goals.length > 0 && (
        <div className="block">
          <h3 className="block__title">Goals</h3>
          <div className="chips">
            {intake.goals.map((g) => (
              <Chip key={g}>{g}</Chip>
            ))}
          </div>
        </div>
      )}

      <div className="grid-2">
        <div className="block">
          <h3 className="block__title">Must-haves</h3>
          <ListOrMissing items={intake.must_haves} empty="None specified" />
        </div>
        <div className="block">
          <h3 className="block__title">Nice-to-haves</h3>
          <ListOrMissing items={intake.nice_to_haves} empty="None specified" />
        </div>
      </div>

      <div className="grid-2">
        <div className="block">
          <h3 className="block__title">Assumptions</h3>
          <ListOrMissing items={intake.assumptions} empty="No assumptions" />
        </div>
        <div className="block">
          <h3 className="block__title">Constraints</h3>
          <ListOrMissing items={intake.constraints} empty="None detected" />
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="block block--warn">
          <h3 className="block__title">Market realism warnings</h3>
          <ul className="bullets">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {contradictions.length > 0 && (
        <div className="block block--warn">
          <h3 className="block__title">Contradictions</h3>
          <ul className="bullets">
            {contradictions.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {missing.length > 0 && (
        <div className="block block--info">
          <h3 className="block__title">Missing / follow-up questions</h3>
          <ul className="bullets">
            {missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
