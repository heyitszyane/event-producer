import { useState, type FormEvent, type ChangeEvent } from 'react'
import Head from 'next/head'
import EventCommandHeader from '../components/EventCommandHeader'
import AgentCrewTrace from '../components/AgentCrewTrace'
import ApprovalInbox from '../components/ApprovalInbox'
import ScopeCard, { type ScopeItem } from '../components/ScopeCard'
import BudgetCard, { type BudgetSummary } from '../components/BudgetCard'
import RunOfShowCard, { type ScheduleResult, type CallSheetEntry } from '../components/RunOfShowCard'
import VendorsCard, { type Vendor } from '../components/VendorsCard'
import RiskCard, { type RiskFlag } from '../components/RiskCard'
import ChatPane from '../components/ChatPane'
import SecurityBeat from '../components/SecurityBeat'
import IntakeHero from '../components/IntakeHero'
import ExtractedRequirements from '../components/ExtractedRequirements'
import CreativeConcept from '../components/CreativeConcept'
import type {
  BriefIntake,
  CreativeConcept as CreativeConceptData,
  ModelModeSummary,
  AgentTraceStep,
  ProposedAction,
  OrchestratorChatResponse,
} from '../types/agentic'

// In production, set NEXT_PUBLIC_API_BASE_URL to the Cloud Run backend URL.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

// Backend-supported event types (must match _SCOPE_CATALOGUE keys)
const EVENT_TYPES = [
  { value: 'corporate', label: 'Corporate' },
  { value: 'networking', label: 'Networking' },
  { value: 'product_launch', label: 'Product Launch' },
  { value: 'conference', label: 'Conference' },
] as const

