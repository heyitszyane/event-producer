import { useEffect, useState, type FormEvent, type ChangeEvent, type KeyboardEvent } from 'react'
import Head from 'next/head'
import EventCommandHeader, { type FieldErrors } from '../components/EventCommandHeader'
import AgentCrewTrace from '../components/AgentCrewTrace'
import ApprovalInbox from '../components/ApprovalInbox'
import ScopeCard, { type ScopeItem } from '../components/ScopeCard'
import BudgetCard, { type BudgetSummary } from '../components/BudgetCard'
import RunOfShowCard, { type ScheduleResult, type CallSheetEntry } from '../components/RunOfShowCard'
import VendorNotebook from '../components/VendorNotebook'
import RiskCard, { type RiskFlag } from '../components/RiskCard'
import ChatPane from '../components/ChatPane'
import ExtractedRequirements from '../components/ExtractedRequirements'
import AgentMissionControl from '../components/AgentMissionControl'
import RequirementsConfirmation from '../components/RequirementsConfirmation'
import NextBestStep from '../components/NextBestStep'
import InfoHint from '../components/InfoHint'
import pkg from '../package.json'
import { ApiRequestError, apiFetch, getApiBase } from '../lib/api'
import {
  createCasefile,
  getCasefile,
  getRunSnapshot,
  getStorageInfo,
  listCasefiles,
  runCasefileFirstPass,
  seedCasefiles,
  updateCasefileBasics,
  updateCasefileBrief,
  type StorageInfo,
} from '../lib/casefiles'
import { humanizeValue } from '../lib/humanize'
import type {
  BriefIntake,
  CasefileState,
  CasefileSummary,
  ConstraintResolution,
  CreativeConcept as CreativeConceptData,
  EventBasics,
  ScopeStrategy as ScopeStrategyData,
  VendorDraft,
  ModelModeSummary,
  RuntimeModelTestResult,
  AgentTraceStep,
  ProposedAction,
  OrchestratorChatResponse,
  RecomputeNotice,
  ResolvedEventState,
  RequirementsPayload,
  NextBestStep as NextBestStepData,
  BookingDeadline,
} from '../types/agentic'

// Run-output vendor fixtures (suggestions only; the persistent records live
// in the Vendor Notebook casefile artifact).
interface Vendor {
  id: string
  name: string
  category: string
  contact_email: string
  contact_phone: string
  rating: string
  notes: string
  locked?: boolean
}

