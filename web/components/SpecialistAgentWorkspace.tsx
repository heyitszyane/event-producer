import { useMemo, useState } from 'react'
import { getCasefile, runSpecialistAgent } from '../lib/casefiles'
import type {
  AgentMode,
  CasefileArtifact,
  CasefileState,
  SpecialistAgentId,
  SpecialistAgentResponse,
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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function modeLabel(mode?: AgentMode | null): string {
  return mode ? MODE_LABEL[mode] : 'Not run'
}

function updatedLabel(artifact?: CasefileArtifact): string {
  if (!artifact) return 'Not run'
  return `Saved ${new Date(artifact.updated_at).toLocaleString()}`
}

function latestSummary(config: AgentConfig, artifact?: CasefileArtifact, response?: SpecialistAgentResponse): string {
  const payload = asRecord(response?.output)
  const output = asRecord(payload.output)
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

function ArtifactPreview({ config, response }: { config: AgentConfig; response?: SpecialistAgentResponse }) {
  if (!response) return null
  const payload = asRecord(response.output)
  const output = asRecord(payload.output)

  if (config.id === 'creative_concept') {
    const titles = asArray(output.event_title_options).map(String).slice(0, 3)
    const ideas = asArray(output.creative_ideas).map(asRecord).slice(0, 3)
    return (
      <div className="specialist-preview">
        {asText(output.concept_summary) && <p>{asText(output.concept_summary)}</p>}
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
    return (
      <div className="specialist-preview">
        {asText(output.strategy_summary) && <p>{asText(output.strategy_summary)}</p>}
        {recommendations.length > 0 && (
          <ul className="compact-list">
            {recommendations.map((rec) => (
              <li key={asText(rec.title)}>{asText(rec.title)} - {asText(rec.rationale)}</li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  if (config.id === 'vendor_copy') {
    return (
      <div className="specialist-preview specialist-preview--draft">
        {asText(output.subject) && <p><strong>{asText(output.subject)}</strong></p>}
        {asText(output.body) && <pre>{asText(output.body)}</pre>}
        {asText(output.ask_summary) && <p>{asText(output.ask_summary)}</p>}
      </div>
    )
  }

  const flags = asArray(output.risk_flags).map(asRecord)
  const actions = asArray(output.recommended_next_actions).map(String)
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
  const [responses, setResponses] = useState<Partial<Record<SpecialistAgentId, SpecialistAgentResponse>>>({})

  const artifactMap = useMemo(() => casefile?.artifacts || {}, [casefile?.artifacts])

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
      setResponses((current) => ({ ...current, [config.id]: response }))
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
          const response = responses[config.id]
          const mode = response?.model_mode
          const isRunning = running === config.id
          return (
            <article className="specialist-card" key={config.id}>
              <div className="specialist-card__top">
                <div>
                  <h3>{config.title}</h3>
                  <p>{latestSummary(config, artifact, response)}</p>
                </div>
                <span className={`badge ${mode ? MODE_CLASS[mode] ?? 'badge--muted' : 'badge--muted'}`}>
                  {modeLabel(mode)}
                </span>
              </div>

              <div className="specialist-card__meta">
                <span>{updatedLabel(artifact)}</span>
                {response?.fallback_reason && <span>Fallback: {response.fallback_reason}</span>}
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

              <ArtifactPreview config={config} response={response} />
            </article>
          )
        })}
      </div>
    </section>
  )
}
