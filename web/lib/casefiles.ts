import { apiFetch } from './api'
import type {
  CasefileState,
  CasefileSummary,
  EventBasics,
  NextBestStep,
  SpecialistAgentId,
  SpecialistAgentRequest,
  SpecialistAgentResponse,
  VendorCopyArtifactResponse,
  VendorCopyDraft,
  VendorDraftRecord,
  VendorListResponse,
  VendorLogEntry,
  VendorRecord,
} from '../types/agentic'

export async function createCasefile(payload: {
  basics: EventBasics
  brief: string
}): Promise<CasefileState> {
  const res = await apiFetch('/casefiles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function listCasefiles(): Promise<CasefileSummary[]> {
  const res = await apiFetch('/casefiles')
  return res.json()
}

export interface SeedCasefilesResult {
  seeded_ids: string[]
  casefiles: CasefileSummary[]
}

// Materialize the two committed demo casefiles (idempotent). Fresh clones use
// this to get reference events without hand-entering a brief.
export async function seedCasefiles(): Promise<SeedCasefilesResult> {
  const res = await apiFetch('/casefiles/seed', { method: 'POST' })
  return res.json()
}

export async function getCasefile(eventId: string): Promise<CasefileState> {
  const res = await apiFetch(`/casefiles/${eventId}`)
  return res.json()
}

export async function updateCasefileBasics(
  eventId: string,
  basics: EventBasics,
): Promise<CasefileState> {
  const res = await apiFetch(`/casefiles/${eventId}/basics`, {
    method: 'PATCH',
    body: JSON.stringify(basics),
  })
  return res.json()
}

export async function updateCasefileBrief(
  eventId: string,
  brief: string,
): Promise<CasefileState> {
  const res = await apiFetch(`/casefiles/${eventId}/brief`, {
    method: 'PUT',
    body: JSON.stringify({ brief }),
  })
  return res.json()
}

export async function confirmCasefileRequirements(eventId: string): Promise<CasefileState> {
  const res = await apiFetch(`/casefiles/${eventId}/requirements/confirm`, {
    method: 'POST',
  })
  return res.json()
}

export async function getCasefileNextStep(eventId: string): Promise<NextBestStep> {
  const res = await apiFetch(`/casefiles/${eventId}/next-step`)
  return res.json()
}

export async function runCasefileFirstPass(eventId: string) {
  const res = await apiFetch('/run', {
    method: 'POST',
    body: JSON.stringify({ casefile_id: eventId }),
  })
  return res.json()
}

// P7N — restore the last saved pipeline run for a casefile (404 => never run).
export async function getRunSnapshot(eventId: string) {
  const res = await apiFetch(`/casefiles/${eventId}/run-snapshot`)
  return res.json()
}

export interface CasefileArtifactPayload {
  event_id: string
  name: string
  payload: Record<string, unknown>
}

export async function getCasefileArtifact(
  eventId: string,
  name: string,
): Promise<CasefileArtifactPayload> {
  const res = await apiFetch(`/casefiles/${eventId}/artifacts/${name}`)
  return res.json()
}

export interface StorageInfo {
  root: string
  casefile_count: number
  storage_kind: string
}

export async function getStorageInfo(): Promise<StorageInfo> {
  const res = await apiFetch('/settings/storage')
  return res.json()
}

export async function runSpecialistAgent(
  eventId: string,
  agentId: SpecialistAgentId,
  payload: SpecialistAgentRequest,
): Promise<SpecialistAgentResponse> {
  const res = await apiFetch(`/casefiles/${eventId}/agents/${agentId}/run`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function getVendorCopyDraft(eventId: string): Promise<VendorCopyArtifactResponse> {
  const res = await apiFetch(`/casefiles/${eventId}/artifacts/vendor-copy`)
  return res.json()
}

export async function saveVendorCopyDraft(
  eventId: string,
  draft: VendorCopyDraft,
): Promise<VendorCopyArtifactResponse> {
  const res = await apiFetch(`/casefiles/${eventId}/artifacts/vendor-copy`, {
    method: 'PUT',
    body: JSON.stringify(draft),
  })
  return res.json()
}

// ---------------------------------------------------------------------------
// P7P — Vendor Notebook helpers (planning metadata only; nothing sends).
// ---------------------------------------------------------------------------

export async function listVendors(eventId: string): Promise<VendorListResponse> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors`)
  return res.json()
}

export async function createVendor(
  eventId: string,
  payload: { name: string; category: string; contact_name?: string; contact_email?: string; contact_phone?: string; website?: string; notes?: string },
): Promise<VendorRecord> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function updateVendor(
  eventId: string,
  vendorId: string,
  updates: Partial<VendorRecord>,
): Promise<VendorRecord> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors/${vendorId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
  return res.json()
}

export async function deleteVendor(eventId: string, vendorId: string): Promise<void> {
  await apiFetch(`/casefiles/${eventId}/vendors/${vendorId}`, { method: 'DELETE' })
}

export async function appendVendorLog(
  eventId: string,
  vendorId: string,
  payload: { body: string; title?: string; type?: 'note' | 'vendor_response_logged' },
): Promise<VendorLogEntry> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors/${vendorId}/log`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function saveVendorDraft(
  eventId: string,
  vendorId: string,
  draft: Partial<VendorDraftRecord>,
): Promise<VendorRecord> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors/${vendorId}/draft`, {
    method: 'PUT',
    body: JSON.stringify(draft),
  })
  return res.json()
}

export async function markVendorDraftCopied(eventId: string, vendorId: string): Promise<VendorRecord> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors/${vendorId}/draft/mark-copied`, {
    method: 'POST',
  })
  return res.json()
}

export async function markVendorDraftManuallySent(eventId: string, vendorId: string): Promise<VendorRecord> {
  const res = await apiFetch(`/casefiles/${eventId}/vendors/${vendorId}/draft/mark-manually-sent`, {
    method: 'POST',
  })
  return res.json()
}
