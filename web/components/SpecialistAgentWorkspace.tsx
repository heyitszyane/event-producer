import { useEffect, useMemo, useState } from 'react'
import { getCasefile, getCasefileArtifact, runSpecialistAgent } from '../lib/casefiles'
import type {
  AgentMode,
  CasefileArtifact,
  CasefileState,
  SpecialistAgentId,
} from '../types/agentic'
import { MODE_CLASS, MODE_LABEL } from '../types/agentic'

interface SpecialistAgentWorkspaceProps {
  casefile: CasefileState | null
  onCasefileChange: (casefile: CasefileState) => void
  onError: (message: string) => void
}

interface AgentConfig {
  id: SpecialistAgentId
  artifactName: string
  title: string
  actionLabel: string
  placeholder: string
}

const AGENTS: AgentConfig[] = [
  {
    id: 'creative_concept',
    artifactName: 'creative-concept',
    title: 'Creative Concept Agent',
    actionLabel: 'Ask this agent',
    placeholder: 'Generate three more concepts that feel premium but stay budget-conscious.',
  },
  {
    id: 'scope_strategy',
    artifactName: 'scope-strategy',
    title: 'Scope Strategy Agent',
    actionLabel: 'Ask this agent',
    placeholder: 'Cut this down to fit SGD 10k without losing the core networking goal.',
  },
  {
    id: 'vendor_copy',
    artifactName: 'vendor-copy',
    title: 'Vendor Copy Agent',
    actionLabel: 'Draft vendor copy',
    placeholder: 'Draft a short venue inquiry I can copy to vendors.',
  },
  {
    id: 'risk_review',
    artifactName: 'risk-review',
    title: 'Risk Review Agent',
    actionLabel: 'Run risk review',
    placeholder: 'Check what is missing before I contact vendors.',
  },
]

// Artifact payload shape shared by live responses and saved artifacts:
// { output: {...}, model_mode, fallback_reason, generated_at, ... }
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

function modeOf(payload?: AgentPayload): AgentMode | null {
  const mode = payload?.model_mode
  return typeof mode === 'string' && mode in MODE_LABEL ? mode as AgentMode : null
}

function updatedLabel(artifact?: CasefileArtifact): string {
  if (!artifact) return 'Not run yet'
  return `Saved ${new Date(artifact.updated_at).toLocaleString()}`
}

function latestSummary(config: AgentConfig, artifact?: CasefileArtifact, payload?: AgentPayload): string {
  const output = asRecord(payload?.output)
  if (config.id === 'creative_concept') {
    return asText(output.concept_summary) || (artifact ? 'Creative artifact saved.' : 'No concept saved yet.')
  }
  if (config.id === 'scope_strategy') {
    return asText(output.strategy_summary) || (artifact ? 'Scope strategy artifact saved.' : 'No strategy saved yet.')
  }
  if (config.id === 'vendor_copy') {
    return asText(output.ask_summary) || asText(output.subject) || (artifact ? 'Vendor copy artifact saved.' : 'No draft saved yet.')
  }
  const actions = asArray(output.recommended_next_actions)
  return asText(actions[0]) || (artifact ? 'Risk review artifact saved.' : 'No review saved yet.')
}

// Detail preview beneath each card. The one-line summary already renders in
// the card header, so it is intentionally not repeated here.
function ArtifactPreview({ config, payload }: { config: AgentConfig; payload?: AgentPayload }) {
  if (!payload) return null
  const output = asRecord(payload.output)

  if (config.id === 'creative_concept') {
    const titles = asArray(output.event_title_options).map(String).slice(0, 3)
    const ideas = asArray(output.creative_ideas).map(asRecord).slice(0, 3)
    if (titles.length === 0 && ideas.length === 0) return null
    return (
      <div className="specialist-preview">
        {titles.length > 0 && <p><strong>Titles:</strong> {titles.join(', ')}</p>}
        {ideas.length > 0 && (
          <ul className="compact-list">
            {ideas.map((idea) => <li key={asText(idea.title)}>{asText(idea.title)} - {asText(idea.description)}</li>)}
          </ul>
        )}
      </div>
    )
  }

  if (config.id === 'scope_strategy') {
    const recommendations = asArray(output.recommendations).map(asRecord).slice(0, 4)
    const tradeoffs = asArray(output.tradeoffs).map(String).slice(0, 2)
    if (recommendations.length === 0 && tradeoffs.length === 0) return null
    return (
      <div className="specialist-preview">
        {recommendations.length > 0 && (
          <ul className="compact-list">
            {recommendations.map((rec) => (
              <li key={asText(rec.title)}>{asText(rec.title)} - {asText(rec.rationale)}</li>
            ))}
          </ul>
        )}
        {tradeoffs.length > 0 && <p><strong>Tradeoffs:</strong> {tradeoffs.join(' ')}</p>}
      </div>
    )
  }

  if (config.id === 'vendor_copy') {
    if (!asText(output.subject) && !asText(output.body)) return null
    return (
      <div className="specialist-preview specialist-preview--draft">
        {asText(output.subject) && <p><strong>{asText(output.subject)}</strong></p>}
        {asText(output.body) && <pre>{asText(output.body)}</pre>}
      </div>
    )
  }

  const flags = asArray(output.risk_flags).map(asRecord)
  const actions = asArray(output.recommended_next_actions).map(String)
  if (flags.length === 0 && actions.length === 0) return null
  return (
    <div className="specialist-preview">
      {flags.length > 0 && (
        <ul className="compact-list">
          {flags.slice(0, 5).map((flag) => (
            <li key={`${asText(flag.category)}-${asText(flag.message)}`}>{asText(flag.category)}: {asText(flag.message)}</li>
          ))}
        </ul>
      )}
      {actions.length > 0 && <p><strong>Next:</strong> {actions[0]}</p>}
    </div>
  )
}

