// P7A agentic intake response shapes (mirror the backend Pydantic models).
// Kept loose on optional fields so the UI never 500s on an older backend.

export type AgentMode =
  | 'gemini_live'
  | 'openai_compatible_live'
  | 'rule_based_fallback'
  | 'deterministic_engine'
  | 'scripted_fixture'
  | 'human_approval_gate'
  | 'not_enabled'

// P7D: requirement source tracking for provenance display
export type RequirementSource =
  | 'brief_extracted'
  | 'manual_override'
  | 'fallback_default'
  | 'missing'

export type CasefileSource =
  | 'user_field'
  | 'saved_casefile'
  | 'brief_extracted'
  | 'missing'
  | 'demo_seed'

export type CasefileNoticeType = 'missing' | 'conflict' | 'info'

export interface EventBasics {
  working_title: string
  country: string
  city: string
  currency: string
  budget_cap?: string | number | null
  start_date: string
  end_date: string
  expected_turnout?: number | null
  event_type: string
}

export interface CasefileNotice {
  type: CasefileNoticeType
  field: string
  message: string
  brief_value?: string | number | null
  casefile_value?: string | number | null
}

export interface ResolvedEventState {
  basics: EventBasics
  sources: Record<string, CasefileSource>
  notices: CasefileNotice[]
  confirmed: boolean
}

export type RequirementFieldStatus = 'ok' | 'missing' | 'conflict'

export interface RequirementField {
  key: string
  label: string
  value?: string | number | null
  source_label: string
  status: RequirementFieldStatus
}

export interface RequirementsPayload {
  confirmed: boolean
  confirmed_at?: string | null
  confirmed_by?: string | null
  fields: RequirementField[]
  missing: CasefileNotice[]
  conflicts: CasefileNotice[]
}

export interface NextStepAction {
  id: string
  label: string
  target: string
  kind: 'primary' | 'secondary'
  reason?: string
  disabled?: boolean
}

export interface NextBestStep {
  state: string
  primary: NextStepAction
  secondary: NextStepAction[]
  rationale?: string
}

export interface CasefileArtifact {
  name: string
  path: string
  updated_at: string
}

export interface CasefileState {
  event_id: string
  created_at: string
  updated_at: string
  basics: EventBasics
  brief: string
  resolved: ResolvedEventState
  status: 'draft' | 'generated' | 'requirements_confirmed'
  requirements_confirmed_at?: string | null
  requirements_confirmed_by?: string | null
  requirements?: RequirementsPayload | null
  next_step?: NextBestStep | null
  artifacts: Record<string, CasefileArtifact>
  planning_assumptions?: Record<string, unknown>
}

export interface CasefileSummary {
  event_id: string
  working_title: string
  country: string
  city: string
  start_date: string
  end_date: string
  expected_turnout?: number | null
  updated_at: string
  status: 'draft' | 'generated' | 'requirements_confirmed'
}

export type SpecialistAgentId =
  | 'creative_concept'
  | 'scope_strategy'
  | 'vendor_copy'
  | 'risk_review'

export interface SpecialistAgentRequest {
  instruction?: string
  regenerate?: boolean
  artifact_id?: string | null
}

export interface SpecialistAgentResponse {
  event_id: string
  agent_id: SpecialistAgentId
  artifact: CasefileArtifact
  output: Record<string, unknown>
  model_mode: AgentMode
  fallback_reason?: string | null
  notices?: CasefileNotice[]
  next_step?: NextBestStep | null
}

export interface BriefIntakeSourceMap {
  attendees?: RequirementSource
  budget_cap?: RequirementSource
  contingency_pct?: RequirementSource
  date?: RequirementSource
  event_type?: RequirementSource
  venue_type?: RequirementSource
  location?: RequirementSource
}

export interface ConstraintResolutionField {
  brief_value?: string | number | null
  manual_value?: string | number | null
  resolved_value?: string | number | null
  source?: RequirementSource
}

export type ConstraintResolution = Record<string, ConstraintResolutionField>

export interface AgentTraceStep {
  id: string
  role: string
  label: string
  status: 'complete' | 'warning' | 'blocked' | 'pending_approval' | 'error'
  input_summary: string
  output_summary: string
  artifacts: string[]
  deterministic_core: string | null
  approval_required: boolean
  model_mode?: AgentMode
  model_name?: string | null
  prompt_version?: string | null
  fallback_reason?: string | null
  confidence?: string | null
}

export interface BriefIntake {
  normalized_brief?: string
  event_type?: string
  event_type_raw?: string | null
  attendees?: number | null
  budget_cap?: string | null
  contingency_pct?: string | null
  venue_type?: string | null
  date?: string | null
  location?: string | null
  goals?: string[]
  audience_profile?: string | null
  tone?: string | null
  must_haves?: string[]
  nice_to_haves?: string[]
  constraints?: string[]
  assumptions?: string[]
  missing_questions?: string[]
  contradictions?: string[]
  market_realism_warnings?: string[]
  confidence?: string
  model_mode?: AgentMode
  fallback_reason?: string | null
  // P7D: source map for provenance display
  source_map?: BriefIntakeSourceMap
}

