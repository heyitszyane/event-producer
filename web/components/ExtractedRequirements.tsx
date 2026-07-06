import { useMemo } from 'react'
import type { BriefIntake, ConstraintResolution, RequirementSource } from '../types/agentic'
import { MODE_LABEL, MODE_CLASS } from '../types/agentic'
import { humanizeKey } from '../lib/humanize'

interface Props {
  intake: BriefIntake | null
  resolution?: ConstraintResolution
}

interface ProvenanceRow {
  id: string
  field: string
  value: string
  source: RequirementSource
}

const KNOWN_FIELDS = [
  'event_type',
  'attendees',
  'budget_cap',
  'contingency_pct',
  'date',
  'location',
  'venue_type',
  'goals',
  'must_haves',
  'nice_to_haves',
  'constraints',
  'assumptions',
  'missing_questions',
]

function SourceBadge({ source }: { source?: RequirementSource }) {
  if (!source) return null
  const labels: Record<RequirementSource, string> = {
    brief_extracted: 'From brief',
    manual_override: 'You entered',
    fallback_default: 'Planning default',
    missing: 'Missing / needs follow-up',
  }
  const classes: Record<RequirementSource, string> = {
    brief_extracted: 'badge--ok',
    manual_override: 'badge--warn',
    fallback_default: 'badge--info',
    missing: 'badge--muted',
  }
  return (
    <span className={`badge ${classes[source]}`}>
      {labels[source]}
    </span>
  )
}

export default function ExtractedRequirements({ intake, resolution }: Props) {
  const rows = useMemo<ProvenanceRow[]>(() => {
    if (!intake) return []
    const readValue = (key: string): string => {
      const resolved = resolution?.[key]?.resolved_value
      const raw = (intake as unknown as Record<string, unknown>)[key]
      const value = resolved ?? raw
      if (Array.isArray(value)) return value.join('; ')
      return value === null || value === undefined ? '' : String(value)
    }
    return KNOWN_FIELDS
      .map((key) => ({
        id: `row-${key}`,
        field: key,
        value: readValue(key),
        source: (resolution?.[key]?.source ?? intake.source_map?.[key as keyof typeof intake.source_map] ?? 'missing') as RequirementSource,
      }))
      .filter((row) => row.value || row.source === 'missing')
  }, [intake, resolution])

  if (!intake) {
    return (
      <section className="card" id="extracted" aria-labelledby="extracted-heading">
        <div className="card__header">
          <h2 id="extracted-heading">Requirement Provenance</h2>
        </div>
        <div className="empty-state">
          Run an event to see how each planning value was resolved.
        </div>
      </section>
    )
  }

  const mode = intake.model_mode
  const warnings = intake.market_realism_warnings ?? []
  const missing = intake.missing_questions ?? []
  const contradictions = intake.contradictions ?? []

  return (
    <section className="card" id="extracted" aria-labelledby="extracted-heading">
      <div className="card__header">
        <h2 id="extracted-heading">Requirement Provenance</h2>
        <div className="card__header-badges">
          {mode && (
            <span className={`badge ${MODE_CLASS[mode] ?? 'badge--muted'}`}>
              {MODE_LABEL[mode]}
            </span>
          )}
        </div>
      </div>

      <p className="body-copy">
        Where each planning value came from. A value you entered always wins over one
        the intake agent extracted from the brief; blanks fall back to a stated default
        or stay flagged as missing.
      </p>

      <table className="data-table provenance-table">
        <thead>
          <tr>
            <th scope="col">Requirement</th>
            <th scope="col">Value</th>
            <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td data-label="Requirement">{humanizeKey(row.field)}</td>
              <td data-label="Value">{row.value || <span className="muted">—</span>}</td>
              <td data-label="Source"><SourceBadge source={row.source} /></td>
            </tr>
          ))}
        </tbody>
      </table>

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
