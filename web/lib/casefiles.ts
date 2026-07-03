import { apiFetch } from './api'
import type { CasefileState, CasefileSummary, EventBasics } from '../types/agentic'

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

export async function runCasefileFirstPass(eventId: string) {
  const res = await apiFetch('/run', {
    method: 'POST',
    body: JSON.stringify({ casefile_id: eventId }),
  })
  return res.json()
}

