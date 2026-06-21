import { useState, type FormEvent } from 'react'
import Head from 'next/head'
import EventCommandHeader from '../components/EventCommandHeader'
import ApprovalInbox from '../components/ApprovalInbox'
import ScopeCard, { type ScopeItem } from '../components/ScopeCard'
import BudgetCard, { type BudgetSummary } from '../components/BudgetCard'
import RunOfShowCard, { type ScheduleResult, type CallSheetEntry } from '../components/RunOfShowCard'
import VendorsCard, { type Vendor } from '../components/VendorsCard'
import RiskCard, { type RiskFlag } from '../components/RiskCard'
import ChatPane from '../components/ChatPane'
import ConflictReportCard, { type ConflictReport } from '../components/ConflictReportCard'

// In production, set NEXT_PUBLIC_API_BASE_URL to the Cloud Run backend URL.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

export interface RunEventResponse {
  event_id?: string
  status?: string
  event_spec?: Record<string, unknown>
  scope_items?: ScopeItem[]
  budget_summary?: BudgetSummary
  schedule_result?: ScheduleResult | null
  conflict_report?: ConflictReport | null
  call_sheet?: CallSheetEntry[]
  vendors?: Vendor[]
  risk_flags?: RiskFlag[]
  run_of_show?: {
    vendors?: Vendor[]
  }
  agent_trace?: Array<Record<string, unknown>>
  chat_log?: Array<Record<string, unknown>>
  approvals?: Array<Record<string, unknown>>
  security_beat?: Record<string, unknown>
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
  const [hasRun, setHasRun] = useState(false)

  async function handleRun(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Demo-User': 'demo-user',
        },
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
      setHasRun(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  // Fix: read vendors from run_of_show.vendors (not result.vendors)
  const vendors = result?.run_of_show?.vendors || result?.vendors || []

  return (
    <>
      <Head>
        <title>Event Producer Dashboard</title>
        <meta name="description" content="AI production crew for brand/experiential events" />
      </Head>

      <EventCommandHeader
        eventSpec={result?.event_spec || null}
        formData={{
          brief,
          budgetCap,
          contingencyPct,
          attendees,
          eventType,
          venueType,
          date,
        }}
        formHandlers={{
          setBrief,
          setBudgetCap,
          setContingencyPct,
          setAttendees,
          setEventType,
          setVenueType,
          setDate,
        }}
        onRun={handleRun}
        loading={loading}
        running={hasRun}
      />

      <main>
        {/* Error bar */}
        {error && (
          <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-3) var(--space-6)' }}>
            <div className="error-bar" role="alert">
              <span>Error: {error}</span>
              <button
                onClick={() => setError(null)}
                style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 'var(--text-md)', lineHeight: 1 }}
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* Pre-run empty state */}
        {!result && !error && !loading && (
          <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-8) var(--space-6)' }}>
            <div className="empty-state" style={{ textAlign: 'center', padding: 'var(--space-12)' }}>
              <p style={{ fontSize: 'var(--text-md)', color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
                Configure your event above and click <strong>Run Event</strong> to begin.
              </p>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
                The AI production crew will generate scope, budget, run-of-show, vendor coordination, and risk assessments.
              </p>
            </div>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-8) var(--space-6)' }}>
            <div className="empty-state loading-pulse" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
              <p style={{ fontSize: 'var(--text-md)', color: 'var(--text-inverse)' }}>
                Running event production pipeline...
              </p>
            </div>
          </div>
        )}

        {/* Two-column grid layout */}
        {result && (
          <div className="grid-2col" style={{ paddingTop: 'var(--space-5)', paddingBottom: 'var(--space-8' }}>
            {/* LEFT COLUMN: Budget, Scope, RunOfShow, ConflictReport */}
            <div className="stack">
              <BudgetCard budget={result.budget_summary || null} />
              <ScopeCard items={result.scope_items || []} />

              {result.schedule_result === null && result.conflict_report ? (
                <ConflictReportCard report={result.conflict_report} />
              ) : (
                <RunOfShowCard
                  schedule={result.schedule_result}
                  callSheet={result.call_sheet || []}
                />
              )}
            </div>

            {/* RIGHT COLUMN: Approvals, Risks, Vendors, Chat */}
            <div className="stack">
              <ApprovalInbox />
              <RiskCard risks={result.risk_flags || []} />
              <VendorsCard vendors={vendors} />
              <ChatPane />
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <span>
          Event Producer &mdash; AI Production Crew &mdash; Last run: {hasRun ? new Date().toLocaleTimeString() : 'Never'}
        </span>
      </footer>
    </>
  )
}