export default function SpecialistAgentWorkspace({
  casefile,
  onCasefileChange,
  onError,
}: SpecialistAgentWorkspaceProps) {
  const [instructions, setInstructions] = useState<Record<SpecialistAgentId, string>>({
    creative_concept: '',
    scope_strategy: '',
    vendor_copy: '',
    risk_review: '',
  })
  const [running, setRunning] = useState<SpecialistAgentId | null>(null)
  const [payloads, setPayloads] = useState<Partial<Record<SpecialistAgentId, AgentPayload>>>({})

  const artifactMap = useMemo(() => casefile?.artifacts || {}, [casefile?.artifacts])
  const eventId = casefile?.event_id

  // Load saved artifact payloads so previous agent output is visible after a
  // reload, not only within the session that generated it.
  useEffect(() => {
    if (!eventId) {
      setPayloads({})
      return
    }
    let cancelled = false
    async function loadSaved() {
      const next: Partial<Record<SpecialistAgentId, AgentPayload>> = {}
      await Promise.all(AGENTS.map(async (config) => {
        if (!artifactMap[config.artifactName]) return
        try {
          const artifact = await getCasefileArtifact(eventId as string, config.artifactName)
          next[config.id] = asRecord(artifact.payload)
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
  }, [eventId, artifactMap])

  async function handleRun(config: AgentConfig, regenerate: boolean) {
    if (!casefile) return
    setRunning(config.id)
    onError('')
    try {
      const response = await runSpecialistAgent(casefile.event_id, config.id, {
        instruction: instructions[config.id],
        regenerate,
        artifact_id: artifactMap[config.artifactName]?.name || null,
      })
      setPayloads((current) => ({ ...current, [config.id]: asRecord(response.output) }))
      const refreshed = await getCasefile(casefile.event_id)
      onCasefileChange(refreshed)
    } catch (err) {
      onError(err instanceof Error ? err.message : `Could not run ${config.title}.`)
    } finally {
      setRunning(null)
    }
  }

  return (
    <section className="card specialist-workspace" aria-labelledby="specialist-workspace-heading">
      <div className="card__header">
        <div>
          <span className="war-eyebrow">Direct specialist actions</span>
          <h2 id="specialist-workspace-heading">Specialist Agent Workspace</h2>
        </div>
        <span className={casefile ? 'badge badge--ok' : 'badge badge--muted'}>
          {casefile ? 'Saved casefile loaded' : 'Save a casefile first'}
        </span>
      </div>

      <div className="specialist-grid">
        {AGENTS.map((config) => {
          const artifact = artifactMap[config.artifactName]
          const payload = payloads[config.id]
          const mode = modeOf(payload)
          const fallbackReason = asText(payload?.fallback_reason)
          const isRunning = running === config.id
          return (
            <article className="specialist-card" key={config.id}>
              <div className="specialist-card__top">
                <div>
                  <h3>{config.title}</h3>
                  <p>{latestSummary(config, artifact, payload)}</p>
                </div>
                <span className={`badge ${mode ? MODE_CLASS[mode] ?? 'badge--muted' : 'badge--muted'}`}>
                  {mode ? MODE_LABEL[mode] : artifact ? 'Saved' : 'Not run'}
                </span>
              </div>

              <div className="specialist-card__meta">
                <span>{updatedLabel(artifact)}</span>
                {fallbackReason && <span>Fallback: {fallbackReason}</span>}
              </div>

              <textarea
                className="textarea specialist-card__input"
                value={instructions[config.id]}
                onChange={(event) => setInstructions((current) => ({ ...current, [config.id]: event.target.value }))}
                placeholder={config.placeholder}
                disabled={!casefile || isRunning}
              />

              <div className="specialist-card__actions">
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={!casefile || isRunning}
                  onClick={() => handleRun(config, false)}
                >
                  {isRunning ? 'Running...' : config.actionLabel}
                </button>
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  disabled={!casefile || isRunning || !artifact}
                  onClick={() => handleRun(config, true)}
                >
                  Refine
                </button>
              </div>

              <ArtifactPreview config={config} payload={payload} />
            </article>
          )
        })}
      </div>
    </section>
  )
}