export interface RunEventResponse {
  event_id?: string
  status?: string
  model_mode_summary?: ModelModeSummary
  casefile?: CasefileState
  resolved_event_state?: ResolvedEventState
  requirements?: RequirementsPayload | null
  next_step?: NextBestStepData | null
  planning_assumptions?: Record<string, unknown>
  brief_intake?: BriefIntake | null
  creative_concept?: CreativeConceptData | null
  scope_strategy?: ScopeStrategyData | null
  vendor_draft?: VendorDraft | null
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
  booking_deadlines?: BookingDeadline[]
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
  constraint_resolution?: ConstraintResolution
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

const EMPTY_BASICS: EventBasics = {
  working_title: '',
  country: '',
  city: '',
  currency: 'USD',
  budget_cap: null,
  contingency_pct: null,
  start_date: '',
  end_date: '',
  expected_turnout: null,
  event_type: '',
}

const PRODUCER_PROMPTS = [
  'Flag unrealistic assumptions',
  'Suggest cuts to stay under budget',
  'Rebalance scope under budget',
  'Make this feel more premium',
  'Add low-cost networking mechanics',
  'Suggest vendor/service additions',
  'Make this more brand/photo-ready',
]

type SectionId =
  | 'overview'
  | 'brief'
  | 'ai-crew'
  | 'scope'
  | 'budget'
  | 'run-sheet'
  | 'approvals'
  | 'vendors'
  | 'risks'
  | 'audit'
  | 'settings'

const WAR_ROOM_SECTIONS: Array<{ id: SectionId; label: string; code: string }> = [
  { id: 'overview', label: 'Overview', code: '00' },
  { id: 'brief', label: 'Brief Intake', code: '01' },
  { id: 'ai-crew', label: 'AI Crew', code: '02' },
  { id: 'scope', label: 'Scope', code: '03' },
  { id: 'budget', label: 'Budget', code: '04' },
  { id: 'run-sheet', label: 'Run Sheet', code: '05' },
  { id: 'approvals', label: 'Approvals', code: '06' },
  { id: 'vendors', label: 'Vendors', code: '07' },
  { id: 'risks', label: 'Risks', code: '08' },
  { id: 'audit', label: 'Audit Log', code: '09' },
  { id: 'settings', label: 'Settings', code: '10' },
]

function normalizeEventTitleCandidate(value?: string | null): string | null {
  const cleaned = (value || '')
    .replace(/\s+/g, ' ')
    .replace(/^need\s+(a|an|the)\s+/i, '')
    .replace(/^planning\s+(a|an|the)\s+/i, '')
    .trim()

  if (!cleaned) return null

  const firstSentence = cleaned.split(/[.!?]/)[0]?.trim() || cleaned
  const capped = firstSentence.length > 68 ? `${firstSentence.slice(0, 65).trim()}...` : firstSentence
  return capped || null
}

function generateDisplayEventTitle(args: {
  manual?: string
  creativeOptions?: string[]
  eventSpecName?: string
  brief?: string
}): string {
  return (
    normalizeEventTitleCandidate(args.manual) ||
    normalizeEventTitleCandidate(args.creativeOptions?.[0]) ||
    normalizeEventTitleCandidate(args.eventSpecName) ||
    normalizeEventTitleCandidate(args.brief) ||
    'Untitled Event'
  )
}

function compactNumber(value: number): string {
  if (value >= 1000 && value % 1000 === 0) return `${value / 1000}k`
  if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}k`
  return value.toLocaleString()
}

function formatBudgetMeta(value?: string | number | null, brief?: string): string | null {
  if (value === undefined || value === null || value === '') return null
  const numeric = Number(String(value).replace(/[^0-9.]/g, ''))
  if (!Number.isFinite(numeric) || numeric <= 0) return String(value)
  return `${/sgd/i.test(brief || '') ? 'SGD ' : '$'}${compactNumber(numeric)}`
}

function displayMetaValue(value?: string | number | null): string | null {
  if (value === undefined || value === null || value === '') return null
  const text = String(value).trim()
  return text || null
}

// Money in the casefile's own currency (ISO code prefix, e.g. "SGD -650").
function formatMoney(currency: string | undefined, value: number): string {
  const code = (currency || 'USD').toUpperCase()
  const sign = value < 0 ? '-' : ''
  return `${sign}${code} ${Math.abs(value).toLocaleString()}`
}

function formatEventDate(value?: string | null): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toISOString().slice(0, 10)
}

function formatDateRange(start?: string | null, end?: string | null): string {
  if (start && end && start !== end) return `${start} to ${end}`
  return start || end || 'Not set'
}

// Where each saved artifact is viewable in the app.
const ARTIFACT_ROUTES: Record<string, SectionId> = {
  'brief-intake': 'brief',
  'creative-concept': 'ai-crew',
  'scope-strategy': 'ai-crew',
  'risk-review': 'ai-crew',
  'budget-summary': 'budget',
  'run-sheet': 'run-sheet',
  'vendor-copy': 'vendors',
  'vendor-notebook': 'vendors',
}

const ROUTE_META: Record<SectionId, { route: string; title: string; desc: string }> = {
  overview: {
    route: '00 / Event Overview',
    title: 'Event Overview',
    desc: 'A command summary for the current event casefile: state, budget, agents, approval wall, and route links.',
  },
  brief: {
    route: '01 / Brief Intake',
    title: 'Brief Intake',
    desc: 'Event Basics are saved first. Brief text can add context and surface conflicts.',
  },
  'ai-crew': {
    route: '02 / Agent Mission Control',
    title: 'Agent Mission Control',
    desc: 'Ask the AI Producer, then direct the crew: every card is a runtime-loaded skill contract with live status, saved output, and direct actions.',
  },
  scope: {
    route: '03 / Scope Configurator',
    title: 'Scope Configurator',
    desc: 'Editable scope ledger for rentals, services, vendors, tiering, quantities, and selected state.',
  },
  budget: {
    route: '04 / Deterministic Budget Ledger',
    title: 'Deterministic Budget Ledger',
    desc: 'Budget engine output, tier pressure, contingency, and selected-vs-requested feasibility.',
  },
  'run-sheet': {
    route: '05 / Run Sheet + CPM Timeline',
    title: 'Run Sheet + CPM Timeline',
    desc: 'Deterministic schedule, critical path, event anchors, and recompute warnings.',
  },
  approvals: {
    route: '06 / Structural Approval Wall',
    title: 'Structural Approval Wall',
    desc: 'Human-gated vendor-facing actions with plain-English diffs and no unapproved execution.',
  },
  vendors: {
    route: '07 / Vendor Notebook',
    title: 'Vendor Notebook',
    desc: 'Persistent per-vendor chase list: workflow and payment status, activity logs, and agent-drafted copy — review before external use.',
  },
  risks: {
    route: '08 / Risks, Gaps + Operational Checks',
    title: 'Risks, Gaps + Operational Checks',
    desc: 'Budget realism, missing vendors, permit checks, and lead-time warnings.',
  },
  audit: {
    route: '09 / Production Log + Technical Trace',
    title: 'Production Log + Technical Trace',
    desc: 'Read-only evidence route for trace, provenance, logs, and public-claim proof.',
  },
  settings: {
    route: '10 / Provider Settings',
    title: 'Provider Settings',
    desc: 'Configure Gemini, OpenRouter, LM Studio, or another local OpenAI-compatible model for this dev server.',
  },
}

type ProviderName = 'gemini' | 'openrouter' | 'openai_compatible' | 'local' | 'ollama' | 'lmstudio'

interface ModelSettings {
  provider: ProviderName
  live_enabled: boolean
  strict_live_model: boolean
  effective_mode: string
  model_name: string
  api_base_url?: string | null
  has_api_key: boolean
  request_timeout_seconds: number
  fallback_reason?: string | null
  env_path: string
  restart_required: boolean
}

const PROVIDER_OPTIONS: Array<{ value: ProviderName; label: string }> = [
  { value: 'gemini', label: 'Gemini' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'lmstudio', label: 'LM Studio' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'local', label: 'Local OpenAI-compatible' },
  { value: 'openai_compatible', label: 'Hosted OpenAI-compatible' },
]

function providerDefaults(provider: ProviderName): { modelName: string; apiBaseUrl: string } {
  if (provider === 'gemini') return { modelName: 'gemini-2.5-flash', apiBaseUrl: '' }
  if (provider === 'openrouter') return { modelName: 'google/gemini-2.5-flash', apiBaseUrl: '' }
  if (provider === 'ollama') return { modelName: 'qwen2.5-coder:latest', apiBaseUrl: 'http://127.0.0.1:11434/v1/chat/completions' }
  if (provider === 'lmstudio') return { modelName: 'qwen/qwen3.5-9b', apiBaseUrl: 'http://127.0.0.1:1234/v1/chat/completions' }
  return { modelName: 'qwen2.5-coder:latest', apiBaseUrl: 'http://127.0.0.1:1234/v1/chat/completions' }
}

function validateCasefileForm(basics: EventBasics, brief: string): { valid: boolean; errors: FieldErrors } {
  const errors: FieldErrors = {}

  if (!brief.trim()) {
    errors.brief = 'Brief is required'
  }

  if (basics.budget_cap !== null && basics.budget_cap !== undefined && String(basics.budget_cap).trim()) {
    const bc = parseFloat(String(basics.budget_cap))
    if (isNaN(bc) || bc <= 0) {
      errors.budgetCap = 'Must be a positive number'
    }
  }

  if (basics.contingency_pct !== null && basics.contingency_pct !== undefined && String(basics.contingency_pct).trim()) {
    const cp = parseFloat(String(basics.contingency_pct))
    if (isNaN(cp) || cp < 0 || cp > 100) {
      errors.contingencyPct = 'Must be between 0 and 100'
    }
  }

  if (basics.expected_turnout !== null && basics.expected_turnout !== undefined && basics.expected_turnout <= 0) {
    errors.expectedTurnout = 'Must be greater than 0'
  }

  if (basics.start_date) {
    const parsed = new Date(basics.start_date)
    if (isNaN(parsed.getTime())) {
      errors.startDate = 'Invalid date format'
    }
  }

  if (basics.end_date) {
    const parsed = new Date(basics.end_date)
    if (isNaN(parsed.getTime())) {
      errors.endDate = 'Invalid date format'
    }
  }

  return { valid: Object.keys(errors).length === 0, errors }
}

export default function Dashboard() {
  const [brief, setBrief] = useState('')
  const [basics, setBasics] = useState<EventBasics>(EMPTY_BASICS)
  const [activeCasefile, setActiveCasefile] = useState<CasefileState | null>(null)
  const [casefiles, setCasefiles] = useState<CasefileSummary[]>([])
  const [casefilesLoading, setCasefilesLoading] = useState(false)
  const [result, setResult] = useState<RunEventResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [hasRun, setHasRun] = useState(false)
  const [lastRunAt, setLastRunAt] = useState<Date | null>(null)
  // P7B — orchestrator chat state
  const [chatInput, setChatInput] = useState('')
  const [orchestratorProposals, setOrchestratorProposals] = useState<ProposedAction[]>([])
  // The producer console keeps a running transcript so each answer is logged
  // alongside the question that produced it, instead of replacing the last one.
  const [producerThread, setProducerThread] = useState<Array<{
    id: string
    prompt: string
    reply: string
    modelMode: string | null
    fallbackReason: string | null
  }>>([])
  const [chatModelMode, setChatModelMode] = useState<string | null>(null)
  const [selectedProducerPrompt, setSelectedProducerPrompt] = useState('')
  const [producerLoading, setProducerLoading] = useState(false)
  const [producerError, setProducerError] = useState<string | null>(null)
  const [recomputeNotice, setRecomputeNotice] = useState<RecomputeNotice | null>(null)
  const [activeSection, setActiveSection] = useState<SectionId>('overview')
  const [eventNameOverride, setEventNameOverride] = useState('')
  const [editingEventName, setEditingEventName] = useState(false)
  const [modelSettings, setModelSettings] = useState<ModelSettings | null>(null)
  const [settingsProvider, setSettingsProvider] = useState<ProviderName>('gemini')
  const [settingsModelName, setSettingsModelName] = useState('')
  const [settingsApiBaseUrl, setSettingsApiBaseUrl] = useState('')
  const [settingsApiKey, setSettingsApiKey] = useState('')
  const [settingsLiveEnabled, setSettingsLiveEnabled] = useState(true)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [providerTestResult, setProviderTestResult] = useState<RuntimeModelTestResult | null>(null)
  const [providerTesting, setProviderTesting] = useState(false)
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null)
  const [copiedCasefileId, setCopiedCasefileId] = useState(false)
  const [seeding, setSeeding] = useState(false)

  function formatApiError(err: unknown): string {
    if (err instanceof ApiRequestError && err.payload.code === 'LIVE_MODEL_PROVIDER_FAILED') {
      return [
        'Live provider failed in strict mode.',
        `Provider: ${err.payload.provider || 'unknown'}`,
        `Model: ${err.payload.model_name || 'unknown'}`,
        `Agent: ${err.payload.agent_name || 'unknown'}`,
        `Error: ${err.payload.message}`,
        'Use Settings -> Test provider to diagnose the configured provider.',
      ].join('\n')
    }
    if (err instanceof TypeError && err.message === 'Failed to fetch') {
      return (
        `Backend is unreachable at ${getApiBase()}. Start the backend on the same host/port, ` +
        `or set NEXT_PUBLIC_API_BASE_URL to the backend you are running.`
      )
    }
    return err instanceof Error ? err.message : String(err)
  }

  useEffect(() => {
    const hash = window.location.hash.replace('#', '') as SectionId
    if (WAR_ROOM_SECTIONS.some((section) => section.id === hash)) {
      setActiveSection(hash)
    }
  }, [])

  useEffect(() => {
    async function loadInitialModelSettings() {
      try {
        const res = await apiFetch('/settings/model')
        const data: ModelSettings = await res.json()
        setModelSettings(data)
        setSettingsProvider(data.provider)
        setSettingsModelName(data.model_name || providerDefaults(data.provider).modelName)
        setSettingsApiBaseUrl(data.api_base_url || providerDefaults(data.provider).apiBaseUrl)
        setSettingsLiveEnabled(data.live_enabled)
      } catch (err) {
        setSettingsError(err instanceof Error ? err.message : String(err))
      }
    }
    loadInitialModelSettings()
  }, [])

  useEffect(() => {
    async function loadSavedCasefiles() {
      setCasefilesLoading(true)
      try {
        const summaries = await listCasefiles()
        setCasefiles(summaries)
        // Resume the most recently updated casefile so a reload does not
        // land on an empty workspace.
        if (summaries.length > 0) {
          await selectCasefile(summaries[0].event_id)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setCasefilesLoading(false)
      }
    }
    loadSavedCasefiles()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    getStorageInfo().then(setStorageInfo).catch(() => setStorageInfo(null))
  }, [])

  async function refreshCasefiles() {
    setCasefilesLoading(true)
    try {
      setCasefiles(await listCasefiles())
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setCasefilesLoading(false)
    }
  }

  async function selectCasefile(eventId: string) {
    setError(null)
    try {
      const loaded = await getCasefile(eventId)
      setActiveCasefile(loaded)
      setBasics(loaded.basics)
      setBrief(loaded.brief)
      setEventNameOverride(loaded.resolved.basics.working_title)
      setRecomputeNotice(null)
      // Restore the last saved pipeline run so every route works after a
      // reload. A 404 just means this casefile has not been run yet.
      try {
        const snapshot: RunEventResponse = await getRunSnapshot(eventId)
        setResult(snapshot)
        setHasRun(true)
      } catch (snapshotErr) {
        if (snapshotErr instanceof ApiRequestError && snapshotErr.status === 404) {
          setResult(null)
          setHasRun(false)
        } else {
          throw snapshotErr
        }
      }
    } catch (err) {
      setError(formatApiError(err))
    }
  }

  function applyCasefileState(casefile: CasefileState) {
    setActiveCasefile(casefile)
    setBasics(casefile.basics)
    setResult((prev) => prev ? ({
      ...prev,
      event_id: casefile.event_id,
      casefile,
      resolved_event_state: casefile.resolved,
      requirements: casefile.requirements,
      next_step: casefile.next_step,
    }) : null)
    setEventNameOverride(casefile.resolved.basics.working_title)
    void refreshCasefiles()
  }

  function newCasefile() {
    setActiveCasefile(null)
    setBasics({ ...EMPTY_BASICS })
    setBrief('')
    setResult(null)
    setHasRun(false)
    setLastRunAt(null)
    setEventNameOverride('')
    setRecomputeNotice(null)
    navigate('brief')
  }

  // Materialize the committed demo casefiles (LA + Singapore) and open one so a
  // fresh clone has real reference events to explore.
  async function seedDemo() {
    setSeeding(true)
    setError(null)
    try {
      const data = await seedCasefiles()
      await refreshCasefiles()
      const firstId = data.seeded_ids[0]
      if (firstId) await selectCasefile(firstId)
      navigate('brief')
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setSeeding(false)
    }
  }

  // The event title is edited on the page hero and is the single source of
  // truth for the casefile's working title — persist it so it survives reload.
  async function commitEventName() {
    setEditingEventName(false)
    const trimmed = eventNameOverride.trim()
    setEventNameOverride(trimmed)
    // Patch only the title so any unsaved brief-form edits are preserved.
    setBasics((prev) => ({ ...prev, working_title: trimmed }))
    if (activeCasefile && trimmed && trimmed !== activeCasefile.basics.working_title) {
      try {
        const updated = await updateCasefileBasics(activeCasefile.event_id, {
          ...activeCasefile.basics,
          working_title: trimmed,
        })
        setActiveCasefile(updated)
        setResult((prev) => prev ? {
          ...prev,
          event_id: updated.event_id,
          casefile: updated,
          resolved_event_state: updated.resolved,
          requirements: updated.requirements,
          next_step: updated.next_step,
        } : prev)
        void refreshCasefiles()
      } catch (err) {
        setError(formatApiError(err))
      }
    }
  }

  function applyModelSettings(data: ModelSettings) {
    setModelSettings(data)
    setSettingsProvider(data.provider)
    setSettingsModelName(data.model_name || providerDefaults(data.provider).modelName)
    setSettingsApiBaseUrl(data.api_base_url || providerDefaults(data.provider).apiBaseUrl)
    setSettingsLiveEnabled(data.live_enabled)
  }

  async function loadModelSettings() {
    const res = await apiFetch('/settings/model')
    const data: ModelSettings = await res.json()
    applyModelSettings(data)
  }

  function handleProviderChange(nextProvider: ProviderName) {
    const defaults = providerDefaults(nextProvider)
    setSettingsProvider(nextProvider)
    setSettingsModelName(defaults.modelName)
    setSettingsApiBaseUrl(defaults.apiBaseUrl)
    setSettingsMessage(null)
    setSettingsError(null)
  }

  async function saveModelSettings(e: FormEvent) {
    e.preventDefault()
    setSettingsSaving(true)
    setSettingsMessage(null)
    setSettingsError(null)
    try {
      const res = await apiFetch('/settings/model', {
        method: 'POST',
        body: JSON.stringify({
          provider: settingsProvider,
          model_name: settingsModelName.trim(),
          api_base_url: settingsApiBaseUrl.trim(),
          api_key: settingsApiKey.trim() ? settingsApiKey.trim() : null,
          live_enabled: settingsLiveEnabled,
        }),
      })
      const data: ModelSettings = await res.json()
      applyModelSettings(data)
      setSettingsApiKey('')
      setSettingsMessage(`Saved to ${data.env_path} and applied to the running backend — no restart needed.`)
      setProviderTestResult(null)
    } catch (err) {
      setSettingsError(formatApiError(err))
    } finally {
      setSettingsSaving(false)
    }
  }

  async function testProvider() {
    setProviderTesting(true)
    setSettingsMessage(null)
    setSettingsError(null)
    try {
      const res = await apiFetch('/runtime/model/test', {
        method: 'POST',
        body: JSON.stringify({}),
      })
      const data: RuntimeModelTestResult = await res.json()
      setProviderTestResult(data)
      if (data.ok) {
        setSettingsMessage('Provider test succeeded.')
      } else {
        setSettingsError(data.error || data.fallback_reason || 'Provider test failed.')
      }
    } catch (err) {
      setSettingsError(formatApiError(err))
    } finally {
      setProviderTesting(false)
    }
  }

  function navigate(section: SectionId) {
    setActiveSection(section)
    // One-shot mutation feedback should not linger across sections.
    setRecomputeNotice(null)
    window.history.replaceState(null, '', `#${section}`)
  }

  async function handleRun(e: FormEvent) {
    e.preventDefault()

    const normalizedBasics: EventBasics = {
      ...basics,
      budget_cap: basics.budget_cap === '' ? null : basics.budget_cap,
      contingency_pct: basics.contingency_pct === '' ? null : basics.contingency_pct,
      expected_turnout: basics.expected_turnout === undefined ? null : basics.expected_turnout,
      end_date: basics.end_date || basics.start_date,
    }
    const { valid, errors } = validateCasefileForm(normalizedBasics, brief)
    if (!valid) {
      setFieldErrors(errors)
      return
    }

    setFieldErrors({})
    setLoading(true)
    setError(null)

    try {
      let saved = activeCasefile
      if (saved) {
        saved = await updateCasefileBasics(saved.event_id, normalizedBasics)
        saved = await updateCasefileBrief(saved.event_id, brief)
      } else {
        saved = await createCasefile({ basics: normalizedBasics, brief })
      }
      setActiveCasefile(saved)
      setBasics(saved.basics)
      const data: RunEventResponse = await runCasefileFirstPass(saved.event_id)
      setResult(data)
      if (data.casefile) {
        setActiveCasefile(data.casefile)
        setBasics(data.casefile.basics)
        setEventNameOverride(data.casefile.resolved.basics.working_title)
      }
      setHasRun(true)
      setLastRunAt(new Date())
      setRecomputeNotice(null)
      await refreshCasefiles()
    } catch (err) {
      setError(formatApiError(err))
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
  const resolvedState = result?.resolved_event_state || activeCasefile?.resolved || null
  const resolvedBasics = resolvedState?.basics || basics
  const requirements = activeCasefile?.requirements || result?.requirements || null
  const nextStep = activeCasefile?.next_step || result?.next_step || null
  const casefileArtifacts = Object.values(activeCasefile?.artifacts || result?.casefile?.artifacts || {})
  // run-snapshot is an internal restore artifact, not a user-facing output.
  const visibleArtifacts = casefileArtifacts.filter((artifact) => artifact.name !== 'run-snapshot')
  const turnoutLabel = resolvedBasics.expected_turnout ? `${resolvedBasics.expected_turnout} pax` : 'Expected turnout not set'
  const attendeeSource = resolvedState?.sources?.expected_turnout || result?.constraint_resolution?.attendees?.source

  // Hero strip budget health
  const budgetSummary = result?.budget_summary
  const scheduleResult = result?.schedule_result
  const criticalCount = scheduleResult?.critical_path?.length || 0
  const pendingApprovalCount = approvals.filter((a) => a.status === 'pending').length
  const activeMeta = ROUTE_META[activeSection]
  const headroomNumber = budgetSummary?.headroom ? Number(budgetSummary.headroom) : null
  const sourceLabel = attendeeSource === 'brief_extracted' ? 'turnout from brief' : attendeeSource ? `source: ${humanizeValue(String(attendeeSource))}` : 'awaiting casefile'

  // P7B — orchestrator chat handler
  async function sendProducerPrompt(message: string) {
    if (!result?.event_id || !message.trim()) return

    setProducerLoading(true)
    setProducerError(null)
    try {
      const res = await apiFetch(`/event/${result.event_id}/chat`, {
        method: 'POST',
        body: JSON.stringify({ message }),
      })
      const data: OrchestratorChatResponse = await res.json()
      setProducerThread((prev) => [
        ...prev,
        {
          id: `${Date.now()}`,
          prompt: message,
          reply: data.reply,
          modelMode: data.model_mode,
          fallbackReason: data.fallback_reason || null,
        },
      ])
      setOrchestratorProposals(data.proposals)
      setChatModelMode(data.model_mode)
      setChatInput('')
      setSelectedProducerPrompt('')
    } catch (err) {
      setProducerError(formatApiError(err))
    } finally {
      setProducerLoading(false)
    }
  }

  async function handleOrchestratorChat(e: FormEvent) {
    e.preventDefault()
    await sendProducerPrompt(chatInput)
  }

  function applyMutationPayload(data: {
    scope_items?: ScopeItem[]
    budget_summary?: BudgetSummary
    schedule_result?: ScheduleResult | null
    call_sheet?: CallSheetEntry[]
    recompute_notice?: RecomputeNotice
  }) {
    setResult((prev) => prev ? ({
      ...prev,
      scope_items: data.scope_items ?? prev.scope_items,
      budget_summary: data.budget_summary ?? prev.budget_summary,
      schedule_result: data.schedule_result ?? prev.schedule_result,
      call_sheet: data.call_sheet ?? prev.call_sheet,
    }) : prev)
    if (data.recompute_notice) setRecomputeNotice(data.recompute_notice)
  }

  // P7B — apply a proposal
  async function applyProposal(proposal: ProposedAction) {
    if (!result?.event_id) return
    setProducerError(null)
    try {
      const res = await apiFetch(`/event/${result.event_id}/proposals/${proposal.id}/apply`, {
        method: 'POST',
      })
      const data = await res.json()
      applyMutationPayload(data)
      setOrchestratorProposals((prev) => prev.filter((p) => p.id !== proposal.id))
    } catch (err) {
      setProducerError(formatApiError(err))
    }
  }

  async function dismissProposal(proposal: ProposedAction) {
    if (!result?.event_id) return
    setProducerError(null)
    try {
      await apiFetch(`/event/${result.event_id}/proposals/${proposal.id}/dismiss`, {
        method: 'POST',
      })
      setOrchestratorProposals((prev) => prev.filter((p) => p.id !== proposal.id))
    } catch (err) {
      setProducerError(formatApiError(err))
    }
  }

  // P7B — handle creative suggestion → add to scope. Returns whether the item
  // was added so the card can show real "Added" feedback instead of theatre.
  async function handleAddToScope(suggestion: {
    title: string
    description: string
    category: string
    estimated_cost?: string | null
    tier?: string
  }): Promise<boolean> {
    if (!result?.event_id) return false
    // The estimated cost from the creative agent may arrive as "$500" or
    // "500 SGD"; keep only the number and fall back to a modest default.
    const parsed = Number(String(suggestion.estimated_cost ?? '').replace(/[^0-9.]/g, ''))
    const cost = Number.isFinite(parsed) && parsed > 0 ? String(parsed) : '500'
    setProducerError(null)
    try {
      const res = await apiFetch(`/event/${result.event_id}/scope-items`, {
        method: 'POST',
        body: JSON.stringify({
          name: suggestion.title,
          description: suggestion.description,
          category: suggestion.category,
          tier: (suggestion.tier as 'must' | 'should' | 'could' | 'wow') || 'could',
          estimated_cost: cost,
          currency: resolvedBasics.currency,
          qty: '1',
        }),
      })
      const data = await res.json()
      applyMutationPayload(data)
      return true
    } catch (err) {
      setProducerError(formatApiError(err))
      return false
    }
  }

  const realismWarnings = result?.brief_intake?.market_realism_warnings ?? []
  const hasRealismRisk = realismWarnings.length > 0
  const eventState = budgetSummary?.over_budget ? 'OVER BUDGET' : hasRealismRisk ? 'AT RISK' : result ? 'ON TRACK' : 'AWAITING BRIEF'
  const eventTitle = generateDisplayEventTitle({
    manual: eventNameOverride,
    creativeOptions: result?.creative_concept?.event_title_options,
    eventSpecName: resolvedBasics.working_title || result?.event_spec?.name,
    brief,
  })
  const headerTitle = eventTitle
  const eventMetaSegments = [
    [resolvedBasics.city, resolvedBasics.country].filter(Boolean).join(', ') || null,
    turnoutLabel,
    formatBudgetMeta(resolvedBasics.budget_cap ?? result?.budget_summary?.budget_cap, resolvedBasics.currency),
    resolvedBasics.event_type ? humanizeValue(resolvedBasics.event_type) : null,
    formatEventDate(resolvedBasics.start_date || null),
  ].filter((segment): segment is string => Boolean(segment))
  const producerModeLabel = chatModelMode ? humanizeValue(chatModelMode) : 'Awaiting question'
  const producerModeClass = chatModelMode?.includes('live') ? 'badge--live' : chatModelMode ? 'badge--fallback' : 'badge--muted'
  const degradedSteps = agentTrace.filter((step) => step.fallback_reason)
  const liveAgentCount = Object.values(result?.model_mode_summary || {}).filter((mode) => String(mode).includes('live')).length
  const hasLiveRuntime = liveAgentCount > 0
  const compactRuntimeLabel = result
    ? hasLiveRuntime
      ? `Live - ${liveAgentCount} agent${liveAgentCount === 1 ? '' : 's'}`
      : 'Fallback mode'
    : 'Awaiting run'
  const lastRunLabel = lastRunAt?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const producerConsole = result ? (
    <section className="war-panel producer-console" id="orchestrator-chat">
      <div className="war-panel__header">
        <div>
          <span className="war-eyebrow">Producer actions</span>
          <h2>
            Ask the AI Producer{' '}
            <InfoHint text="The orchestrator reads the saved casefile and returns typed proposals — nothing is applied until you confirm it, and vendor or payment intents also require the approval gate." />
          </h2>
        </div>
        <div className="cluster">
          <span className={`badge ${producerModeClass}`}>{producerModeLabel}</span>
          <span className="badge badge--info">{orchestratorProposals.length} proposal{orchestratorProposals.length === 1 ? '' : 's'}</span>
        </div>
      </div>
      {producerThread.length > 0 && (
        <div className="producer-thread" aria-live="polite">
          {producerThread.map((turn) => (
            <div key={turn.id} className="producer-turn">
              <div className="producer-turn__msg producer-turn__msg--user">
                <span className="producer-turn__who">You</span>
                <p>{turn.prompt}</p>
              </div>
              <div className="producer-turn__msg producer-turn__msg--agent">
                <span className="producer-turn__who">AI Producer</span>
                <p>{turn.reply}</p>
                {turn.fallbackReason && (
                  <span className="producer-turn__note">Degraded fallback: {turn.fallbackReason}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <form onSubmit={handleOrchestratorChat} className="ai-producer-form">
        <textarea
          value={chatInput}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setChatInput(e.target.value)}
          placeholder="Ask for cuts, premium swaps, vendor additions, or assumption checks"
          disabled={!result?.event_id || producerLoading}
          rows={3}
          className="ai-producer-textarea"
        />
        <button type="submit" disabled={!result?.event_id || producerLoading || !chatInput.trim()} className="btn btn--primary">
          {producerLoading ? 'Thinking...' : 'Ask'}
        </button>
      </form>
      <div className="producer-prompt-tools">
        <label className="producer-prompt-select">
          <span>Sample prompt</span>
          <select
            value={selectedProducerPrompt}
            onChange={(e) => setSelectedProducerPrompt(e.target.value)}
            disabled={producerLoading}
          >
            <option value="">Choose a sample prompt...</option>
            {PRODUCER_PROMPTS.map((prompt) => (
              <option key={prompt} value={prompt}>{prompt}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => sendProducerPrompt(selectedProducerPrompt)}
          disabled={!selectedProducerPrompt || producerLoading}
        >
          Run sample
        </button>
      </div>
      {producerError && (
        <div className="error-bar" role="alert" aria-live="polite">
          {producerError}
        </div>
      )}
      {orchestratorProposals.length > 0 && (
        <div className="proposal-ledger">
          {orchestratorProposals.map((p) => (
            <div key={p.id} className="war-inset">
              <div className="war-inset__topline">
                <strong>{p.title}</strong>
                <span className="badge badge--info">{String(p.payload?.tier || p.type)}</span>
              </div>
              <p>{p.rationale}</p>
              {p.payload?.estimated_cost !== undefined && p.payload?.estimated_cost !== null && (
                <p className="muted">Budget impact: {resolvedBasics.currency} {String(p.payload.estimated_cost)}</p>
              )}
              <div className="cluster">
                {p.requires_approval_gate && <span className="badge badge--approval">approval gate</span>}
                <button onClick={() => applyProposal(p)} className="btn btn--primary btn--sm" type="button" disabled={p.requires_approval_gate}>
                  {p.requires_approval_gate ? 'Approval required' : 'Apply'}
                </button>
                <button onClick={() => dismissProposal(p)} className="btn btn--ghost btn--sm" type="button">Dismiss</button>
              </div>
            </div>
          ))}
        </div>
      )}
      {recomputeNotice?.message && (
        <div className={recomputeNotice.schedule_status === 'warning' ? 'block block--warn' : 'block block--info'}>
          {recomputeNotice.message}
        </div>
      )}
    </section>
  ) : null

  // Shared props that turn a metric tile into a keyboard-accessible link to
  // the route where that number can actually be acted on.
  function metricNav(section: SectionId, hint: string) {
    return {
      role: 'button' as const,
      tabIndex: 0,
      className: 'war-metric--link',
      title: hint,
      onClick: () => navigate(section),
      onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(section)
        }
      },
    }
  }

  const contingencyDetail = budgetSummary
    ? `${Number(budgetSummary.contingency_pct)}% contingency ${resolvedBasics.currency} ${Number(budgetSummary.contingency_reserve).toLocaleString()}`
    : null

  function navigateToTarget(target: string) {
    if (WAR_ROOM_SECTIONS.some((section) => section.id === target)) {
      navigate(target as SectionId)
    }
  }

  function renderActiveSection() {
    if (loading) {
      return (
        <div className="pipeline-loading" role="status" aria-live="polite">
          <div className="loading-spinner" />
          <p>Running event production pipeline...</p>
        </div>
      )
    }

    if (!result && activeSection !== 'brief' && activeSection !== 'overview' && activeSection !== 'ai-crew' && activeSection !== 'vendors' && activeSection !== 'settings') {
      return (
        <section className="war-panel empty-state">
          <p>Start with Brief Intake, then run the AI production crew to populate the war room.</p>
        </section>
      )
    }

    switch (activeSection) {
      case 'overview':
        return (
          <div className="war-overview-grid">
            <div className="war-stack">
              <section className="war-panel overview-panel">
                <div className="war-panel__header">
                  <div>
                    <span className="war-eyebrow">Current event</span>
                    <h2>{eventTitle} <InfoHint text={ROUTE_META.overview.desc} /></h2>
                  </div>
                  <span className={requirements?.confirmed ? 'badge badge--ok' : 'badge badge--info'}>
                    {requirements?.confirmed ? 'Requirements confirmed' : 'Requirements open'}
                  </span>
                </div>
                <div className="overview-fact-grid">
                  <div><span>Location</span><strong>{[resolvedBasics.city, resolvedBasics.country].filter(Boolean).join(', ') || 'Not set'}</strong></div>
                  <div><span>Budget cap</span><strong>{resolvedBasics.budget_cap ? `${resolvedBasics.currency} ${Number(resolvedBasics.budget_cap).toLocaleString()}` : 'Not set'}</strong></div>
                  <div><span>Date</span><strong>{formatDateRange(resolvedBasics.start_date, resolvedBasics.end_date)}</strong></div>
                  <div><span>Expected turnout</span><strong>{turnoutLabel}</strong></div>
                  <div><span>Event type</span><strong>{resolvedBasics.event_type ? humanizeValue(resolvedBasics.event_type) : 'Not set'}</strong></div>
                  <div><span>Brief</span><strong>{brief.trim() ? 'Saved' : 'Not saved'}</strong></div>
                </div>
              </section>
              <NextBestStep nextStep={nextStep} onNavigate={navigateToTarget} />
            </div>
            <div className="war-stack">
              <section className="war-panel">
                <div className="war-panel__header">
                  <span className="war-panel-title">
                    Saved casefile artifacts{' '}
                    <InfoHint text="Every agent output is saved to the casefile as a named artifact. Click one to open the route where it lives." />
                  </span>
                  <span className="badge badge--info">{visibleArtifacts.length} saved</span>
                </div>
                {visibleArtifacts.length > 0 ? (
                  <ul className="artifact-list">
                    {visibleArtifacts.map((artifact) => (
                      <li key={artifact.name}>
                        <button
                          type="button"
                          className="artifact-list__link"
                          onClick={() => navigateToTarget(ARTIFACT_ROUTES[artifact.name] || 'overview')}
                        >
                          {humanizeValue(artifact.name)}
                        </button>
                        <span>{new Date(artifact.updated_at).toLocaleString()}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="body-copy">Run the production crew to save concept, scope, budget, schedule, and vendor draft artifacts.</p>
                )}
                {activeCasefile && (
                  <div className="artifact-storage-hint">
                    <span>Saved to this casefile.</span>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(activeCasefile.event_id)
                          setCopiedCasefileId(true)
                          setTimeout(() => setCopiedCasefileId(false), 2000)
                        } catch {
                          setError('Copy is unavailable in this browser.')
                        }
                      }}
                    >
                      {copiedCasefileId ? 'Copied' : 'Copy casefile ID'}
                    </button>
                  </div>
                )}
              </section>
            </div>
          </div>
        )
      case 'brief':
        return (
          <div className="war-stack">
            <EventCommandHeader
              basics={basics}
              brief={brief}
              onBasicsChange={setBasics}
              onBriefChange={setBrief}
              fieldErrors={fieldErrors}
              onRun={handleRun}
              loading={loading}
              hasCasefile={Boolean(activeCasefile)}
            />
            <RequirementsConfirmation
              casefile={activeCasefile}
              onCasefileChange={applyCasefileState}
              onError={setError}
            />
          </div>
        )
      case 'ai-crew':
        return (
          <div className="war-stack">
            {producerConsole}
            {!result && (
              <section className="war-panel empty-state">
                <p>
                  The producer console unlocks after the first pass. You can still task the
                  specialists below directly against the saved casefile.
                </p>
              </section>
            )}
            <AgentMissionControl
              casefile={activeCasefile}
              trace={agentTrace}
              modelModeSummary={result?.model_mode_summary}
              creativeConcept={result?.creative_concept ?? null}
              scopeStrategy={result?.scope_strategy ?? null}
              onCasefileChange={applyCasefileState}
              onError={setError}
              onNavigate={navigateToTarget}
              onAddToScope={handleAddToScope}
            />
          </div>
        )
      case 'scope':
        return (
          <div className="war-stack">
            <ScopeCard
              items={result?.scope_items || []}
              eventId={result?.event_id}
              budget={result?.budget_summary || null}
              currency={resolvedBasics.currency}
              onMutation={applyMutationPayload}
            />
          </div>
        )
      case 'budget':
        return <BudgetCard budget={result?.budget_summary || null} warnings={realismWarnings} currency={resolvedBasics.currency} />
      case 'run-sheet':
        return (
          <RunOfShowCard
            schedule={result?.schedule_result}
            callSheet={result?.call_sheet || []}
            bookingDeadlines={result?.booking_deadlines || []}
          />
        )
      case 'approvals':
        return (
          <div className="war-stack">
            <ApprovalInbox
              approvals={approvals}
              eventId={result?.event_id}
              defaultExpanded
              vendorDraft={result?.vendor_draft ?? null}
            />
          </div>
        )
      case 'vendors':
        return (
          <div className="war-stack">
            <VendorNotebook
              casefile={activeCasefile}
              suggestedVendors={vendors}
              onCasefileChange={applyCasefileState}
              onError={setError}
            />
          </div>
        )
      case 'risks':
        return (
          <div className="war-stack">
            <RiskCard risks={riskFlags} />
            {realismWarnings.length > 0 && (
              <section className="war-panel">
                <div className="war-panel__header"><h2>Budget Realism Risks</h2></div>
                <ul className="bullets">{realismWarnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
              </section>
            )}
          </div>
        )
      case 'audit':
        return (
          <div className="war-stack">
            <section className="war-panel production-log">
              <div className="production-log-header">
                <span>Production Log</span>
                <span>{chatLog.length} entries</span>
              </div>
              <ChatPane messages={chatLog} showHeader={false} />
            </section>
            <ExtractedRequirements intake={result?.brief_intake ?? null} resolution={result?.constraint_resolution} />
            <AgentCrewTrace steps={agentTrace} />
          </div>
        )
      case 'settings':
        return (
          <div className="settings-grid">
            <section className="war-panel settings-panel">
              <div className="war-panel__header">
                <div>
                  <span className="war-eyebrow">Model harness</span>
                  <h2>Provider Settings</h2>
                </div>
                <span className={`badge ${modelSettings?.effective_mode === 'rule_based_fallback' ? 'badge--fallback' : 'badge--live'}`}>
                  {modelSettings ? humanizeValue(modelSettings.effective_mode) : 'loading'}
                </span>
              </div>
              <form className="settings-form" onSubmit={saveModelSettings}>
                <label className="field-compact">
                  Provider
                  <select
                    className="select"
                    value={settingsProvider}
                    onChange={(e) => handleProviderChange(e.target.value as ProviderName)}
                  >
                    {PROVIDER_OPTIONS.map((provider) => (
                      <option key={provider.value} value={provider.value}>{provider.label}</option>
                    ))}
                  </select>
                </label>
                <label className="field-compact">
                  Model
                  <input
                    className="input"
                    value={settingsModelName}
                    onChange={(e) => setSettingsModelName(e.target.value)}
                    placeholder={providerDefaults(settingsProvider).modelName}
                  />
                </label>
                {settingsProvider !== 'gemini' && settingsProvider !== 'openrouter' && (
                  <label className="field-compact settings-form__wide">
                    Base URL
                    <input
                      className="input"
                      value={settingsApiBaseUrl}
                      onChange={(e) => setSettingsApiBaseUrl(e.target.value)}
                      placeholder={providerDefaults(settingsProvider).apiBaseUrl}
                    />
                  </label>
                )}
                <label className="field-compact settings-form__wide">
                  API key
                  <input
                    className="input"
                    type="password"
                    value={settingsApiKey}
                    onChange={(e) => setSettingsApiKey(e.target.value)}
                    placeholder={modelSettings?.has_api_key ? 'Existing key loaded - leave blank to keep it' : 'Paste key if this provider requires one'}
                    autoComplete="off"
                  />
                </label>
                <label className="field-compact field-compact--checkbox settings-form__wide">
                  <input
                    type="checkbox"
                    checked={settingsLiveEnabled}
                    onChange={(e) => setSettingsLiveEnabled(e.target.checked)}
                  />
                  Enable live model calls
                </label>
                <div className="settings-actions settings-form__wide">
                  <button className="btn btn--primary" type="submit" disabled={settingsSaving}>
                    {settingsSaving ? 'Saving...' : 'Save Provider'}
                  </button>
                  <button className="btn btn--ghost" type="button" onClick={() => loadModelSettings()} disabled={settingsSaving}>
                    Refresh Status
                  </button>
                  <button className="btn btn--ghost" type="button" onClick={testProvider} disabled={settingsSaving || providerTesting}>
                    {providerTesting ? 'Testing...' : 'Test provider'}
                  </button>
                </div>
              </form>
              {settingsMessage && <div className="callout callout--success">{settingsMessage}</div>}
              {settingsError && <div className="error-bar" role="alert">{settingsError}</div>}
              {providerTestResult && (
                <div className={providerTestResult.ok ? 'provider-test provider-test--ok' : 'provider-test provider-test--fail'}>
                  <div className="provider-test__header">
                    <strong>{providerTestResult.ok ? 'Provider reachable' : 'Provider test failed'}</strong>
                    <span className={`badge ${providerTestResult.ok ? 'badge--live' : 'badge--fallback'}`}>
                      {providerTestResult.ok ? 'success' : 'failure'}
                    </span>
                  </div>
                  <table className="data-table settings-table">
                    <tbody>
                      <tr><th>Provider</th><td>{humanizeValue(providerTestResult.provider)}</td></tr>
                      <tr><th>Model</th><td>{providerTestResult.model_name || '-'}</td></tr>
                      <tr><th>Effective mode</th><td>{humanizeValue(providerTestResult.effective_mode)}</td></tr>
                      <tr><th>Response format</th><td>{humanizeValue(providerTestResult.response_format_mode || '-')}</td></tr>
                      <tr><th>Schema repair</th><td>{providerTestResult.repaired_schema ? `Applied: ${(providerTestResult.repaired_fields || []).join(', ') || 'field shape'}` : 'Not applied'}</td></tr>
                      <tr><th>Latency</th><td>{providerTestResult.latency_ms !== null && providerTestResult.latency_ms !== undefined ? `${providerTestResult.latency_ms} ms` : '-'}</td></tr>
                      <tr><th>HTTP</th><td>{providerTestResult.http_status || '-'}</td></tr>
                      <tr><th>Key loaded</th><td>{providerTestResult.has_api_key ? 'Yes' : 'No'}</td></tr>
                      {!providerTestResult.ok && <tr><th>Error</th><td>{providerTestResult.error || providerTestResult.fallback_reason || '-'}</td></tr>}
                    </tbody>
                  </table>
                  {providerTestResult.response_preview && (
                    <pre className="diff-block provider-test__preview">{providerTestResult.response_preview}</pre>
                  )}
                </div>
              )}
            </section>
            <div className="war-stack">
              <section className="war-panel settings-panel">
                <div className="war-panel__header">
                  <span className="war-panel-title">Current Backend Runtime</span>
                  <span className={`badge ${modelSettings?.has_api_key ? 'badge--ok' : 'badge--fallback'}`}>
                    {modelSettings?.has_api_key ? 'key loaded from .env' : 'no key loaded'}
                  </span>
                </div>
                <table className="data-table settings-table">
                  <tbody>
                    <tr><th>Provider</th><td>{modelSettings?.provider || '-'}</td></tr>
                    <tr><th>Live calls</th><td>{modelSettings?.live_enabled ? 'Enabled' : 'Disabled'}</td></tr>
                    <tr><th>Mode</th><td>{modelSettings ? humanizeValue(modelSettings.effective_mode) : '-'}</td></tr>
                    <tr><th>Model</th><td>{modelSettings?.model_name || '-'}</td></tr>
                    <tr><th>Base URL</th><td>{modelSettings?.api_base_url || '-'}</td></tr>
                    <tr><th>.env</th><td>{modelSettings?.env_path || '-'}</td></tr>
                  </tbody>
                </table>
                {modelSettings?.fallback_reason && (
                  <div className="callout callout--warning">{modelSettings.fallback_reason}</div>
                )}
              </section>
              <section className="war-panel settings-panel">
                <div className="war-panel__header">
                  <span className="war-panel-title">Local Data</span>
                  <span className="badge badge--info">local demo storage</span>
                </div>
                <table className="data-table settings-table">
                  <tbody>
                    <tr><th>Casefile root</th><td>{storageInfo?.root || '-'}</td></tr>
                    <tr><th>Saved casefiles</th><td>{storageInfo?.casefile_count ?? '-'}</td></tr>
                    <tr><th>Active casefile ID</th><td>{activeCasefile?.event_id || '-'}</td></tr>
                  </tbody>
                </table>
                <p className="body-copy">
                  Casefiles and artifacts are JSON files on this machine — not a cloud
                  database. Delete a casefile folder under the root above to remove it.
                </p>
              </section>
            </div>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <>
      <Head>
        <title>Event Producer — Paper War Room</title>
        <meta name="description" content="AI production crew for brand/experiential events" />
      </Head>

      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="war-room">
        <aside className="war-room__nav" aria-label="Paper War Room sections">
          <div className="war-room__brand">
            <strong>Event<br />Producer</strong>
            <small>Your AI production crew</small>
            <small className="war-room__version">v{pkg.version}</small>
          </div>
          <div className="nav-status-card" aria-label="Current casefile status">
            <strong>{eventState}</strong>
            <span>{compactRuntimeLabel}</span>
            <small>{hasRun && lastRunLabel ? `Last run ${lastRunLabel}` : 'No run yet'}</small>
          </div>
          <div className="casefile-switcher" aria-label="Saved casefiles">
            <div className="casefile-switcher__header">
              <span className="side-section-title">Casefile</span>
              <button type="button" className="btn btn--ghost btn--sm" onClick={newCasefile}>New</button>
            </div>
            {casefilesLoading && <small className="casefile-switcher__hint">Loading casefiles...</small>}
            {!casefilesLoading && casefiles.length === 0 && (
              <small className="casefile-switcher__hint">No saved casefiles yet</small>
            )}
            {casefiles.length > 0 && (
              <select
                className="casefile-switcher__select"
                aria-label="Switch casefile"
                value={activeCasefile?.event_id || ''}
                onChange={(e) => {
                  if (e.target.value) void selectCasefile(e.target.value)
                }}
              >
                {!activeCasefile && <option value="">Select a casefile...</option>}
                {casefiles.map((casefile) => (
                  <option key={casefile.event_id} value={casefile.event_id}>
                    {(casefile.working_title || 'Untitled Event')
                      + (casefile.start_date ? ` — ${casefile.start_date}` : '')}
                  </option>
                ))}
              </select>
            )}
            {activeCasefile && (
              <small className="casefile-switcher__hint">
                {[
                  activeCasefile.resolved.basics.city,
                  activeCasefile.resolved.basics.expected_turnout
                    ? `${activeCasefile.resolved.basics.expected_turnout} pax`
                    : null,
                ].filter(Boolean).join(' · ') || activeCasefile.status}
              </small>
            )}
          </div>
          <div className="side-section-title">Route Map</div>
          <nav>
            {WAR_ROOM_SECTIONS.map((section) => (
              <button
                key={section.id}
                type="button"
                className={activeSection === section.id ? 'war-nav-item war-nav-item--active' : 'war-nav-item'}
                onClick={() => navigate(section.id)}
              >
                <span>{section.code}</span>
                {section.label}
              </button>
            ))}
          </nav>
        </aside>

        <main className="war-room__main" id="main-content">
          <header className="war-room__header">
            <div>
              <span className="war-eyebrow">{activeMeta.route}</span>
              {editingEventName ? (
                <input
                  className="event-title-input"
                  value={eventNameOverride}
                  autoFocus
                  onChange={(e) => setEventNameOverride(e.target.value)}
                  onBlur={() => void commitEventName()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void commitEventName()
                    if (e.key === 'Escape') {
                      setEventNameOverride(activeCasefile?.basics.working_title || '')
                      setEditingEventName(false)
                    }
                  }}
                  aria-label="Edit event name"
                />
              ) : (
                <button
                  className="event-title-button"
                  type="button"
                  onClick={() => {
                    setEventNameOverride((prev) => prev || eventTitle)
                    setEditingEventName(true)
                  }}
                >
                  {headerTitle}
                </button>
              )}
              {eventMetaSegments.length > 0 && (
                <div className="event-title-meta">{eventMetaSegments.join(' - ')}</div>
              )}
              <p>{activeMeta.desc}</p>
            </div>
            <div className="top-actions">
              <button className="btn btn--primary" type="button" onClick={newCasefile}>New Event</button>
              <button className="btn btn--ghost" type="button" onClick={seedDemo} disabled={seeding}>
                {seeding ? 'Seeding...' : 'Seed Demo'}
              </button>
            </div>
          </header>

          <section className="war-metrics" aria-label="Top metrics">
            <div {...(budgetSummary ? metricNav('budget', 'Open the Budget ledger') : {})}>
              <label>Budget Headroom</label>
              <span className={budgetSummary?.over_budget ? 'metric-value--red' : 'metric-value--green'}>
                {headroomNumber !== null ? formatMoney(resolvedBasics.currency, headroomNumber) : '-'}
              </span>
              <small>
                {budgetSummary
                  ? `${budgetSummary.over_budget ? 'over cap' : 'computed'}${contingencyDetail ? ` · ${contingencyDetail}` : ''}`
                  : 'awaiting run'}
              </small>
            </div>
            <div>
              <label>Production Status</label>
              <span className={eventState === 'ON TRACK' ? 'metric-value--green' : eventState === 'AT RISK' ? 'metric-value--gold' : 'metric-value--red'}>{eventState}</span>
              <small>{result ? 'current casefile' : 'no event yet'}</small>
            </div>
            <div {...(scheduleResult ? metricNav('run-sheet', 'Open the Run Sheet') : {})}>
              <label>Schedule Tasks</label>
              <span>{scheduleResult?.ordered_tasks?.length || 0}</span>
              <small>{criticalCount} on critical path</small>
            </div>
            <div {...(pendingApprovalCount > 0 ? metricNav('approvals', 'Open the Approval wall') : {})}>
              <label>Approvals</label>
              <span className={pendingApprovalCount > 0 ? 'metric-value--red' : 'metric-value--green'}>{pendingApprovalCount}</span>
              <small>pending wall</small>
            </div>
            <div>
              <label>Expected Turnout</label>
              <span>{resolvedBasics.expected_turnout ?? '-'}</span>
              <small>{sourceLabel}</small>
            </div>
          </section>

          {error && (
            <div className="error-bar" role="alert">
              <span>{error.includes('Live provider failed') || error.includes('unreachable') ? error : `Error: ${error}`}</span>
              <button onClick={() => setError(null)} className="dismiss-btn" aria-label="Dismiss error">x</button>
            </div>
          )}

          {degradedSteps.length > 0 && (
            <div className="callout callout--warning runtime-degraded" role="status">
              Degraded mode: {degradedSteps[0].role} used fallback because {degradedSteps[0].fallback_reason}.
            </div>
          )}

          <div className="war-room__content">
            {renderActiveSection()}
          </div>
        </main>
      </div>
    </>
  )
}
