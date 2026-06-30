// P7A agentic intake response shapes (mirror the backend Pydantic models).
// Kept loose on optional fields so the UI never 500s on an older backend.

export type AgentMode =
  | 'gemini_live'
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

export interface BriefIntakeSourceMap {
  attendees?: RequirementSource
  budget_cap?: RequirementSource
  contingency_pct?: RequirementSource
  date?: RequirementSource
  event_type?: RequirementSource
  venue_type?: RequirementSource
  location?: RequirementSource
}

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

export interface ModelModeSummary {
  brief_intake?: string
  creative_concept?: string
  budget_manager?: string
  production_manager?: string
  vendor_coordinator?: string
  security?: string
}

export const MODE_LABEL: Record<AgentMode, string> = {
  gemini_live: 'Gemini live',
  rule_based_fallback: 'Rule-based fallback',
  deterministic_engine: 'Deterministic engine',
  scripted_fixture: 'Scripted fixture',
  human_approval_gate: 'Approval-gated',
  not_enabled: 'Not enabled',
}

export const MODE_CLASS: Record<AgentMode, string> = {
  gemini_live: 'badge--live',
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
