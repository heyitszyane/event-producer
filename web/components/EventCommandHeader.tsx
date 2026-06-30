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
    attendees: number
    eventType: string
    venueType: string
    date: string
  }
  formHandlers: {
    setBrief: (v: string) => void
    setBudgetCap: (v: string) => void
    setContingencyPct: (v: string) => void
    setAttendees: (v: number) => void
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
  const eventName = eventSpec?.name || 'New Event'
  const eventType = eventSpec?.event_type || '—'
  const eventDate = eventSpec?.date || '—'
  const headcount = eventSpec?.attendees ? String(eventSpec.attendees) : '—'
  const venue = eventSpec?.venue_type || '—'

  return (
    <header className="header">
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-3) var(--space-6)' }}>
        {/* Top row: event name + run button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <div style={{ flex: '1 1 auto', minWidth: 200 }}>
            <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>
              {eventName}
            </h1>
            <p
              className="header__sub"
              style={{ margin: 0, fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}
            >
              Constraints / manual overrides — optional
            </p>
            {running && (
              <p className="header__meta" style={{ marginTop: 'var(--space-1)' }}>
                {eventType} &middot; {eventDate} &middot; {headcount} attendees &middot; {venue}
              </p>
            )}
          </div>

          <button
            onClick={onRun}
            disabled={loading}
            className={`btn btn--primary ${loading ? 'loading-pulse' : ''}`}
            aria-label={running ? 'Re-run event' : 'Run event'}
          >
            {loading ? 'Running...' : running ? 'Re-run' : 'Update constraints'}
          </button>
        </div>
      </div>

      {/* Form panel — always visible but compact */}
      <div style={{ borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-tertiary)' }}>
        <form
          onSubmit={onRun}
          style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-4) var(--space-6)' }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
            {/* Brief — mirrors the intake hero above (kept for compact edits) */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Brief{' '}
                <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>
                  (primary input is above)
                </span>
              </span>
              <input
                type="text"
                value={formData.brief}
                onChange={(e) => formHandlers.setBrief(e.target.value)}
                placeholder="Describe the event"
                className={`input ${fieldErrors.brief ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.brief}
                aria-describedby={fieldErrors.brief ? 'error-brief' : undefined}
              />
              {fieldErrors.brief && (
                <span id="error-brief" className="field-error" role="alert">{fieldErrors.brief}</span>
              )}
            </label>

            {/* Budget Cap */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Budget Cap</span>
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

            {/* Contingency % */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Contingency %</span>
              <input
                type="number"
                value={formData.contingencyPct}
                onChange={(e) => formHandlers.setContingencyPct(e.target.value)}
                className={`input ${fieldErrors.contingencyPct ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.contingencyPct}
                aria-describedby={fieldErrors.contingencyPct ? 'error-contingencyPct' : undefined}
              />
              {fieldErrors.contingencyPct && (
                <span id="error-contingencyPct" className="field-error" role="alert">{fieldErrors.contingencyPct}</span>
              )}
            </label>

            {/* Attendees */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Attendees</span>
              <input
                type="number"
                value={formData.attendees}
                onChange={(e) => formHandlers.setAttendees(Number(e.target.value))}
                className={`input ${fieldErrors.attendees ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.attendees}
                aria-describedby={fieldErrors.attendees ? 'error-attendees' : undefined}
              />
              {fieldErrors.attendees && (
                <span id="error-attendees" className="field-error" role="alert">{fieldErrors.attendees}</span>
              )}
            </label>

            {/* Event Type */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Event Type</span>
              <select
                value={formData.eventType}
                onChange={(e) => formHandlers.setEventType(e.target.value)}
                className={`select ${fieldErrors.eventType ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.eventType}
                aria-describedby={fieldErrors.eventType ? 'error-eventType' : undefined}
              >
                {EVENT_TYPES.map((et) => (
                  <option key={et.value} value={et.value}>{et.label}</option>
                ))}
              </select>
              {fieldErrors.eventType && (
                <span id="error-eventType" className="field-error" role="alert">{fieldErrors.eventType}</span>
              )}
            </label>

            {/* Venue Type */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Venue Type</span>
              <select
                value={formData.venueType}
                onChange={(e) => formHandlers.setVenueType(e.target.value)}
                className={`select ${fieldErrors.venueType ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.venueType}
                aria-describedby={fieldErrors.venueType ? 'error-venueType' : undefined}
              >
                <option value="indoor">Indoor</option>
                <option value="outdoor">Outdoor</option>
                <option value="hybrid">Hybrid</option>
              </select>
              {fieldErrors.venueType && (
                <span id="error-venueType" className="field-error" role="alert">{fieldErrors.venueType}</span>
              )}
            </label>

            {/* Date */}
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Date</span>
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

          <div style={{ marginTop: 'var(--space-3)', display: 'flex', justifyContent: 'flex-end' }}>
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
