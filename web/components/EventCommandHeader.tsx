import { type FormEvent } from 'react'
import type { EventBasics } from '../types/agentic'

export interface FieldErrors {
  brief?: string
  budgetCap?: string
  expectedTurnout?: string
  startDate?: string
  endDate?: string
}

const EVENT_TYPES = [
  { value: 'corporate', label: 'Corporate' },
  { value: 'networking', label: 'Networking' },
  { value: 'product_launch', label: 'Product Launch' },
  { value: 'conference', label: 'Conference' },
]

const CURRENCIES = ['USD', 'SGD', 'THB', 'MYR', 'IDR', 'GBP', 'EUR', 'AUD']
const COUNTRIES = ['Singapore', 'United States', 'Thailand', 'Malaysia', 'Indonesia', 'United Kingdom', 'Australia']

export interface EventCommandHeaderProps {
  basics: EventBasics
  brief: string
  onBasicsChange: (next: EventBasics) => void
  onBriefChange: (value: string) => void
  fieldErrors?: FieldErrors
  onRun: (e: FormEvent) => void
  loading: boolean
  hasCasefile: boolean
}

export default function EventCommandHeader({
  basics,
  brief,
  onBasicsChange,
  onBriefChange,
  fieldErrors = {},
  onRun,
  loading,
  hasCasefile,
}: EventCommandHeaderProps) {
  function update<K extends keyof EventBasics>(field: K, value: EventBasics[K]) {
    onBasicsChange({ ...basics, [field]: value })
  }

  return (
    <header className="event-constraints">
      <div className="event-constraints__summary">
        <div className="event-constraints__title">
          <div>
            <span className="war-eyebrow">Event Basics</span>
            <p className="event-constraints__sub">
              Saved casefile fields are the source of truth for the production crew.
            </p>
          </div>
        </div>
      </div>

      <div className="event-constraints__body">
        <form onSubmit={onRun} className="event-constraints__form">
          <div className="event-constraints__grid">
            <label className="event-field">
              <span>Working title</span>
              <input
                type="text"
                value={basics.working_title}
                onChange={(e) => update('working_title', e.target.value)}
                placeholder="AI Industry Networking Night"
                className="input"
              />
            </label>

            <label className="event-field">
              <span>Country</span>
              <select
                value={basics.country}
                onChange={(e) => update('country', e.target.value)}
                className="select"
              >
                <option value="">Not set</option>
                {COUNTRIES.map((country) => <option key={country} value={country}>{country}</option>)}
              </select>
            </label>

            <label className="event-field">
              <span>City</span>
              <input
                type="text"
                value={basics.city}
                onChange={(e) => update('city', e.target.value)}
                placeholder="Singapore"
                className="input"
              />
            </label>

            <label className="event-field">
              <span>Currency</span>
              <select
                value={basics.currency}
                onChange={(e) => update('currency', e.target.value)}
                className="select"
              >
                {CURRENCIES.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
              </select>
            </label>

            <label className="event-field">
              <span>Budget cap</span>
              <input
                type="text"
                value={basics.budget_cap ?? ''}
                onChange={(e) => update('budget_cap', e.target.value)}
                placeholder="10000"
                className={`input ${fieldErrors.budgetCap ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.budgetCap}
              />
              {fieldErrors.budgetCap && <span className="field-error" role="alert">{fieldErrors.budgetCap}</span>}
            </label>

            <label className="event-field">
              <span>Start date</span>
              <input
                type="date"
                value={basics.start_date}
                onChange={(e) => update('start_date', e.target.value)}
                className={`input ${fieldErrors.startDate ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.startDate}
              />
              {fieldErrors.startDate && <span className="field-error" role="alert">{fieldErrors.startDate}</span>}
            </label>

            <label className="event-field">
              <span>End date</span>
              <input
                type="date"
                value={basics.end_date}
                onChange={(e) => update('end_date', e.target.value)}
                className={`input ${fieldErrors.endDate ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.endDate}
              />
              {fieldErrors.endDate && <span className="field-error" role="alert">{fieldErrors.endDate}</span>}
            </label>

            <label className="event-field">
              <span>Expected turnout</span>
              <input
                type="number"
                value={basics.expected_turnout ?? ''}
                onChange={(e) => update('expected_turnout', e.target.value ? Number(e.target.value) : null)}
                placeholder="100"
                className={`input ${fieldErrors.expectedTurnout ? 'input--error' : ''}`}
                aria-invalid={!!fieldErrors.expectedTurnout}
              />
              {fieldErrors.expectedTurnout && <span className="field-error" role="alert">{fieldErrors.expectedTurnout}</span>}
            </label>

            <label className="event-field">
              <span>Event type</span>
              <select
                value={basics.event_type}
                onChange={(e) => update('event_type', e.target.value)}
                className="select"
              >
                <option value="">Not set</option>
                {EVENT_TYPES.map((eventType) => (
                  <option key={eventType.value} value={eventType.value}>{eventType.label}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="event-field event-field--wide">
            <span>Event brief</span>
            <textarea
              className={`input intake-hero__textarea ${fieldErrors.brief ? 'input--error' : ''}`}
              value={brief}
              onChange={(e) => onBriefChange(e.target.value)}
              placeholder="Add event notes, goals, constraints, and context."
              rows={5}
              aria-label="Event brief"
            />
            {fieldErrors.brief && <span className="field-error" role="alert">{fieldErrors.brief}</span>}
          </label>

          <div className="event-constraints__actions">
            <button
              type="submit"
              disabled={loading}
              className={`btn btn--primary ${loading ? 'loading-pulse' : ''}`}
            >
              {loading
                ? 'Generating...'
                : hasCasefile
                ? 'Save casefile and generate first pass'
                : 'Create casefile and generate first pass'}
            </button>
          </div>
        </form>
      </div>
    </header>
  )
}
