import { useState } from 'react'
import ChatPane from '../components/ChatPane'
import ApprovalInbox from '../components/ApprovalInbox'
import ScopeCard, { ScopeItem } from '../components/ScopeCard'
import BudgetCard, { BudgetSummary } from '../components/BudgetCard'
import RunOfShowCard, { ScheduleResult, CallSheetEntry } from '../components/RunOfShowCard'
import VendorsCard, { Vendor } from '../components/VendorsCard'
import RiskCard, { RiskFlag } from '../components/RiskCard'

// In production, set NEXT_PUBLIC_API_BASE_URL to the Cloud Run backend URL.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

export interface Conflict {
	task_id: string
	conflicting_task_id: string
	conflict_type: string
	message: string
}

export interface ConflictReport {
	lead_time_conflicts: Conflict[]
	anchor_conflicts: Conflict[]
	cycle: string[]
	conflicts?: Conflict[]
}

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
	vendor_draft?: unknown
	run_of_show?: unknown
}

function conflictTypeLabel(type: string): string {
	switch (type) {
		case 'lead_time': return 'Lead Time Conflict'
		case 'anchor': return 'Anchor Conflict'
		case 'cycle': return 'Dependency Cycle'
		case 'missing_dependency': return 'Missing Dependency'
		case 'duplicate_id': return 'Duplicate Task ID'
		default: return type
	}
}

function ConflictReportCard({ report }: { report: ConflictReport }) {
	const allConflicts = [
		...(report.conflicts || []),
		...report.lead_time_conflicts,
		...report.anchor_conflicts,
	]

	return (
		<div style={{
			border: '1px solid #f87171',
			borderRadius: 8,
			padding: 16,
			marginBottom: 16,
			backgroundColor: '#fef2f2',
		}}>
			<h2 style={{ margin: '0 0 12px 0', fontSize: 18, fontWeight: 600, color: '#991b1b' }}>
				Schedule Conflicts Detected
			</h2>

			{allConflicts.length > 0 && (
				<div style={{ marginBottom: 12 }}>
					{allConflicts.map((c, idx) => (
						<div key={idx} style={{
							padding: '8px 12px',
							borderRadius: 6,
							marginBottom: 6,
							border: '1px solid #fecaca',
							backgroundColor: '#ffffff',
						}}>
							<div style={{ fontWeight: 600, fontSize: 14, color: '#991b1b' }}>
								{conflictTypeLabel(c.conflict_type)}
							</div>
							<div style={{ fontSize: 13, color: '#374151', marginTop: 2 }}>
								Task: <code style={{ backgroundColor: '#f3f4f6', padding: '1px 4px', borderRadius: 3 }}>{c.task_id}</code>
								{c.conflicting_task_id && (
									<> &rarr; <code style={{ backgroundColor: '#f3f4f6', padding: '1px 4px', borderRadius: 3 }}>{c.conflicting_task_id}</code></>
								)}
							</div>
							{c.message && (
								<div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
									{c.message}
								</div>
							)}
						</div>
					))}
				</div>
			)}

			{report.cycle.length > 0 && (
				<div style={{ marginBottom: 8 }}>
					<div style={{ fontWeight: 600, fontSize: 14, color: '#991b1b', marginBottom: 4 }}>
						Circular Dependency Detected
					</div>
					<div style={{ fontSize: 13, color: '#374151' }}>
						Cycle path: {report.cycle.join(' → ')} → {report.cycle[0]}
					</div>
				</div>
			)}

			<p style={{ fontSize: 12, color: '#6b7280', margin: 0 }}>
				Adjust task dependencies, lead times, or remove duplicate IDs and re-run.
			</p>
		</div>
	)
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
			const res = await fetch(`${API_BASE}/run`, {
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

			{!result && !error && (
				<p style={{ color: '#6b7280', fontSize: 14 }}>
					Run the seeded networking event to generate scope, budget, run-of-show, vendor draft, approvals, and risks.
				</p>
			)}

			{result && (
				<div>
					<h2>Results</h2>

					<ScopeCard items={result.scope_items || []} />
					{result.budget_summary && <BudgetCard budget={result.budget_summary} />}

					{result.schedule_result === null && result.conflict_report ? (
						<ConflictReportCard report={result.conflict_report} />
					) : (
						<RunOfShowCard
							schedule={result.schedule_result}
							callSheet={result.call_sheet || []}
						/>
					)}

					<VendorsCard vendors={result.vendors || []} />
					<RiskCard risks={result.risk_flags || []} />
				</div>
			)}

			<ChatPane />

			<ApprovalInbox />
		</div>
	)
}
