import { useState } from 'react'
import { confirmCasefileRequirements } from '../lib/casefiles'
import type { CasefileState } from '../types/agentic'

interface RequirementsConfirmationProps {
  casefile: CasefileState | null
  onCasefileChange: (casefile: CasefileState) => void
  onError: (message: string) => void
}

// Compact confirmation bar. The editable facts live in the Event Basics form
// directly above this component, so no field table is repeated here.
export default function RequirementsConfirmation({
  casefile,
  onCasefileChange,
  onError,
}: RequirementsConfirmationProps) {
  const [saving, setSaving] = useState(false)
  const requirements = casefile?.requirements
  const missingCount = requirements?.missing.length
    || requirements?.fields.filter((field) => field.status === 'missing').length
    || 0
  const confirmedAt = casefile?.requirements_confirmed_at || requirements?.confirmed_at || null

  async function confirmRequirements() {
    if (!casefile) return
    setSaving(true)
    try {
      const confirmed = await confirmCasefileRequirements(casefile.event_id)
      onCasefileChange(confirmed)
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (!casefile || !requirements) {
    return null
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
            ? `Confirmed ${new Date(confirmedAt).toLocaleString()}`
            : 'Needs confirmation'}
        </span>
      </div>

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
        <p className="body-copy requirements-actions__hint">
          {requirements.confirmed
            ? 'The saved event facts above are confirmed for the production crew.'
            : 'Review the Event Basics above, then confirm them as the facts the production crew plans against.'}
        </p>
        <button
          type="button"
          className="btn btn--primary"
          onClick={confirmRequirements}
          disabled={saving || requirements.confirmed || missingCount > 0}
        >
          {saving ? 'Saving...' : requirements.confirmed ? 'Confirmed' : 'Confirm requirements'}
        </button>
      </div>
    </section>
  )
}
