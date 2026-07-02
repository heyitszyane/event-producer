import { useEffect, useMemo, useState } from 'react'
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
  source: RequirementSource | 'user_added'
  status: string
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

export default function ExtractedRequirements({ intake, resolution }: Props) {
  const baseRows = useMemo<ProvenanceRow[]>(() => {
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
        id: `base-${key}`,
        field: key,
        value: readValue(key),
        source: resolution?.[key]?.source ?? intake.source_map?.[key as keyof typeof intake.source_map] ?? 'missing',
        status: resolution?.[key]?.source === 'manual_override' ? 'manual override' : 'backend extracted',
      }))
      .filter((row) => row.value || row.source === 'missing')
  }, [intake, resolution])

  const [rows, setRows] = useState<ProvenanceRow[]>([])

  useEffect(() => {
    setRows(baseRows)
  }, [baseRows])

  function updateRow(id: string, patch: Partial<ProvenanceRow>) {
    setRows((prev) => prev.map((row) => row.id === id ? {
      ...row,
      ...patch,
      source: row.source === 'user_added' ? 'user_added' : 'manual_override',
      status: patch.status ?? (row.source === 'user_added' ? 'user added' : 'edited manual override'),
    } : row))
  }

  function addRow() {
    setRows((prev) => [
      ...prev,
      {
        id: `added-${Date.now()}`,
        field: 'assumptions',
        value: '',
        source: 'user_added',
        status: 'user added draft',
      },
    ])
  }

  if (!intake) {
    return (
      <section
        className="card"
        id="extracted"
        aria-labelledby="extracted-heading"
      >
        <div className="card__header">
          <h2 id="extracted-heading">Extraction Provenance Preview</h2>
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
        <h2 id="extracted-heading">Extraction Provenance Preview</h2>
        <div className="card__header-badges">
          {mode && (
            <span className={`badge ${MODE_CLASS[mode] ?? 'badge--muted'}`}>
              {MODE_LABEL[mode]}
            </span>
          )}
        </div>
      </div>

      <div className="block block--info">
        Inline edits are session drafts. They become backend inputs only when mapped into manual constraints and the event is re-run or recomputed.
      </div>

      <div className="table-actions">
        <button className="btn btn--primary btn--sm" type="button" onClick={addRow}>
          Add provenance row
        </button>
      </div>

      <table className="data-table provenance-table">
        <thead>
          <tr>
            <th scope="col">Requirement</th>
            <th scope="col">Value</th>
            <th scope="col">Source</th>
            <th scope="col">Notes/Status</th>
            <th scope="col">Remove Row</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td data-label="Requirement">
                <input
                  className="input input--inline"
                  value={humanizeKey(row.field)}
                  onChange={(e) => updateRow(row.id, { field: e.target.value })}
                />
              </td>
              <td data-label="Value">
                <input
                  className="input input--inline"
                  value={row.value}
                  placeholder="Add value"
                  onChange={(e) => updateRow(row.id, { value: e.target.value })}
                />
              </td>
              <td data-label="Source">
                <SourceBadge source={row.source === 'user_added' ? 'manual_override' : row.source} />
              </td>
              <td data-label="Notes/Status">
                <input
                  className="input input--inline"
                  value={row.status}
                  onChange={(e) => updateRow(row.id, { status: e.target.value })}
                />
              </td>
              <td data-label="Remove Row">
                <button className="btn btn--ghost btn--sm" type="button" onClick={() => setRows((prev) => prev.filter((item) => item.id !== row.id))}>
                  Remove
                </button>
              </td>
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