export interface CreativeIdea {
  title: string
  description: string
  tier: 'must' | 'should' | 'could' | 'wow'
  estimated_complexity: 'low' | 'medium' | 'high'
  budget_pressure: 'low' | 'medium' | 'high'
  why_it_fits: string
}

export interface CreativeScopeSuggestion {
  title: string
  description: string
  category: string
  tier: 'must' | 'should' | 'could' | 'wow'
  estimated_cost?: string | null
  budget_pressure: 'low' | 'medium' | 'high'
  action_hint: 'add' | 'cut' | 'reduce' | 'reconsider'
  rationale: string
}

export interface CreativeConcept {
  event_title_options?: string[]
  concept_summary?: string
  experience_principles?: string[]
  creative_ideas?: CreativeIdea[]
  suggested_additions?: CreativeScopeSuggestion[]
  suggested_cuts_or_reductions?: CreativeScopeSuggestion[]
  budget_sensitive_notes?: string[]
  production_risks?: string[]
  sponsor_or_partner_hooks?: string[]
  model_mode?: AgentMode
}

export interface ScopeStrategyRecommendation {
  title: string
  recommendation_type: 'add' | 'cut' | 'reduce' | 'retier' | 'keep' | 'clarify'
  category: string
  tier: 'must' | 'should' | 'could' | 'wow'
  rationale: string
  budget_pressure: 'low' | 'medium' | 'high'
  operational_risk: 'low' | 'medium' | 'high'
  proposed_scope_item?: Record<string, unknown> | null
}

export interface ScopeStrategy {
  strategy_summary?: string
  must_have_logic?: string[]
  tradeoffs?: string[]
  recommendations?: ScopeStrategyRecommendation[]
  questions_for_user?: string[]
  model_mode?: AgentMode
  fallback_reason?: string | null
}

export interface VendorDraft {
  subject?: string
  body?: string
  ask_summary?: string
  required_vendor_response_fields?: string[]
  approval_diff?: string
  risk_notes?: string[]
  model_mode?: AgentMode
  fallback_reason?: string | null
  draft?: string
}

export interface VendorCopyDraft {
  subject: string
  body: string
  ask_summary: string
  required_vendor_response_fields: string[]
  risk_notes: string[]
  review_status: 'draft' | 'reviewed'
  generated_at?: string | null
  updated_at?: string | null
  source_agent: string
  model_mode?: AgentMode | null
  fallback_reason?: string | null
}

export interface VendorCopyArtifactResponse {
  event_id: string
  artifact?: CasefileArtifact | null
  draft: VendorCopyDraft
}

export interface ModelModeSummary {
  brief_intake?: string
  creative_concept?: string
  orchestrator?: string
  scope_strategy?: string
  budget_manager?: string
  production_manager?: string
  vendor_coordinator?: string
  vendor_draft?: string
  security?: string
}

export interface RuntimeModelTestResult {
  provider: string
  effective_mode: string
  model_name: string
  has_api_key: boolean
  ok: boolean
  latency_ms?: number | null
  http_status?: number | null
  response_shape_keys?: string[]
  response_preview?: string | null
  response_format_mode?: string | null
  repaired_schema?: boolean
  repaired_fields?: string[]
  error?: string | null
  fallback_reason?: string | null
  agent_name?: string | null
  prompt_version?: string | null
}

export const MODE_LABEL: Record<AgentMode, string> = {
  gemini_live: 'Gemini live',
  openai_compatible_live: 'OpenAI-compatible live',
  rule_based_fallback: 'Rule-based fallback',
  deterministic_engine: 'Deterministic engine',
  scripted_fixture: 'Scripted fixture',
  human_approval_gate: 'Approval-gated',
  not_enabled: 'Not enabled',
}

export const MODE_CLASS: Record<AgentMode, string> = {
  gemini_live: 'badge--live',
  openai_compatible_live: 'badge--live',
  rule_based_fallback: 'badge--fallback',
  deterministic_engine: 'badge--engine',
  scripted_fixture: 'badge--fixture',
  human_approval_gate: 'badge--approval',
  not_enabled: 'badge--muted',
}

// ---------------------------------------------------------------------------
// P7B — Proposal types (mirror backend schemas)
// ---------------------------------------------------------------------------

export interface ProposedAction {
  id: string
  type: 'add_scope_item' | 'update_scope_item' | 'delete_scope_item' |
        'retier_scope_item' | 'toggle_scope_item' | 'add_risk_flag' |
        'request_clarification' | 'create_approval'
  title: string
  rationale: string
  payload: Record<string, unknown>
  requires_confirmation: boolean
  requires_approval_gate: boolean
  model_mode?: AgentMode
  created_at?: string
}

export interface Proposal {
  id: string
  event_id: string
  source_agent?: string
  title: string
  rationale: string
  proposed_actions: ProposedAction[]
  status: 'pending' | 'applied' | 'dismissed'
  created_at?: string
  model_mode?: AgentMode
  fallback_reason?: string | null
}

export interface OrchestratorChatResponse {
  reply: string
  proposals: ProposedAction[]
  model_mode: AgentMode
  fallback_reason?: string | null
}

export interface RecomputeNotice {
  previous_headroom?: string
  current_headroom?: string
  schedule_status?: 'recomputed' | 'warning' | string
  message?: string
}
