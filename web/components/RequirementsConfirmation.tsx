import { useState, type ChangeEvent } from 'react'
import { confirmCasefileRequirements, updateCasefileBasics } from '../lib/casefiles'
import type { CasefileState, EventBasics, RequirementField } from '../types/agentic'

const EVENT_TYPES = [
  { value: 'corporate', label: 'Corporate' },
  { value: 'networking', label: 'Networking' },
  { value: 'product_launch', label: 'Product Launch' },
  { value: 'conference', label: 'Conference' },
]

const CURRENCIES = ['USD', 'SGD', 'THB', 'MYR', 'IDR', 'GBP', 'EUR', 'AUD']
const COUNTRIES = ['Singapore', 'United States', 'Thailand', 'Malaysia', 'Indonesia', 'United Kingdom', 'Australia']

interface RequirementsConfirmationProps {
  casefile: CasefileState | null
  fallbackBasics: EventBasics
  onCasefileChange: (casefile: CasefileState) => void
  onError: (message: string) => void
}

function displayRequirementValue(field: RequirementField): string {
  if (field.key === 'expected_turnout' && (field.value === null || field.value === undefined || field.value === '')) {
    return 'Expected turnout not set'
  }
  if (field.value === null || field.value === undefined || field.value === '') return 'Not set'
  return String(field.value)
}

function badgeClass(field: RequirementField): string {
  if (field.status === 'missing') return 'badge badge--fallback'
  if (field.status === 'conflict') return 'badge badge--warn'
  return 'badge badge--ok'
}

export default function RequirementsConfirmation({
  casefile,
  fallbackBasics,
  onCasefileChange,
  onError,
}: RequirementsConfirmationProps) {
  const [editing, setEditing] = useState(false)
  const [draftBasics, setDraftBasics] = useState<EventBasics>(casefile?.basics || fallbackBasics)
  const [saving, setSaving] = useState(false)
  const requirements = casefile?.requirements
  const missingCount = requirements?.missing.length || requirements?.fields.filter((field) => field.status === 'missing').length || 0
  const confirmedAt = casefile?.requirements_confirmed_at || requirements?.confirmed_at || null

  function beginEdit() {
    setDraftBasics(casefile?.basics || fallbackBasics)
    setEditing(true)
  }

  function update<K extends keyof EventBasics>(field: K, value: EventBasics[K]) {
    setDraftBasics((prev) => ({ ...prev, [field]: value }))
  }

  async function saveChanges() {
    if (!casefile) return
    setSaving(true)
    try {
      const saved = await updateCasefileBasics(casefile.event_id, {
        ...draftBasics,
        budget_cap: draftBasics.budget_cap === '' ? null : draftBasics.budget_cap,
        expected_turnout: draftBasics.expected_turnout === undefined ? null : draftBasics.expected_turnout,
        end_date: draftBasics.end_date || draftBasics.start_date,
      })
      onCasefileChange(saved)
      setEditing(false)
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function confirmRequirements() {
    if (!casefile) return
    setSaving(true)
    try {
      const confirmed = await confirmCasefileRequirements(casefile.event_id)
      onCasefileChange(confirmed)
      setEditing(false)
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (!casefile || !requirements) {
    return (
      <section className="war-panel requirements-panel">
        <div className="war-panel__header">
          <div>
            <span className="war-eyebrow">Requirements</span>
            <h2>Confirm requirements</h2>
          </div>
          <span className="badge badge--muted">No saved casefile</span>
        </div>
        <p className="body-copy">Create a casefile to review and confirm the event facts being used.</p>
      </section>
    )
  }

  return (
    <section className="war-panel requirements-panel">
      <div className="war-panel__header">
        <div>
          <span className="war-eyebrow">Requirements</span>
          <h2>Confirm requirements</h2>
        </div>
        <span className={requirements.confirmed ? 'badge badge--ok' : 'badge badge--info'}>
          {requirements.confirmed && confirmedAt
            ? `Requirements confirmed · ${new Date(confirmedAt).toLocaleString()}`
            : 'Needs confirmation'}
        </span>
      </div>

      {!editing ? (
        <>
          <table className="data-table requirements-table">
            <tbody>
              <tr><th>Field</th><th>Current value</th><th>Source</th></tr>
              {requirements.fields.map((field) => (
                <tr key={field.key}>
                  <td>{field.label}</td>
                  <td>{displayRequirementValue(field)}</td>
                  <td><span className={badgeClass(field)}>{field.source_label}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          {requirements.conflicts.length > 0 && (
            <div className="block block--warn">
              <strong>Requirement notices</strong>
              <ul className="bullets">
                {requirements.conflicts.map((notice) => <li key={`${notice.field}-${notice.message}`}>{notice.message}</li>)}
              </ul>
            </div>
          )}
          {requirements.missing.length > 0 && (
            <div className="block block--warn">
              <strong>Missing facts</strong>
              <ul className="bullets">
                {requirements.missing.map((notice) => <li key={`${notice.field}-${notice.message}`}>{notice.message}</li>)}
              </ul>
            </div>
          )}

          <div className="requirements-actions">
            <button type="button" className="btn btn--ghost" onClick={beginEdit} disabled={saving}>
              Edit basics
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={confirmRequirements}
              disabled={saving || requirements.confirmed || missingCount > 0}
            >
              {saving ? 'Saving...' : requirements.confirmed ? 'Confirmed' : 'Confirm requirements'}
            </button>
          </div>
        </>
      ) : (
        <div className="requirements-edit-grid">
          <label className="field-compact">
            Working title
            <input className="input" value={draftBasics.working_title} onChange={(e) => update('working_title', e.target.value)} />
          </label>
          <label className="field-compact">
            Country
            <select className="select" value={draftBasics.country} onChange={(e) => update('country', e.target.value)}>
              <option value="">Not set</option>
              {COUNTRIES.map((country) => <option key={country} value={country}>{country}</option>)}
            </select>
          </label>
          <label className="field-compact">
            City
            <input className="input" value={draftBasics.city} onChange={(e) => update('city', e.target.value)} />
          </label>
          <label className="field-compact">
            Currency
            <select className="select" value={draftBasics.currency} onChange={(e) => update('currency', e.target.value)}>
              {CURRENCIES.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
            </select>
          </label>
          <label className="field-compact">
            Budget cap
            <input className="input" value={draftBasics.budget_cap ?? ''} onChange={(e) => update('budget_cap', e.target.value)} />
          </label>
          <label className="field-compact">
            Start date
            <input className="input" type="date" value={draftBasics.start_date} onChange={(e) => update('start_date', e.target.value)} />
          </label>
          <label className="field-compact">
            End date
            <input className="input" type="date" value={draftBasics.end_date} onChange={(e) => update('end_date', e.target.value)} />
          </label>
          <label className="field-compact">
            Expected turnout
            <input
              className="input"
              type="number"
              value={draftBasics.expected_turnout ?? ''}
              onChange={(e: ChangeEvent<HTMLInputElement>) => update('expected_turnout', e.target.value ? Number(e.target.value) : null)}
            />
          </label>
          <label className="field-compact">
            Event type
            <select className="select" value={draftBasics.event_type} onChange={(e) => update('event_type', e.target.value)}>
              <option value="">Not set</option>
              {EVENT_TYPES.map((eventType) => <option key={eventType.value} value={eventType.value}>{eventType.label}</option>)}
            </select>
          </label>
          <div className="requirements-actions requirements-actions--wide">
            <button type="button" className="btn btn--primary" onClick={saveChanges} disabled={saving}>
              {saving ? 'Saving...' : 'Save changes'}
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
