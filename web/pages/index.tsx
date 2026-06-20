import { useState } from 'react'
import ChatPane from '../components/ChatPane'
import ApprovalInbox from '../components/ApprovalInbox'
import ScopeCard, { ScopeItem } from '../components/ScopeCard'
import BudgetCard, { BudgetSummary } from '../components/BudgetCard'
import RunOfShowCard, { ScheduleResult, CallSheetEntry } from '../components/RunOfShowCard'
import VendorsCard, { Vendor } from '../components/VendorsCard'
import RiskCard, { RiskFlag } from '../components/RiskCard'

export interface RunEventResponse {
  event_id?: string
  status?: string
  event_spec?: Record<string, unknown>
  scope_items?: ScopeItem[]
  budget_summary?: BudgetSummary
  schedule_result?: ScheduleResult | null
  call_sheet?: CallSheetEntry[]
  vendors?: Vendor[]
  risk_flags?: RiskFlag[]
  vendor_draft?: unknown
  run_of_show?: unknown
}

export default function Dashboard() {
  const [brief, setBrief] = useState('')
  const [budgetCap, setBudgetCap] = useState('')
  const [contingencyPct, setContingencyPct] = useState('10')
  const [attendees, setAttendees] = useState(50)
  const [eventType, setEventType] = useState('corporate')
  const [venueType, setVenueType] = useState('indoor')
  const [date, setDate] = useState('')
  const [result, setResult] = useState<RunEventResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleRun() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief,
          budget_cap: budgetCap,
          contingency_pct: contingencyPct,
          attendees,
          event_type: eventType,
          venue_type: venueType,
          date,
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`HTTP ${res.status}: ${text}`)
      }
      const data: RunEventResponse = await res.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 800, margin: '0 auto', padding: 24 }}>
      <h1>Event Producer Dashboard</h1>

      <div style={{ display: 'grid', gap: 12, marginBottom: 24 }}>
        <label>
          Brief
          <input
            type="text"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="Describe the event"
            style={{ width: '100%', padding: 8 }}
          />
        </label>

        <label>
          Budget Cap
          <input
            type="text"
            value={budgetCap}
            onChange={(e) => setBudgetCap(e.target.value)}
            placeholder="5000"
            style={{ width: '100%', padding: 8 }}
          />
        </label>

        <label>
          Contingency %
          <input
            type="number"
            value={contingencyPct}
            onChange={(e) => setContingencyPct(e.target.value)}
            style={{ width: '100%', padding: 8 }}
          />
        </label>

        <label>
          Attendees
          <input
            type="number"
            value={attendees}
            onChange={(e) => setAttendees(Number(e.target.value))}
            style={{ width: '100%', padding: 8 }}
          />
        </label>

        <label>
          Event Type
          <select value={eventType} onChange={(e) => setEventType(e.target.value)} style={{ width: '100%', padding: 8 }}>
            <option value="corporate">Corporate</option>
            <option value="wedding">Wedding</option>
            <option value="conference">Conference</option>
            <option value="social">Social</option>
          </select>
        </label>

        <label>
          Venue Type
          <select value={venueType} onChange={(e) => setVenueType(e.target.value)} style={{ width: '100%', padding: 8 }}>
            <option value="indoor">Indoor</option>
            <option value="outdoor">Outdoor</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </label>

        <label>
          Date
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            style={{ width: '100%', padding: 8 }}
          />
        </label>

        <button
          onClick={handleRun}
          disabled={loading}
          style={{ padding: '12px 24px', fontSize: 16, cursor: loading ? 'wait' : 'pointer' }}
        >
          {loading ? 'Running...' : 'Run Event'}
        </button>
      </div>

      {error && (
        <div style={{ color: 'red', marginBottom: 16 }}>Error: {error}</div>
      )}

      {result && (
        <div>
          <h2>Results</h2>

          <ScopeCard items={result.scope_items || []} />
          {result.budget_summary && <BudgetCard budget={result.budget_summary} />}
          <RunOfShowCard
            schedule={result.schedule_result}
            callSheet={result.call_sheet || []}
          />
          <VendorsCard vendors={result.vendors || []} />
          <RiskCard risks={result.risk_flags || []} />
        </div>
      )}

      <ChatPane />

      <ApprovalInbox />
    </div>
  )
}
