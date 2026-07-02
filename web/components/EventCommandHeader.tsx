import { type FormEvent } from 'react'

export interface EventSpec {
  name?: string
  description?: string
  event_type?: string
  attendees?: number | string
  venue_type?: string
  duration_hours?: string | number
  date?: string
  missing_fields?: string[]
  [key: string]: unknown
}

export interface FieldErrors {
  brief?: string
  budgetCap?: string
  contingencyPct?: string
  attendees?: string
  eventType?: string
  venueType?: string
  date?: string
}

// Backend-supported event types (must match _SCOPE_CATALOGUE keys)
const EVENT_TYPES = [
  { value: 'corporate', label: 'Corporate' },
  { value: 'networking', label: 'Networking' },
  { value: 'product_launch', label: 'Product Launch' },
  { value: 'conference', label: 'Conference' },
]

export interface EventCommandHeaderProps {
  eventSpec: EventSpec | null
  formData: {
    brief: string
    budgetCap: string
    contingencyPct: string
    attendees: number | ''
    eventType: string
    venueType: string
    date: string
  }
  formHandlers: {
    setBrief: (v: string) => void
    setBudgetCap: (v: string) => void
    setContingencyPct: (v: string) => void
    setAttendees: (v: number | '') => void
    setEventType: (v: string) => void
    setVenueType: (v: string) => void
    setDate: (v: string) => void
  }
  fieldErrors?: FieldErrors
  onRun: (e: FormEvent) => void
  loading: boolean
  running: boolean
}

export default function EventCommandHeader({
  eventSpec,
  formData,
  formHandlers,
  fieldErrors = {},
  onRun,
  loading,
  running,
}: EventCommandHeaderProps) {
  const eventType = eventSpec?.event_type || '—'
  const eventDate = eventSpec?.date || '—'
  const headcount = eventSpec?.attendees ? String(eventSpec.attendees) : '—'
  const venue = eventSpec?.venue_type || '—'
  const manualActive = {
    budgetCap: Boolean(formData.budgetCap.trim()),
    contingencyPct: Boolean(formData.contingencyPct.trim()),
    attendees: formData.attendees !== '',
    eventType: Boolean(formData.eventType),
    venueType: Boolean(formData.venueType),
    date: Boolean(formData.date),
  }

  function OverrideBadge({ active }: { active: boolean }) {
    return active ? <span className="badge badge--warn">manual override</span> : null
  }

  return (
    <header className="event-constraints">
      <div className="event-constraints__summary">
        <div className="event-constraints__title">
          <div>
            <span className="war-eyebrow">MANUAL CONSTRAINTS</span>
            <p className="event-constraints__sub">
              Optional manual constraints. Filled/enabled values override AI extraction.
            </p>
            {running && (
              <p className="event-constraints__meta">
                {eventType} &middot; {eventDate} &middot; {headcount} attendees &middot; {venue}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="event-constraints__body">
        <form
          onSubmit={onRun}
          className="event-constraints__form"
        >
          <div className="event-constraints__grid">
            {/* Budget Cap */}
            <label className="event-field">
              <span>Budget Cap <OverrideBadge active={manualActive.budgetCap} /></span>
              <input
                type="text"
                value={formData.budgetCap}
                onChange={(e) => formHandlers.setBudgetCap(e.target.value)}
                placeholder="10000"
                className={`input ${fieldErrors.budgetCap ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.budgetCap}
                aria-describedby={fieldErrors.budgetCap ? 'error-budgetCap' : undefined}
              />
              {fieldErrors.budgetCap && (
                <span id="error-budgetCap" className="field-error" role="alert">{fieldErrors.budgetCap}</span>
              )}
            </label>

            {/* Contingency % - empty by default, brief extraction primary */}
            <label className="event-field">
              <span>Contingency % <OverrideBadge active={manualActive.contingencyPct} /></span>
              <input
                type="number"
                value={formData.contingencyPct}
                onChange={(e) => formHandlers.setContingencyPct(e.target.value)}
                placeholder="e.g. 10"
                className={`input ${fieldErrors.contingencyPct ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.contingencyPct}
                aria-describedby={fieldErrors.contingencyPct ? 'error-contingencyPct' : undefined}
              />
              {fieldErrors.contingencyPct && (
                <span id="error-contingencyPct" className="field-error" role="alert">{fieldErrors.contingencyPct}</span>
              )}
            </label>

            {/* Attendees - empty by default, brief extraction primary */}
            <label className="event-field">
              <span>Attendees <OverrideBadge active={manualActive.attendees} /></span>
              <input
                type="number"
                value={formData.attendees}
                onChange={(e) => {
                  const v = e.target.value
                  formHandlers.setAttendees(v ? Number(v) : '')
                }}
                placeholder="e.g. 100"
                className={`input ${fieldErrors.attendees ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.attendees}
                aria-describedby={fieldErrors.attendees ? 'error-attendees' : undefined}
              />
              {fieldErrors.attendees && (
                <span id="error-attendees" className="field-error" role="alert">{fieldErrors.attendees}</span>
              )}
            </label>

            {/* Event Type */}
            <label className="event-field">
              <span>Event Type <OverrideBadge active={manualActive.eventType} /></span>
              <select
                value={formData.eventType}
                onChange={(e) => formHandlers.setEventType(e.target.value)}
                className={`select ${fieldErrors.eventType ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.eventType}
                aria-describedby={fieldErrors.eventType ? 'error-eventType' : undefined}
              >
                <option value="">From brief</option>
                {EVENT_TYPES.map((et) => (
                  <option key={et.value} value={et.value}>{et.label}</option>
                ))}
              </select>
              {fieldErrors.eventType && (
                <span id="error-eventType" className="field-error" role="alert">{fieldErrors.eventType}</span>
              )}
            </label>

            {/* Venue Type */}
            <label className="event-field">
              <span>Venue Type <OverrideBadge active={manualActive.venueType} /></span>
              <select
                value={formData.venueType}
                onChange={(e) => formHandlers.setVenueType(e.target.value)}
                className={`select ${fieldErrors.venueType ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.venueType}
                aria-describedby={fieldErrors.venueType ? 'error-venueType' : undefined}
              >
                <option value="">From brief</option>
                <option value="indoor">Indoor</option>
                <option value="outdoor">Outdoor</option>
                <option value="hybrid">Hybrid</option>
              </select>
              {fieldErrors.venueType && (
                <span id="error-venueType" className="field-error" role="alert">{fieldErrors.venueType}</span>
              )}
            </label>

            {/* Date */}
            <label className="event-field">
              <span>Date <OverrideBadge active={manualActive.date} /></span>
              <input
                type="date"
                value={formData.date}
                onChange={(e) => formHandlers.setDate(e.target.value)}
                className={`input ${fieldErrors.date ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.date}
                aria-describedby={fieldErrors.date ? 'error-date' : undefined}
              />
              {fieldErrors.date && (
                <span id="error-date" className="field-error" role="alert">{fieldErrors.date}</span>
              )}
            </label>
          </div>

          <div className="event-constraints__actions">
            <button
              type="submit"
              disabled={loading}
              className={`btn btn--primary ${loading ? 'loading-pulse' : ''}`}
            >
              {loading ? 'Running...' : running ? 'Re-run Event' : 'Run Event'}
            </button>
          </div>
        </form>
      </div>
    </header>
  )
}
