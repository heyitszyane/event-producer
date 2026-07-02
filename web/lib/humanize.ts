export const LABELS: Record<string, string> = {
  av_equipment: 'AV Equipment',
  food_beverage: 'Food & Beverage',
  networking: 'Networking Event',
  budget_cap: 'Budget Cap',
  contingency_pct: 'Contingency',
  event_type: 'Event Type',
  attendees: 'Attendees',
  venue_type: 'Venue Type',
  indoor: 'Indoor',
  outdoor: 'Outdoor',
  product_launch: 'Product Launch',
  must: 'Essential',
  should: 'Recommended',
  could: 'Optional',
  wow: 'Stretch',
  send_vendor_message: 'Send vendor message',
  change_payment_details: 'Change payment details',
  mark_paid: 'Mark invoice as paid',
  reschedule: 'Change schedule',
  change_scope: 'Change scope',
  approve_budget: 'Approve budget',
  lock_scope: 'Lock scope',
  release_funds: 'Release funds',
  payment_change: 'Payment detail change',
  scripted_vendor_message: 'Scripted vendor message',
  brief_extracted: 'From brief',
  manual_override: 'Manual override',
  fallback_default: 'Fallback default',
  missing: 'Missing',
  gemini_live: 'Gemini live',
  openai_compatible_live: 'OpenAI-compatible live',
  rule_based_fallback: 'Rule-based fallback',
  deterministic_engine: 'Deterministic engine',
  human_approval_gate: 'Human approval gate',
  scripted_fixture: 'Scripted fixture',
  confidence_high: '',
  confidence_medium: '',
  confidence_low: '',
}

export function humanizeKey(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return ''
  const raw = String(value).trim()
  if (!raw) return ''
  const known = LABELS[raw]
  if (known !== undefined) return known
  return raw
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function humanizeValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return ''
  const raw = String(value).trim()
  if (!raw) return ''
  return LABELS[raw] ?? raw.replace(/_/g, ' ')
}

export function displayLabel(value: string | number | null | undefined): string {
  return humanizeKey(value)
}

export function humanizeSummary(value: string): string {
  return value
    .replace(/\bconfidence_(?:high|medium|low)\b/gi, '')
    .replace(/\b(?:missing|contradictions)=\d+\b/gi, '')
    .replace(/\b([a-z][a-z0-9_]+)=([^\s,;]+)/gi, (_match, key: string, val: string) => {
      const label = humanizeKey(key)
      const humanValue = humanizeValue(val)
      if (!label || !humanValue) return ''
      return `${label}: ${humanValue}`
    })
    .replace(/\s+([,;.])/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[,;.\s]+|[,;.\s]+$/g, '')
}
