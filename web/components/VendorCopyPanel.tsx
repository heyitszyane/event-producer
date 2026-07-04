import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import {
  getCasefile,
  getVendorCopyDraft,
  runSpecialistAgent,
  saveVendorCopyDraft,
} from '../lib/casefiles'
import type { CasefileState, VendorCopyDraft } from '../types/agentic'
import { MODE_CLASS, MODE_LABEL } from '../types/agentic'

interface VendorCopyPanelProps {
  casefile: CasefileState | null
  onCasefileChange: (casefile: CasefileState) => void
  onError: (message: string) => void
}

const EMPTY_DRAFT: VendorCopyDraft = {
  subject: '',
  body: '',
  ask_summary: '',
  required_vendor_response_fields: [],
  risk_notes: [],
  review_status: 'draft',
  generated_at: null,
  updated_at: null,
  source_agent: 'vendor_copy',
  model_mode: null,
  fallback_reason: null,
}

const PROMPT_CHIPS = [
  'Make shorter',
  'More formal',
  'More casual',
  'Ask for itemized quote',
  'Ask about minimum spend',
  'Mention 100 pax and SGD 10k cap',
]

function formatTimestamp(value?: string | null): string {
  if (!value) return 'Not saved yet'
  return new Date(value).toLocaleString()
}

function copyTextFor(draft: VendorCopyDraft): string {
  return `Subject: ${draft.subject.trim()}\n\n${draft.body.trim()}`.trim()
}

