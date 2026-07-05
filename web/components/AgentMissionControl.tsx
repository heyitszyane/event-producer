import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/api'
import { getCasefile, getCasefileArtifact, runSpecialistAgent } from '../lib/casefiles'
import { humanizeSummary } from '../lib/humanize'
import CreativeConcept from './CreativeConcept'
import ScopeStrategy from './ScopeStrategy'
import type {
  AgentMode,
  AgentTraceStep,
  CasefileArtifact,
  CasefileState,
  CreativeConcept as CreativeConceptData,
  ModelModeSummary,
  ScopeStrategy as ScopeStrategyData,
  SpecialistAgentId,
} from '../types/agentic'
import { MODE_CLASS, MODE_LABEL } from '../types/agentic'

// ---------------------------------------------------------------------------
// Registry card shape — mirrors the frontmatter contract served by GET /agents
// (source of truth: event_producer/agents/cards/*.md, loaded at runtime).
// ---------------------------------------------------------------------------

type AgentKind = 'llm_agent' | 'rule_based_agent' | 'deterministic_engine' | 'structural_gate'

interface AgentCard {
  name: string
  title: string
  kind: AgentKind
  order: number
  card_version: string
  purpose: string
  capabilities: string[]
  input: { required: string[]; optional: string[] }
  output: { artifact: string | null; format: string; schema: string | null }
  boundaries: {
    proposes_only: boolean
    mutates_critical_facts: boolean
    external_actions: string
    requires_human_approval_for: string[]
  }
  model_routing: { reason_step: string; formatter_step: string; prompt: string } | null
  runtime: {
    module: string
    mode_key: keyof ModelModeSummary | null
    trace_role: string | null
    direct_agent_id: SpecialistAgentId | null
  }
  ui: { route: string }
  source_file: string
}

const KIND_LABEL: Record<AgentKind, string> = {
  llm_agent: 'LLM agent',
  rule_based_agent: 'Rule-based',
  deterministic_engine: 'Deterministic engine',
  structural_gate: 'Structural gate',
}

// Honest default mode per kind, used until a run reports the actual mode.
const KIND_DEFAULT_MODE: Record<AgentKind, AgentMode | null> = {
  llm_agent: null,
  rule_based_agent: 'deterministic_engine',
  deterministic_engine: 'deterministic_engine',
  structural_gate: 'human_approval_gate',
}

const ROUTE_ACTION_LABEL: Record<string, string> = {
  brief: 'Open Brief Intake',
  scope: 'Open Scope ledger',
  budget: 'Open Budget',
  'run-sheet': 'Open Run Sheet',
  approvals: 'Open Approvals',
  vendors: 'Open Vendor Copy',
}

const SPECIALIST_PLACEHOLDER: Partial<Record<SpecialistAgentId, string>> = {
  creative_concept: 'Generate three more concepts that feel premium but stay budget-conscious.',
  scope_strategy: 'Cut this down to fit the budget cap without losing the core goal.',
  vendor_copy: 'Draft a short venue inquiry I can copy to vendors.',
  risk_review: 'Check what is missing before I contact vendors.',
}

type AgentPayload = Record<string, unknown>

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function payloadMode(payload?: AgentPayload): AgentMode | null {
  const mode = payload?.model_mode
  return typeof mode === 'string' && mode in MODE_LABEL ? mode as AgentMode : null
}

function summaryMode(value?: string): AgentMode | null {
  return value && value in MODE_LABEL ? value as AgentMode : null
}

// One-line "what happened last" for a card.
function lastActivity(card: AgentCard, artifact?: CasefileArtifact, traceStep?: AgentTraceStep): string {
  if (artifact) return `Artifact saved ${new Date(artifact.updated_at).toLocaleString()}`
  if (traceStep?.output_summary) return humanizeSummary(traceStep.output_summary)
  return 'Not run yet'
}

