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