export default function VendorCopyPanel({
  casefile,
  onCasefileChange,
  onError,
}: VendorCopyPanelProps) {
  const [draft, setDraft] = useState<VendorCopyDraft>(EMPTY_DRAFT)
  const [hasArtifact, setHasArtifact] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [status, setStatus] = useState('')

  const modeBadge = useMemo(() => {
    if (!draft.model_mode) return null
    return (
      <span className={`badge ${MODE_CLASS[draft.model_mode] ?? 'badge--muted'}`}>
        {MODE_LABEL[draft.model_mode]}
      </span>
    )
  }, [draft.model_mode])

  useEffect(() => {
    let cancelled = false
    async function loadDraft() {
      if (!casefile) {
        setDraft(EMPTY_DRAFT)
        setHasArtifact(false)
        setDirty(false)
        return
      }
      setLoading(true)
      setStatus('')
      try {
        const response = await getVendorCopyDraft(casefile.event_id)
        if (cancelled) return
        setDraft(response.draft)
        setHasArtifact(Boolean(response.artifact))
        setDirty(false)
      } catch (err) {
        if (!cancelled) onError(err instanceof Error ? err.message : 'Could not load vendor copy draft.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadDraft()
    return () => {
      cancelled = true
    }
  }, [casefile?.event_id, casefile, onError])

  function updateDraft(field: keyof VendorCopyDraft, value: string) {
    setDraft((current) => ({ ...current, [field]: value }))
    setDirty(true)
    setStatus('')
  }

  async function refreshCasefile() {
    if (!casefile) return
    const refreshed = await getCasefile(casefile.event_id)
    onCasefileChange(refreshed)
  }

  async function saveDraft() {
    if (!casefile) return
    setSaving(true)
    onError('')
    setStatus('')
    try {
      const response = await saveVendorCopyDraft(casefile.event_id, draft)
      setDraft(response.draft)
      setHasArtifact(Boolean(response.artifact))
      setDirty(false)
      setStatus('Draft saved.')
      await refreshCasefile()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Could not save vendor copy draft.')
    } finally {
      setSaving(false)
    }
  }

  async function copyDraft() {
    const text = copyTextFor(draft)
    if (!text) {
      setStatus('Nothing to copy yet.')
      return
    }
    if (!navigator.clipboard?.writeText) {
      setStatus('Copy is unavailable in this browser; select the text manually.')
      return
    }
    try {
      await navigator.clipboard.writeText(text)
      setStatus('Draft copied. Review it before using it externally.')
    } catch {
      setStatus('Copy is unavailable in this browser; select the text manually.')
    }
  }

  async function runVendorCopyAgent(regenerate: boolean) {
    if (!casefile) return
    if (dirty && !window.confirm('You have unsaved edits. Discard them and refresh the draft?')) {
      return
    }
    setRunning(true)
    onError('')
    setStatus('')
    try {
      await runSpecialistAgent(casefile.event_id, 'vendor_copy', {
        instruction,
        regenerate,
        artifact_id: 'vendor-copy',
      })
      const response = await getVendorCopyDraft(casefile.event_id)
      setDraft(response.draft)
      setHasArtifact(Boolean(response.artifact))
      setDirty(false)
      setStatus(regenerate ? 'Draft refreshed.' : 'Draft prepared.')
      await refreshCasefile()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Could not refresh vendor copy draft.')
    } finally {
      setRunning(false)
    }
  }

  function handleTextChange(field: keyof VendorCopyDraft) {
    return (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      updateDraft(field, event.target.value)
    }
  }

  const disabled = !casefile || loading || saving || running

  return (
    <section className="card vendor-copy-panel" aria-labelledby="vendor-copy-heading">
      <div className="card__header">
        <div>
          <span className="war-eyebrow">Review before external use</span>
          <h2 id="vendor-copy-heading">Vendor Copy</h2>
        </div>
        <div className="cluster">
          {modeBadge}
          <span className={dirty ? 'badge badge--warn' : 'badge badge--ok'}>
            {dirty ? 'Unsaved edits' : 'Saved state'}
          </span>
        </div>
      </div>

      <div className="block block--info">
        Event Producer prepares drafts only. Review, edit, save, and copy the text for external use.
      </div>

      {!casefile && (
        <div className="empty-state">Save or load a casefile before preparing vendor copy.</div>
      )}

      {casefile && !hasArtifact && !loading && (
        <div className="empty-state">
          No vendor draft yet. Ask the Vendor Copy Agent to prepare one from this casefile.
        </div>
      )}

      <div className="vendor-copy-form">
        <label className="field-compact">
          <span>Subject</span>
          <input
            className="input"
            value={draft.subject}
            onChange={handleTextChange('subject')}
            disabled={disabled}
            placeholder="Venue inquiry for AI networking night"
          />
        </label>

        <label className="field-compact">
          <span>Body</span>
          <textarea
            className="textarea vendor-copy-body"
            value={draft.body}
            onChange={handleTextChange('body')}
            disabled={disabled}
            placeholder="Draft vendor-facing copy will appear here."
          />
        </label>

        <label className="field-compact">
          <span>Ask summary</span>
          <textarea
            className="textarea vendor-copy-summary"
            value={draft.ask_summary}
            onChange={handleTextChange('ask_summary')}
            disabled={disabled}
            placeholder="Availability, minimum spend, AV, F&B package"
          />
        </label>

        <div className="vendor-copy-meta-grid">
          <div>
            <span className="field-label">Required response fields</span>
            {draft.required_vendor_response_fields.length > 0 ? (
              <div className="chip-row">
                {draft.required_vendor_response_fields.map((field) => <span key={field} className="chip">{field}</span>)}
              </div>
            ) : (
              <p className="small">No required response fields listed yet.</p>
            )}
          </div>
          <div>
            <span className="field-label">Risk notes</span>
            {draft.risk_notes.length > 0 ? (
              <ul className="compact-list">
                {draft.risk_notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            ) : (
              <p className="small">No risk notes listed yet.</p>
            )}
          </div>
        </div>

        <div className="vendor-copy-footer">
          <span className="small">Last saved: {formatTimestamp(draft.updated_at)}</span>
          <div className="cluster">
            <button type="button" className="btn btn--primary btn--sm" onClick={saveDraft} disabled={disabled || !dirty}>
              {saving ? 'Saving...' : 'Save Draft'}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={copyDraft} disabled={!casefile || loading || !copyTextFor(draft)}>
              Copy draft
            </button>
          </div>
        </div>
      </div>

      <div className="vendor-copy-refine">
        <label className="field-compact">
          <span>Refine instruction</span>
          <textarea
            className="textarea vendor-copy-instruction"
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            disabled={!casefile || running}
            placeholder="Make shorter, ask for an itemized quote, or adjust tone."
          />
        </label>
        <div className="chip-row">
          {PROMPT_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              className="chip chip--button"
              onClick={() => setInstruction(chip)}
              disabled={!casefile || running}
            >
              {chip}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={() => runVendorCopyAgent(hasArtifact)}
          disabled={!casefile || running}
        >
          {running ? 'Working...' : hasArtifact ? 'Refine draft' : 'Regenerate draft'}
        </button>
      </div>

      {draft.fallback_reason && <div className="block block--warn">Fallback: {draft.fallback_reason}</div>}
      {status && <div className="callout callout--success">{status}</div>}
    </section>
  )
}