function specialistSummary(card: AgentCard, payload?: AgentPayload): string | null {
  const output = asRecord(payload?.output)
  if (card.runtime.direct_agent_id === 'creative_concept') return asText(output.concept_summary) || null
  if (card.runtime.direct_agent_id === 'scope_strategy') return asText(output.strategy_summary) || null
  if (card.runtime.direct_agent_id === 'vendor_copy') {
    return asText(output.ask_summary) || asText(output.subject) || null
  }
  if (card.runtime.direct_agent_id === 'risk_review') {
    return asText(asArray(output.recommended_next_actions)[0]) || null
  }
  return null
}

function RiskPreview({ payload }: { payload?: AgentPayload }) {
  const output = asRecord(payload?.output)
  const flags = asArray(output.risk_flags).map(asRecord)
  if (flags.length === 0) return null
  return (
    <ul className="compact-list mission-card__preview">
      {flags.slice(0, 4).map((flag) => (
        <li key={`${asText(flag.category)}-${asText(flag.message)}`}>
          {asText(flag.category)}: {asText(flag.message)}
        </li>
      ))}
    </ul>
  )
}

function VendorCopyPreview({ payload }: { payload?: AgentPayload }) {
  const output = asRecord(payload?.output)
  if (!asText(output.subject) && !asText(output.body)) return null
  return (
    <div className="mission-card__preview specialist-preview--draft">
      {asText(output.subject) && <p><strong>{asText(output.subject)}</strong></p>}
      {asText(output.body) && <pre>{asText(output.body)}</pre>}
    </div>
  )
}

export interface AgentMissionControlProps {
  casefile: CasefileState | null
  trace: AgentTraceStep[]
  modelModeSummary?: ModelModeSummary
  creativeConcept?: CreativeConceptData | null
  scopeStrategy?: ScopeStrategyData | null
  onCasefileChange: (casefile: CasefileState) => void
  onError: (message: string) => void
  onNavigate: (target: string) => void
  onAddToScope: (suggestion: {
    title: string
    description: string
    category: string
    estimated_cost?: string | null
    tier?: string
  }) => void
}

