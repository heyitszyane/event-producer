import type { BriefIntake, ConstraintResolution, ConstraintResolutionField, RequirementSource } from '../types/agentic'
import { MODE_LABEL, MODE_CLASS } from '../types/agentic'

interface Props {
  intake: BriefIntake | null
  resolution?: ConstraintResolution
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
  if (!source) return null
  const labels: Record<RequirementSource, string> = {
    brief_extracted: 'from brief',
    manual_override: 'Manual override',
    fallback_default: 'Fallback default',
    missing: 'Missing / needs follow-up',
  }
  const classes: Record<RequirementSource, string> = {
    brief_extracted: 'badge--ok',
    manual_override: 'badge--warn',
    fallback_default: 'badge--info',
    missing: 'badge--muted',
  }
  return (
    <span className={`badge ${classes[source]}`} style={{ marginLeft: 'var(--space-1)', fontSize: 'var(--text-xs)' }}>
      {labels[source]}
    </span>
  )
}

function field(label: string, value: string | number | null | undefined, source?: RequirementSource, resolved?: ConstraintResolutionField) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="kv">
      <span className="kv__label">{label}</span>
      <span className="kv__value">
        {String(value)}
        <SourceBadge source={source} />
        {source === 'manual_override' && resolved?.brief_value !== null && resolved?.brief_value !== undefined && (
          <span className="muted" style={{ display: 'block', marginTop: '2px', fontSize: 'var(--text-xs)' }}>
            Brief said: {String(resolved.brief_value)}
          </span>
        )}
      </span>
    </div>
  )
}

function resolvedValue(
  resolution: ConstraintResolution | undefined,
  key: string,
  fallback: string | number | null | undefined,
) {
  return resolution?.[key]?.resolved_value ?? fallback
}

function resolvedSource(
  resolution: ConstraintResolution | undefined,
  key: string,
  fallback?: RequirementSource,
) {
  return resolution?.[key]?.source ?? fallback
}

export default function ExtractedRequirements({ intake, resolution }: Props) {
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
        {field('Event type', resolvedValue(resolution, 'event_type', intake.event_type), resolvedSource(resolution, 'event_type', intake.source_map?.event_type), resolution?.event_type)}
        {field('Attendee basis', resolvedValue(resolution, 'attendees', intake.attendees), resolvedSource(resolution, 'attendees', intake.source_map?.attendees), resolution?.attendees)}
        {field('Budget cap', resolvedValue(resolution, 'budget_cap', intake.budget_cap), resolvedSource(resolution, 'budget_cap', intake.source_map?.budget_cap), resolution?.budget_cap)}
        {field('Contingency', resolvedValue(resolution, 'contingency_pct', intake.contingency_pct), resolvedSource(resolution, 'contingency_pct', intake.source_map?.contingency_pct), resolution?.contingency_pct)}
        {field('Venue type', resolvedValue(resolution, 'venue_type', intake.venue_type), resolvedSource(resolution, 'venue_type', intake.source_map?.venue_type), resolution?.venue_type)}
        {field('Date', resolvedValue(resolution, 'date', intake.date), resolvedSource(resolution, 'date', intake.source_map?.date), resolution?.date)}
        {field('Location', resolvedValue(resolution, 'location', intake.location), resolvedSource(resolution, 'location', intake.source_map?.location), resolution?.location)}
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