export interface RunEventResponse {
  event_id?: string
  status?: string
  model_mode_summary?: ModelModeSummary
  brief_intake?: BriefIntake | null
  creative_concept?: CreativeConceptData | null
  event_spec?: {
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
  scope_items?: ScopeItem[]
  budget_summary?: BudgetSummary
  schedule_result?: ScheduleResult | null
  call_sheet?: CallSheetEntry[]
  vendors?: Vendor[]
  risk_flags?: RiskFlag[]
  run_of_show?: {
    vendors?: Vendor[]
    approvals?: Approval[]
    risk_flags?: RiskFlag[]
  }
  agent_trace?: AgentTraceStep[]
  chat_log?: ChatMessage[]
  approvals?: Approval[]
  security_beat?: {
    status: string
    title?: string
    summary?: string
    source?: string
    external_action_executed?: boolean
    state_mutation_executed?: boolean
    blocked_actions?: string[]
    gate?: { name: string; load_bearing_control: boolean; reason: string }
    fixtures?: Array<{
      id: string
      channel: string
      label: string
      content: string
      flags: string[]
      classifier_role: string
      blocked_by: string
      external_action_executed: boolean
      ocr_implemented?: boolean
    }>
    approval_required?: boolean
    approval_id?: string
    notes?: string[]
    note?: string
  }
}

interface ChatMessage {
  role: string
  content: string
  agent?: string
}

interface Approval {
  id: string
  action: string
  requested_by: string
  status: string
  approved_by?: string
  timestamp?: string
  notes?: string
}

interface FormData {
  brief: string
  budgetCap: string
  contingencyPct: string
  attendees: number
  eventType: string
  venueType: string
  date: string
}

interface FieldErrors {
  brief?: string
  budgetCap?: string
  contingencyPct?: string
  attendees?: string
  eventType?: string
  venueType?: string
  date?: string
}

// P7A validation: the brief is the one required field (it's the primary
// product input). Constraints (budget, pax, type, venue, date, contingency)
// are optional manual overrides; if provided they must be well-formed, but if
// left blank the backend's AI intake resolves them (and records any gaps in
// brief_intake.missing_questions).
function validateForm(data: FormData): { valid: boolean; errors: FieldErrors } {
  const errors: FieldErrors = {}

  if (!data.brief.trim()) {
    errors.brief = 'Brief is required'
  }

  if (data.budgetCap.trim()) {
    const bc = parseFloat(data.budgetCap)
    if (isNaN(bc) || bc <= 0) {
      errors.budgetCap = 'Must be a positive number'
    }
  }

  if (data.contingencyPct.trim()) {
    const cp = parseFloat(data.contingencyPct)
    if (isNaN(cp) || cp < 0 || cp > 50) {
      errors.contingencyPct = 'Must be between 0 and 50'
    }
  }

  // attendees defaults to 50 when blank; validate only when non-defaulting.
  if (data.attendees && data.attendees <= 0) {
    errors.attendees = 'Must be greater than 0'
  }

  if (data.date) {
    const parsed = new Date(data.date)
    if (isNaN(parsed.getTime())) {
      errors.date = 'Invalid date format'
    }
  }

  return { valid: Object.keys(errors).length === 0, errors }
}

async function parseApiError(res: Response): Promise<string> {
  const text = await res.text()
  try {
    const data = JSON.parse(text)
    if (data?.error?.message) {
      return data.error.message
    }
    if (data?.detail) {
      if (Array.isArray(data.detail)) {
        return data.detail.map((d: { msg?: string; loc?: string[] }) =>
          d.msg ? `${d.loc?.join('.') ? d.loc.join('.') + ': ' : ''}${d.msg}` : JSON.stringify(d)
        ).join('; ')
      }
      return String(data.detail)
    }
    return data?.message || text
  } catch {
    return text || `HTTP ${res.status}`
  }
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
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [hasRun, setHasRun] = useState(false)
  // P7B — orchestrator chat state
  const [chatInput, setChatInput] = useState('')
  const [orchestratorProposals, setOrchestratorProposals] = useState<ProposedAction[]>([])
  const [chatReply, setChatReply] = useState<string | null>(null)

  async function handleRun(e: FormEvent) {
    e.preventDefault()

    const formData: FormData = {
      brief,
      budgetCap,
      contingencyPct,
      attendees,
      eventType,
      venueType,
      date,
    }

    const { valid, errors } = validateForm(formData)
    if (!valid) {
      setFieldErrors(errors)
      return
    }

    setFieldErrors({})
    setLoading(true)
    setError(null)

    try {
      // P7A: brief-primary. Constraints are optional manual overrides; when
      // blank we omit them (null) and let the AI intake resolve them.
      const body: Record<string, unknown> = { brief }
      if (budgetCap.trim()) body.budget_cap = budgetCap.trim()
      if (contingencyPct.trim()) body.contingency_pct = contingencyPct.trim()
      if (attendees && attendees > 0) body.attendees = attendees
      if (eventType) body.event_type = eventType
      if (venueType) body.venue_type = venueType
      if (date) body.date = date

      const res = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Demo-User': 'demo-user',
        },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const message = await parseApiError(res)
        throw new Error(message)
      }
      const data: RunEventResponse = await res.json()
      setResult(data)
      setHasRun(true)
    } catch (err) {
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError(
          `Backend is unreachable. Start the backend with: ` +
          `python3 -m uvicorn event_producer.main:create_app --factory --host 127.0.0.1 --port 8080 --reload`
        )
      } else {
        setError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      setLoading(false)
    }
  }

  // Derive data from response
  const vendors = result?.run_of_show?.vendors || result?.vendors || []
  const approvals = result?.approvals || result?.run_of_show?.approvals || []
  const agentTrace = result?.agent_trace || []
  const chatLog = result?.chat_log || []
  const riskFlags = result?.risk_flags || result?.run_of_show?.risk_flags || []
  const securityBeat = result?.security_beat

  // Hero strip budget health
  const budgetSummary = result?.budget_summary
  const scheduleResult = result?.schedule_result
  const criticalCount = scheduleResult?.critical_path?.length || 0
  const pendingApprovalCount = approvals.filter((a) => a.status === 'pending').length

  // P7B — orchestrator chat handler
  async function handleOrchestratorChat(e: FormEvent) {
    e.preventDefault()
    if (!result?.event_id || !chatInput.trim()) return

    const res = await fetch(`${API_BASE}/event/${result.event_id}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Demo-User': 'demo-user' },
      body: JSON.stringify({ message: chatInput }),
    })
    if (res.ok) {
      const data: OrchestratorChatResponse = await res.json()
      setChatReply(data.reply)
      setOrchestratorProposals(data.proposals)
      setChatInput('')
    }
  }

  // P7B — apply a proposal
  async function applyProposal(proposal: ProposedAction) {
    if (!result?.event_id) return
    const res = await fetch(`${API_BASE}/event/${result.event_id}/proposals/${proposal.id}/apply`, {
      method: 'POST',
      headers: { 'X-Demo-User': 'demo-user' },
    })
    if (res.ok) {
      const data = await res.json()
      // Update scope items and budget from response
      setResult((prev) => ({
        ...prev,
        scope_items: data.scope_items,
        budget_summary: data.budget_summary,
        schedule_result: data.schedule_result,
      }) as RunEventResponse)
      setOrchestratorProposals((prev) => prev.filter((p) => p.id !== proposal.id))
    }
  }

  // P7B — handle creative suggestion → add to scope
  async function handleAddToScope(suggestion: {
    title: string
    description: string
    category: string
    estimated_cost?: string | null
    tier?: string
  }) {
    if (!result?.event_id) return
    const cost = suggestion.estimated_cost || '1000'
    const res = await fetch(`${API_BASE}/event/${result.event_id}/scope-items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Demo-User': 'demo-user' },
      body: JSON.stringify({
        name: suggestion.title,
        description: suggestion.description,
        category: suggestion.category,
        tier: (suggestion.tier as 'must' | 'should' | 'could' | 'wow') || 'could',
        estimated_cost: cost,
        qty: '1',
      }),
    })
    if (res.ok) {
      const data = await res.json()
      setResult((prev) => ({
        ...prev,
        scope_items: data.scope_items,
        budget_summary: data.budget_summary,
      }) as RunEventResponse)
    }
  }

  return (
    <>
      <Head>
        <title>Event Producer — Mission Control</title>
        <meta name="description" content="AI production crew for brand/experiential events" />
      </Head>

      {/* ── Hero strip ── */}
      {result && (
        <div className="hero-strip">
          <div className="hero-strip__inner">
            <div className="hero-strip__identity">
              <h1 className="hero-strip__title">
                {String(result.event_spec?.name || 'Event')}
              </h1>
              <span className="hero-strip__meta">
                {String(result.event_spec?.event_type || '—')} &middot;{' '}
                {String(result.event_spec?.date || '—')} &middot;{' '}
                {String(result.event_spec?.attendees || '—')} attendees
              </span>
            </div>
            <div className="hero-strip__metrics">
              <div className="hero-metric">
                <span className="hero-metric__value hero-metric__value--ok">
                  {budgetSummary
                    ? `$${Math.round(parseFloat(String(budgetSummary.headroom || '0'))).toLocaleString('en-US')}`
                    : '—'}
                </span>
                <span className="hero-metric__label">Headroom</span>
              </div>
              <div className="hero-metric">
                <span className={`hero-metric__value ${
                  budgetSummary?.over_budget
                    ? 'hero-metric__value--critical'
                    : 'hero-metric__value--ok'
                }`}>
                  {budgetSummary?.over_budget ? 'OVER BUDGET' : 'ON TRACK'}
                </span>
                <span className="hero-metric__label">Budget</span>
              </div>
              <div className="hero-metric">
                <span className="hero-metric__value">
                  {scheduleResult?.ordered_tasks?.length || 0} tasks
                </span>
                <span className="hero-metric__label">
                  {criticalCount > 0 ? `${criticalCount} critical` : 'Schedule'}
                </span>
              </div>
              {pendingApprovalCount > 0 && (
                <div className="hero-metric">
                  <span className="hero-metric__value hero-metric__value--warn">
                    {pendingApprovalCount}
                  </span>
                  <span className="hero-metric__label">Pending Approval</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── P7A: primary intake (messy brief) ── */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-6) var(--space-6) 0' }}>
        <IntakeHero
          brief={brief}
          onBriefChange={setBrief}
          onSubmit={handleRun}
          loading={loading}
          hasRun={hasRun}
        />
      </div>

      {/* ── Constraints / manual overrides ── */}
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
          setAttendees: (v) => setAttendees(v),
          setEventType,
          setVenueType,
          setDate,
        }}
        fieldErrors={fieldErrors}
        onRun={handleRun}
        loading={loading}
        running={hasRun}
      />

      <main>
        {/* Error bar */}
        {error && (
          <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-3) var(--space-6)' }}>
            <div className="error-bar" role="alert">
              <span>{
                error.includes('Failed to fetch') || error.includes('unreachable')
                  ? error
                  : `Error: ${error}`
              }</span>
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
                Describe your event in the brief above and click{' '}
                <strong>Analyze with AI Production Crew</strong>.
              </p>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)' }}>
                The AI production crew interprets the brief, proposes a creative
                direction, and runs deterministic budget + scheduling engines.
              </p>
            </div>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div style={{ maxWidth: 1200, margin: '0 auto', padding: 'var(--space-8) var(--space-6)' }}>
            <div className="loading-state" style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
              <div className="loading-spinner" />
              <p style={{ fontSize: 'var(--text-md)', color: 'var(--text-secondary)', marginTop: 'var(--space-4)' }}>
                Running event production pipeline...
              </p>
            </div>
          </div>
        )}

        {/* Mission control layout after run */}
        {result && (
          <div className="mc-grid">
            {/* LEFT COLUMN: Extracted → Creative → Scope → Budget → Schedule */}
            <div className="stack">
              <ExtractedRequirements intake={result.brief_intake ?? null} />
              <CreativeConcept
                concept={result.creative_concept ?? null}
                onAddToScope={handleAddToScope}
              />
              <ScopeCard
                items={result.scope_items || []}
                eventId={result.event_id}
                onItemsChange={(items) =>
                  setResult((prev) => ({ ...prev, scope_items: items }) as RunEventResponse)
                }
              />
              <BudgetCard budget={result.budget_summary || null} />
              <RunOfShowCard
                schedule={result.schedule_result}
                callSheet={result.call_sheet || []}
              />
            </div>

            {/* RIGHT COLUMN: Trace → Approvals → Security → Vendors → Risks → Chat */}
            <div className="stack">
              <AgentCrewTrace steps={agentTrace} />
              <ApprovalInbox
                approvals={approvals}
                defaultExpanded={pendingApprovalCount > 0}
              />
              <SecurityBeat securityBeat={securityBeat || null} />
              <VendorsCard vendors={vendors} />
              <RiskCard risks={riskFlags} />
              {/* P7B — Orchestrator Chat */}
              <section className="card" id="orchestrator-chat">
                <div className="card__header">
                  <h2>Orchestrator Chat</h2>
                </div>
                <div style={{ padding: 'var(--space-3)' }}>
                  <form onSubmit={handleOrchestratorChat}>
                    <textarea
                      value={chatInput}
                      onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setChatInput(e.target.value)}
                      placeholder="Ask for suggestions (e.g., 'Make this feel more premium')"
                      disabled={!result?.event_id}
                      rows={2}
                      style={{ width: '100%', marginBottom: 'var(--space-2)' }}
                    />
                    <button type="submit" disabled={!result?.event_id || loading} className="btn btn--primary">
                      Ask Orchestrator
                    </button>
                  </form>
                  {chatReply && (
                    <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-2)', background: 'var(--surface-tertiary)', borderRadius: 'var(--radius-md)' }}>
                      <strong>Reply:</strong> {chatReply}
                    </div>
                  )}
                  {orchestratorProposals.length > 0 && (
                    <div style={{ marginTop: 'var(--space-3)' }}>
                      <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>Proposals</h3>
                      {orchestratorProposals.map((p) => (
                        <div key={p.id} className="card card--inset" style={{ marginBottom: 'var(--space-2)' }}>
                          <div style={{ fontWeight: 600 }}>{p.title}</div>
                          <div style={{ fontSize: 'var(--text-sm)' }}>{p.rationale}</div>
                          <button onClick={() => applyProposal(p)} className="btn btn--sm" style={{ marginTop: 'var(--space-1)' }}>
                            Apply
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
              <ChatPane messages={chatLog} />
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
