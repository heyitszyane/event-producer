import { useState, type FormEvent } from 'react'

export interface EventSpec {
  name?: string
  description?: string
  event_type?: string
  attendees?: number
  venue_type?: string
  duration_hours?: string | number
  date?: string
  missing_fields?: string[]
}

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
  onRun: (e: FormEvent) => void
  loading: boolean
  running: boolean
}

export default function EventCommandHeader({
  eventSpec,
  formData,
  formHandlers,
  onRun,
  loading,
  running,
}: EventCommandHeaderProps) {
  const [formOpen, setFormOpen] = useState(!eventSpec)

  const eventName = eventSpec?.name || 'New Event'
  const eventType = eventSpec?.event_type || '—'
  const eventDate = eventSpec?.date || '—'
  const headcount = eventSpec?.attendees ? String(eventSpec.attendees) : '—'
  const venue = eventSpec?.venue_type || '—'

  const toggleForm = () => setFormOpen((prev) => !prev)

  return (
    <header className="header">
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-3) var(--space-6)' }}>
        {/* Top row: event name + nav + run button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <div style={{ flex: '1 1 auto', minWidth: 200 }}>
            <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>
              {eventName}
            </h1>
            <p className="header__meta" style={{ marginTop: 'var(--space-1)' }}>
              {eventType} &middot; {eventDate} &middot; {headcount} attendees &middot; {venue}
            </p>
          </div>

          <nav className="header__nav" aria-label="Dashboard sections">
            <a href="#budget" className="nav-link">Budget</a>
            <a href="#schedule" className="nav-link">Schedule</a>
            <a href="#approvals" className="nav-link">Approvals</a>
            <a href="#risks" className="nav-link">Risks</a>
            <a href="#vendors" className="nav-link">Vendors</a>
            <a href="#chat" className="nav-link">Chat</a>
          </nav>

          <button
            onClick={onRun}
            disabled={loading}
            className={`btn btn--primary ${loading ? 'loading-pulse' : ''}`}
            aria-label={running ? 'Re-run event' : 'Run event'}
          >
            {loading ? 'Running...' : running ? 'Re-run' : 'Run Event'}
          </button>
        </div>

        {/* Configure / collapse toggle */}
        <div style={{ marginTop: 'var(--space-2)' }}>
          <button
            onClick={toggleForm}
            className="btn btn--sm"
            style={{ background: 'transparent', color: 'var(--accent)', padding: 0 }}
            aria-expanded={formOpen}
          >
            {formOpen ? 'Hide Configuration' : 'Configure'}
          </button>
        </div>
      </div>

      {/* Collapsible form panel */}
      {formOpen && (
        <div style={{ borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-tertiary)' }}>
          <form
            onSubmit={onRun}
            style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-4) var(--space-6)' }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Brief</span>
                <input
                  type="text"
                  value={formData.brief}
                  onChange={(e) => formHandlers.setBrief(e.target.value)}
                  placeholder="Describe the event"
                  className="input"
                />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Budget Cap</span>
                <input
                  type="text"
                  value={formData.budgetCap}
                  onChange={(e) => formHandlers.setBudgetCap(e.target.value)}
                  placeholder="5000"
                  className="input"
                />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Contingency %</span>
                <input
                  type="number"
                  value={formData.contingencyPct}
                  onChange={(e) => formHandlers.setContingencyPct(e.target.value)}
                  className="input"
                />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Attendees</span>
                <input
                  type="number"
                  value={formData.attendees}
                  onChange={(e) => formHandlers.setAttendees(Number(e.target.value))}
                  className="input"
                />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Event Type</span>
                <select
                  value={formData.eventType}
                  onChange={(e) => formHandlers.setEventType(e.target.value)}
                  className="select"
                >
                  <option value="corporate">Corporate</option>
                  <option value="wedding">Wedding</option>
                  <option value="conference">Conference</option>
                  <option value="social">Social</option>
                </select>
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Venue Type</span>
                <select
                  value={formData.venueType}
                  onChange={(e) => formHandlers.setVenueType(e.target.value)}
                  className="select"
                >
                  <option value="indoor">Indoor</option>
                  <option value="outdoor">Outdoor</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-secondary)' }}>Date</span>
                <input
                  type="date"
                  value={formData.date}
                  onChange={(e) => formHandlers.setDate(e.target.value)}
                  className="input"
                />
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
      )}
    </header>
  )
}