export default function AgentMissionControl({
  casefile,
  trace,
  modelModeSummary,
  creativeConcept,
  scopeStrategy,
  onCasefileChange,
  onError,
  onNavigate,
  onAddToScope,
}: AgentMissionControlProps) {
  const [cards, setCards] = useState<AgentCard[]>([])
  const [registryError, setRegistryError] = useState<string | null>(null)
  const [instructions, setInstructions] = useState<Partial<Record<SpecialistAgentId, string>>>({})
  const [running, setRunning] = useState<SpecialistAgentId | null>(null)
  const [payloads, setPayloads] = useState<Partial<Record<SpecialistAgentId, AgentPayload>>>({})

  const artifactMap = useMemo(() => casefile?.artifacts || {}, [casefile?.artifacts])
  const eventId = casefile?.event_id

  // The crew registry is served from the runtime-loaded skill cards, so the
  // board renders the same contracts the backend enforces.
  useEffect(() => {
    let cancelled = false
    async function loadRegistry() {
      try {
        const res = await apiFetch('/agents')
        const data: { agents: AgentCard[] } = await res.json()
        if (!cancelled) {
          setCards(data.agents)
          setRegistryError(null)
        }
      } catch {
        if (!cancelled) setRegistryError('Agent registry unavailable — is the backend running?')
      }
    }
    void loadRegistry()
    return () => {
      cancelled = true
    }
  }, [])

  // Hydrate saved specialist artifacts so output survives a reload.
  useEffect(() => {
    if (!eventId || cards.length === 0) {
      setPayloads({})
      return
    }
    let cancelled = false
    async function loadSaved() {
      const next: Partial<Record<SpecialistAgentId, AgentPayload>> = {}
      await Promise.all(cards.map(async (card) => {
        const agentId = card.runtime.direct_agent_id
        const artifactName = card.output.artifact
        if (!agentId || !artifactName || !artifactMap[artifactName]) return
        try {
          const artifact = await getCasefileArtifact(eventId as string, artifactName)
          next[agentId] = asRecord(artifact.payload)
        } catch {
          // Missing or unreadable artifact — the card just shows "Not run yet".
        }
      }))
      if (!cancelled) setPayloads(next)
    }
    void loadSaved()
    return () => {
      cancelled = true
    }
  }, [eventId, artifactMap, cards])

  async function handleRun(agentId: SpecialistAgentId, artifactName: string | null, regenerate: boolean) {
    if (!casefile) return
    setRunning(agentId)
    onError('')
    try {
      const response = await runSpecialistAgent(casefile.event_id, agentId, {
        instruction: instructions[agentId] || '',
        regenerate,
        artifact_id: artifactName ? artifactMap[artifactName]?.name || null : null,
      })
      setPayloads((current) => ({ ...current, [agentId]: asRecord(response.output) }))
      const refreshed = await getCasefile(casefile.event_id)
      onCasefileChange(refreshed)
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Could not run the specialist agent.')
    } finally {
      setRunning(null)
    }
  }

  const traceByRole = useMemo(() => {
    const map = new Map<string, AgentTraceStep>()
    for (const step of trace) map.set(step.role, step)
    return map
  }, [trace])

  const liveCount = Object.values(modelModeSummary || {}).filter((mode) => String(mode).includes('live')).length

  function cardMode(card: AgentCard): AgentMode | null {
    const agentId = card.runtime.direct_agent_id
    if (agentId && payloads[agentId]) {
      const mode = payloadMode(payloads[agentId])
      if (mode) return mode
    }
    if (card.runtime.mode_key && modelModeSummary) {
      const mode = summaryMode(modelModeSummary[card.runtime.mode_key])
      if (mode) return mode
    }
    const traceStep = card.runtime.trace_role ? traceByRole.get(card.runtime.trace_role) : undefined
    if (traceStep?.model_mode) return traceStep.model_mode
    return KIND_DEFAULT_MODE[card.kind]
  }

  return (
    <section className="card mission-control" aria-labelledby="mission-control-heading">
      <div className="card__header">
        <div>
          <span className="war-eyebrow">Runtime-loaded agent skill cards</span>
          <h2 id="mission-control-heading">Production Crew</h2>
        </div>
        <div className="cluster">
          <span className={casefile ? 'badge badge--ok' : 'badge badge--muted'}>
            {casefile ? 'Casefile loaded' : 'Save a casefile first'}
          </span>
          <span className="badge badge--info">
            {cards.length} roles{liveCount > 0 ? ` · ${liveCount} live` : ''}
          </span>
        </div>
      </div>

      {registryError && <div className="block block--warn">{registryError}</div>}

      <div className="mission-grid">
        {cards.map((card) => {
          const agentId = card.runtime.direct_agent_id
          const artifact = card.output.artifact ? artifactMap[card.output.artifact] : undefined
          const payload = agentId ? payloads[agentId] : undefined
          const traceStep = card.runtime.trace_role ? traceByRole.get(card.runtime.trace_role) : undefined
          const mode = cardMode(card)
          const isRunning = running === agentId
          const fallbackReason = asText(payload?.fallback_reason) || traceStep?.fallback_reason || null
          const summary = specialistSummary(card, payload)
          const routeAction = ROUTE_ACTION_LABEL[card.ui.route]
          const isOrchestrator = card.name === 'orchestrator'

          return (
            <article className={`mission-card mission-card--${card.kind}`} key={card.name}>
              <div className="mission-card__top">
                <div>
                  <h3>{card.title}</h3>
                  <p className="mission-card__purpose">{card.purpose}</p>
                </div>
                <div className="mission-card__badges">
                  <span className="mission-kind">{KIND_LABEL[card.kind]}</span>
                  <span className={`badge ${mode ? MODE_CLASS[mode] : 'badge--muted'}`}>
                    {mode ? MODE_LABEL[mode] : 'Awaiting run'}
                  </span>
                </div>
              </div>

              <div className="mission-card__meta">
                <span>{lastActivity(card, artifact, traceStep)}</span>
                {fallbackReason && <span>Fallback: {fallbackReason}</span>}
              </div>

              {summary && <p className="mission-card__summary">{summary}</p>}

              {agentId && (
                <>
                  <textarea
                    className="textarea mission-card__input"
                    value={instructions[agentId] || ''}
                    onChange={(event) => setInstructions((current) => ({ ...current, [agentId]: event.target.value }))}
                    placeholder={SPECIALIST_PLACEHOLDER[agentId]}
                    disabled={!casefile || isRunning}
                    rows={2}
                  />
                  <div className="mission-card__actions">
                    <button
                      type="button"
                      className="btn btn--primary btn--xs"
                      disabled={!casefile || isRunning}
                      onClick={() => handleRun(agentId, card.output.artifact, false)}
                    >
                      {isRunning ? 'Running...' : 'Ask this agent'}
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--xs"
                      disabled={!casefile || isRunning || !artifact}
                      onClick={() => handleRun(agentId, card.output.artifact, true)}
                    >
                      Refine
                    </button>
                    {routeAction && card.ui.route !== 'ai-crew' && (
                      <button type="button" className="btn btn--ghost btn--xs" onClick={() => onNavigate(card.ui.route)}>
                        {routeAction}
                      </button>
                    )}
                  </div>
                </>
              )}

              {isOrchestrator && (
                <div className="mission-card__actions">
                  <a className="btn btn--ghost btn--xs" href="#orchestrator-chat">
                    Use the console above
                  </a>
                </div>
              )}

              {!agentId && !isOrchestrator && routeAction && (
                <div className="mission-card__actions">
                  <button type="button" className="btn btn--ghost btn--xs" onClick={() => onNavigate(card.ui.route)}>
                    {routeAction}
                  </button>
                </div>
              )}

              {agentId === 'vendor_copy' && <VendorCopyPreview payload={payload} />}
              {agentId === 'risk_review' && <RiskPreview payload={payload} />}

              {agentId === 'creative_concept' && creativeConcept && (
                <details className="mission-card__detail">
                  <summary>Full concept output</summary>
                  <div className="mission-embed">
                    <CreativeConcept concept={creativeConcept} onAddToScope={onAddToScope} />
                  </div>
                </details>
              )}
              {agentId === 'scope_strategy' && scopeStrategy && (
                <details className="mission-card__detail">
                  <summary>Full strategy output</summary>
                  <div className="mission-embed">
                    <ScopeStrategy strategy={scopeStrategy} />
                  </div>
                </details>
              )}

              <details className="mission-card__detail">
                <summary>Role card</summary>
                <div className="mission-card__contract">
                  <p className="small"><strong>Capabilities</strong></p>
                  <ul className="compact-list">
                    {card.capabilities.map((capability) => <li key={capability}>{capability}</li>)}
                  </ul>
                  <p className="small"><strong>Boundaries</strong></p>
                  <ul className="compact-list">
                    {card.boundaries.proposes_only && <li>Proposes only — never applies changes itself</li>}
                    <li>External actions: {card.boundaries.external_actions}</li>
                    {card.boundaries.requires_human_approval_for.map((item) => (
                      <li key={item}>Human approval required: {item}</li>
                    ))}
                  </ul>
                  <p className="small mission-card__source">
                    {card.source_file} · v{card.card_version}
                    {card.model_routing ? ` · prompt ${card.model_routing.prompt}` : ''}
                  </p>
                </div>
              </details>
            </article>
          )
        })}
      </div>
    </section>
  )
}
