import { useEffect, useMemo, useState } from 'react'
import {
  appendVendorLog,
  createVendor,
  deleteVendor,
  getCasefile,
  listVendors,
  markVendorDraftCopied,
  markVendorDraftManuallySent,
  runSpecialistAgent,
  saveVendorDraft,
  updateVendor,
} from '../lib/casefiles'
import { displayLabel } from '../lib/humanize'
import InfoHint from './InfoHint'
import type {
  CasefileState,
  VendorPaymentStatus,
  VendorRecord,
  VendorWorkflowStatus,
} from '../types/agentic'
import { MODE_CLASS, MODE_LABEL } from '../types/agentic'

// The Vendor Notebook is a solo producer's chase list: who is being talked
// to, where each conversation stands, what money is due when — plus a
// per-vendor draft the Vendor Copy Agent writes from that vendor's own
// history. Nothing here sends messages or executes payments.

const CATEGORIES = [
  'venue', 'fnb', 'av', 'decor', 'talent',
  'logistics', 'security', 'photography', 'printing', 'other',
]

const WORKFLOW_STATUSES: VendorWorkflowStatus[] = [
  'not_started', 'draft_needed', 'draft_ready', 'copied_for_manual_send',
  'manually_sent', 'awaiting_reply', 'follow_up_needed', 'quote_received',
  'contract_pending', 'confirmed', 'settled',
]

const PAYMENT_STATUSES: VendorPaymentStatus[] = [
  'not_applicable', 'not_quoted', 'quote_requested', 'quote_received',
  'deposit_due', 'deposit_paid', 'final_balance_due', 'paid_in_full',
]

const WORKFLOW_BADGE: Record<VendorWorkflowStatus, string> = {
  not_started: 'badge--muted',
  draft_needed: 'badge--muted',
  draft_ready: 'badge--info',
  copied_for_manual_send: 'badge--info',
  manually_sent: 'badge--warn',
  awaiting_reply: 'badge--warn',
  follow_up_needed: 'badge--critical',
  quote_received: 'badge--info',
  contract_pending: 'badge--warn',
  confirmed: 'badge--ok',
  settled: 'badge--ok',
}

const PAYMENT_BADGE: Record<VendorPaymentStatus, string> = {
  not_applicable: 'badge--muted',
  not_quoted: 'badge--muted',
  quote_requested: 'badge--info',
  quote_received: 'badge--info',
  deposit_due: 'badge--warn',
  deposit_paid: 'badge--ok',
  final_balance_due: 'badge--warn',
  paid_in_full: 'badge--ok',
}

const PROMPT_CHIPS = [
  'Ask for an itemized quote and minimum spend',
  'Follow up politely — no reply yet',
  'Ask what AV and setup access are included',
  'Confirm deposit, final balance, and payment deadline',
]

// The activity log is append-only and can grow without bound, so it collapses
// to the most recent entries with an opt-in "show all".
const LOG_PREVIEW_COUNT = 4

interface SuggestedVendor {
  name: string
  category: string
  notes?: string
}

interface VendorNotebookProps {
  casefile: CasefileState | null
  suggestedVendors?: SuggestedVendor[]
  onCasefileChange: (casefile: CasefileState) => void
  onError: (message: string) => void
}

function timestampLabel(value?: string | null): string {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

function suggestedCategory(raw: string): string {
  const lowered = raw.toLowerCase()
  const match = CATEGORIES.find((category) => lowered.includes(category))
  if (match) return match
  if (lowered.includes('cater') || lowered.includes('food')) return 'fnb'
  if (lowered.includes('audio') || lowered.includes('visual') || lowered.includes('equipment')) return 'av'
  return 'other'
}

function moneyLabel(currency: string, amount?: string | null): string | null {
  if (!amount || !String(amount).trim()) return null
  return `${currency} ${amount}`.trim()
}

export default function VendorNotebook({
  casefile,
  suggestedVendors = [],
  onCasefileChange,
  onError,
}: VendorNotebookProps) {
  const eventId = casefile?.event_id || null
  const currency = casefile?.resolved.basics.currency || ''
  const [vendors, setVendors] = useState<VendorRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [adding, setAdding] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', category: 'venue', contact_name: '' })

  const [draftSubject, setDraftSubject] = useState('')
  const [draftBody, setDraftBody] = useState('')
  const [draftDirty, setDraftDirty] = useState(false)
  const [instruction, setInstruction] = useState('')

  const [logInput, setLogInput] = useState('')
  const [logType, setLogType] = useState<'vendor_response_logged' | 'note'>('vendor_response_logged')
  const [logExpanded, setLogExpanded] = useState(false)

  const [profileForm, setProfileForm] = useState<Partial<VendorRecord>>({})
  const [profileOpen, setProfileOpen] = useState(false)

  const selected = useMemo(
    () => vendors.find((vendor) => vendor.id === selectedId) || null,
    [vendors, selectedId],
  )

  // Newest-first; the render slices this to a preview unless expanded.
  const logEntries = useMemo(
    () => (selected ? [...selected.log].reverse() : []),
    [selected],
  )

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!eventId) {
        setVendors([])
        setSelectedId(null)
        return
      }
      try {
        const response = await listVendors(eventId)
        if (cancelled) return
        setVendors(response.vendors)
        setSelectedId((current) =>
          current && response.vendors.some((vendor) => vendor.id === current)
            ? current
            : response.vendors[0]?.id || null,
        )
      } catch (err) {
        if (!cancelled) onError(err instanceof Error ? err.message : 'Could not load the vendor notebook.')
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [eventId, onError])

  // Sync edit buffers when the selection (or its server state) changes.
  useEffect(() => {
    setDraftSubject(selected?.draft?.subject || '')
    setDraftBody(selected?.draft?.body || '')
    setDraftDirty(false)
    setProfileForm(selected ? profileFromVendor(selected) : {})
    setLogExpanded(false)
  }, [selectedId, selected])

  function profileFromVendor(vendor: VendorRecord): Partial<VendorRecord> {
    return {
      name: vendor.name,
      category: vendor.category,
      contact_name: vendor.contact_name,
      contact_email: vendor.contact_email,
      contact_phone: vendor.contact_phone,
      website: vendor.website,
      notes: vendor.notes,
      quoted_amount: vendor.quoted_amount,
      deposit_amount: vendor.deposit_amount,
      final_balance_amount: vendor.final_balance_amount,
      payment_due_date: vendor.payment_due_date,
      payment_notes: vendor.payment_notes,
    }
  }

  function applyVendor(updated: VendorRecord) {
    setVendors((current) => current.map((vendor) => (vendor.id === updated.id ? updated : vendor)))
  }

  async function withBusy<T>(work: () => Promise<T>): Promise<T | undefined> {
    setBusy(true)
    onError('')
    try {
      return await work()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Vendor notebook action failed.')
      return undefined
    } finally {
      setBusy(false)
    }
  }

  function openProfile(vendor: VendorRecord) {
    setSelectedId(vendor.id)
    setProfileForm(profileFromVendor(vendor))
    setProfileOpen(true)
  }

  async function handleAddVendor() {
    if (!eventId || !addForm.name.trim()) return
    await withBusy(async () => {
      const vendor = await createVendor(eventId, addForm)
      setVendors((current) => [...current, vendor])
      setSelectedId(vendor.id)
      setAdding(false)
      setAddForm({ name: '', category: 'venue', contact_name: '' })
    })
  }

  async function handleImportSuggestions() {
    if (!eventId) return
    await withBusy(async () => {
      for (const suggestion of suggestedVendors) {
        await createVendor(eventId, {
          name: suggestion.name,
          category: suggestedCategory(suggestion.category || ''),
          notes: [suggestion.notes, 'Imported from run fixtures.'].filter(Boolean).join(' '),
        })
      }
      const response = await listVendors(eventId)
      setVendors(response.vendors)
      setSelectedId(response.vendors[0]?.id || null)
    })
  }

  async function handleDelete(vendorId: string) {
    if (!eventId) return
    if (!window.confirm('Remove this vendor and its log from the notebook?')) return
    await withBusy(async () => {
      await deleteVendor(eventId, vendorId)
      setVendors((current) => current.filter((vendor) => vendor.id !== vendorId))
      setSelectedId((current) => (current === vendorId ? null : current))
      setProfileOpen(false)
    })
  }

  async function handleStatusChange(field: 'workflow_status' | 'payment_status', value: string) {
    if (!eventId || !selected) return
    await withBusy(async () => {
      applyVendor(await updateVendor(eventId, selected.id, { [field]: value }))
    })
  }

  async function handleQuickPayment(status: VendorPaymentStatus) {
    if (!eventId || !selected) return
    await withBusy(async () => {
      applyVendor(await updateVendor(eventId, selected.id, { payment_status: status }))
    })
  }

  async function handleSaveProfile() {
    if (!eventId || !selected) return
    await withBusy(async () => {
      applyVendor(await updateVendor(eventId, selected.id, profileForm))
      setProfileOpen(false)
    })
  }

  async function handleGenerate() {
    if (!eventId || !selected) return
    if (draftDirty && !window.confirm('You have unsaved draft edits. Replace them with a new agent draft?')) {
      return
    }
    await withBusy(async () => {
      await runSpecialistAgent(eventId, 'vendor_copy', {
        instruction,
        regenerate: Boolean(selected.draft),
        vendor_id: selected.id,
      })
      const response = await listVendors(eventId)
      setVendors(response.vendors)
      setInstruction('')
      onCasefileChange(await getCasefile(eventId))
    })
  }

  async function handleSaveDraft() {
    if (!eventId || !selected) return
    await withBusy(async () => {
      applyVendor(await saveVendorDraft(eventId, selected.id, {
        ...(selected.draft || {}),
        subject: draftSubject,
        body: draftBody,
      }))
      setDraftDirty(false)
    })
  }

  async function handleCopyDraft() {
    if (!eventId || !selected?.draft) return
    const text = `Subject: ${draftSubject.trim()}\n\n${draftBody.trim()}`.trim()
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      onError('Copy is unavailable in this browser; select the text manually.')
      return
    }
    await withBusy(async () => {
      applyVendor(await markVendorDraftCopied(eventId, selected.id))
    })
  }

  async function handleMarkSent() {
    if (!eventId || !selected?.draft) return
    await withBusy(async () => {
      applyVendor(await markVendorDraftManuallySent(eventId, selected.id))
    })
  }

  async function handleAppendLog() {
    if (!eventId || !selected || !logInput.trim()) return
    await withBusy(async () => {
      await appendVendorLog(eventId, selected.id, { body: logInput, type: logType })
      const response = await listVendors(eventId)
      setVendors(response.vendors)
      setLogInput('')
    })
  }

  const showImport = vendors.length === 0 && suggestedVendors.length > 0

  return (
    <section className="card vendor-notebook" aria-labelledby="vendor-notebook-heading">
      <div className="card__header">
        <div>
          <span className="war-eyebrow">Chase list · review before external use</span>
          <h2 id="vendor-notebook-heading">
            Vendor Notebook{' '}
            <InfoHint text="Persistent per-vendor workspace: workflow and payment status, an activity log, and a draft the Vendor Copy Agent writes from that vendor's own history. Drafts are copied manually; payments are recorded, never executed." />
          </h2>
        </div>
        <div className="cluster">
          <span className="badge badge--info">Draft only — not sent from the app</span>
          <span className="badge badge--muted">{vendors.length} vendor{vendors.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      {!casefile && (
        <div className="empty-state">Save or load a casefile to start the vendor notebook.</div>
      )}

      {casefile && (
        <div className="vendor-notebook__layout">
          <div className="vendor-notebook__list">
            {vendors.length === 0 && !adding && (
              <div className="empty-state">
                No vendors yet. Add the venue, caterer, and AV supplier you are talking to —
                each gets its own status, log, and draft.
              </div>
            )}

            {vendors.map((vendor) => {
              const quoted = moneyLabel(currency, vendor.quoted_amount)
              const contactLine = [vendor.contact_name, vendor.contact_email, vendor.contact_phone]
                .filter(Boolean)
                .join(' · ')
              return (
                <div
                  key={vendor.id}
                  className={
                    vendor.id === selectedId
                      ? 'vendor-card vendor-card--active'
                      : 'vendor-card'
                  }
                >
                  <button
                    type="button"
                    className="vendor-card__select"
                    onClick={() => setSelectedId(vendor.id)}
                  >
                    <span className="vendor-card__top">
                      <span className="vendor-card__name">{vendor.name}</span>
                      <span className="vendor-card__category">{displayLabel(vendor.category)}</span>
                    </span>
                    {contactLine && <span className="vendor-card__contact">{contactLine}</span>}
                    <span className="vendor-card__money">
                      {quoted && <span>Quoted {quoted}</span>}
                      {vendor.payment_due_date && !vendor.settled_at && (
                        <span>Due {vendor.payment_due_date}</span>
                      )}
                    </span>
                    <span className="vendor-card__badges">
                      <span className={`badge ${WORKFLOW_BADGE[vendor.workflow_status]}`}>
                        {displayLabel(vendor.workflow_status)}
                      </span>
                      {vendor.payment_status !== 'not_quoted' && vendor.payment_status !== 'not_applicable' && (
                        <span className={`badge ${PAYMENT_BADGE[vendor.payment_status]}`}>
                          {displayLabel(vendor.payment_status)}
                        </span>
                      )}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="vendor-card__edit"
                    onClick={() => openProfile(vendor)}
                    aria-label={`Edit ${vendor.name} details`}
                    title="Edit vendor details"
                  >
                    ✎
                  </button>
                </div>
              )
            })}

            <div className="cluster vendor-notebook__add-actions">
              <button type="button" className="btn btn--primary btn--sm" onClick={() => setAdding(true)} disabled={busy}>
                Add vendor
              </button>
              {showImport && (
                <button type="button" className="btn btn--ghost btn--sm" onClick={handleImportSuggestions} disabled={busy}>
                  Import {suggestedVendors.length} suggested (run fixtures)
                </button>
              )}
            </div>

            {adding && (
              <div className="vendor-notebook__add">
                <label className="field-compact">
                  <span>Vendor name</span>
                  <input
                    className="input"
                    value={addForm.name}
                    onChange={(event) => setAddForm((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Loft Venue Co"
                    autoFocus
                  />
                </label>
                <label className="field-compact">
                  <span>Category</span>
                  <select
                    className="input"
                    value={addForm.category}
                    onChange={(event) => setAddForm((current) => ({ ...current, category: event.target.value }))}
                  >
                    {CATEGORIES.map((category) => (
                      <option key={category} value={category}>{displayLabel(category)}</option>
                    ))}
                  </select>
                </label>
                <label className="field-compact">
                  <span>Contact name</span>
                  <input
                    className="input"
                    value={addForm.contact_name}
                    onChange={(event) => setAddForm((current) => ({ ...current, contact_name: event.target.value }))}
                    placeholder="Dana"
                  />
                </label>
                <div className="cluster">
                  <button type="button" className="btn btn--primary btn--sm" onClick={handleAddVendor} disabled={busy || !addForm.name.trim()}>
                    Save vendor
                  </button>
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => setAdding(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="vendor-notebook__workspace">
            {!selected && (
              <div className="empty-state">Select a vendor to see its status, draft, and log.</div>
            )}

            {selected && (
              <>
                <div className="vendor-notebook__statusbar">
                  <label className="field-compact">
                    <span>Workflow</span>
                    <select
                      className="input"
                      value={selected.workflow_status}
                      onChange={(event) => handleStatusChange('workflow_status', event.target.value)}
                      disabled={busy}
                    >
                      {WORKFLOW_STATUSES.map((status) => (
                        <option key={status} value={status}>{displayLabel(status)}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field-compact">
                    <span>Payment</span>
                    <select
                      className="input"
                      value={selected.payment_status}
                      onChange={(event) => handleStatusChange('payment_status', event.target.value)}
                      disabled={busy}
                    >
                      {PAYMENT_STATUSES.map((status) => (
                        <option key={status} value={status}>{displayLabel(status)}</option>
                      ))}
                    </select>
                  </label>
                  <div className="cluster vendor-notebook__quick">
                    <button type="button" className="btn btn--ghost btn--xs" onClick={() => handleQuickPayment('deposit_paid')} disabled={busy}>
                      Mark deposit paid
                    </button>
                    <button type="button" className="btn btn--ghost btn--xs" onClick={() => handleQuickPayment('paid_in_full')} disabled={busy}>
                      Mark paid in full
                    </button>
                    <button type="button" className="btn btn--ghost btn--xs" onClick={() => openProfile(selected)} disabled={busy}>
                      Edit details
                    </button>
                  </div>
                </div>

                <div className="vendor-notebook__draft">
                  <div className="vendor-notebook__subhead">
                    <strong>Draft for {selected.name}</strong>{' '}
                    <InfoHint text="The Vendor Copy Agent drafts from this vendor's profile, recent log, and current draft — never another vendor's history. You copy and send it yourself." />
                    {selected.draft?.model_mode && (
                      <span className={`badge ${MODE_CLASS[selected.draft.model_mode] ?? 'badge--muted'}`}>
                        {MODE_LABEL[selected.draft.model_mode]}
                      </span>
                    )}
                  </div>

                  {selected.draft ? (
                    <>
                      <label className="field-compact">
                        <span>Subject</span>
                        <input
                          className="input"
                          value={draftSubject}
                          onChange={(event) => { setDraftSubject(event.target.value); setDraftDirty(true) }}
                          disabled={busy}
                        />
                      </label>
                      <label className="field-compact">
                        <span>Body</span>
                        <textarea
                          className="textarea vendor-notebook__body"
                          value={draftBody}
                          rows={10}
                          onChange={(event) => { setDraftBody(event.target.value); setDraftDirty(true) }}
                          disabled={busy}
                        />
                      </label>
                      <div className="vendor-notebook__copyline small">
                        {selected.draft.copied_at && <span>Copied {timestampLabel(selected.draft.copied_at)}</span>}
                        {selected.draft.manually_sent_at && (
                          <span>Marked manually sent {timestampLabel(selected.draft.manually_sent_at)}</span>
                        )}
                        {!selected.draft.copied_at && !selected.draft.manually_sent_at && (
                          <span>Not copied yet — review before any external use.</span>
                        )}
                      </div>
                      <div className="cluster">
                        <button type="button" className="btn btn--primary btn--sm" onClick={handleSaveDraft} disabled={busy || !draftDirty}>
                          Save draft
                        </button>
                        <button type="button" className="btn btn--ghost btn--sm" onClick={handleCopyDraft} disabled={busy}>
                          Copy draft
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={handleMarkSent}
                          disabled={busy || selected.draft.copy_status === 'manually_sent'}
                        >
                          {selected.draft.copy_status === 'manually_sent' ? 'Manually sent' : 'Mark manually sent'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="small">
                      No draft yet. Describe the ask and let the Vendor Copy Agent prepare one from this
                      vendor&apos;s context.
                    </p>
                  )}

                  <label className="field-compact">
                    <span>{selected.draft ? 'Refine / follow-up instruction' : 'What should this note ask?'}</span>
                    <textarea
                      className="textarea vendor-notebook__instruction"
                      value={instruction}
                      onChange={(event) => setInstruction(event.target.value)}
                      placeholder="Ask the venue to confirm hold policy and send the contract."
                      disabled={busy}
                    />
                  </label>
                  <div className="chip-row">
                    {PROMPT_CHIPS.map((chip) => (
                      <button key={chip} type="button" className="chip chip--button" onClick={() => setInstruction(chip)} disabled={busy}>
                        {chip}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="btn btn--primary btn--sm" onClick={handleGenerate} disabled={busy}>
                    {busy ? 'Working...' : selected.draft ? 'Draft follow-up' : 'Generate draft'}
                  </button>
                </div>

                <div className="vendor-notebook__log">
                  <div className="vendor-notebook__subhead">
                    <strong>Activity log</strong>{' '}
                    <InfoHint text="Append-only history for this vendor: drafts, copies, manual sends, replies you log, payment updates. Vendor replies are injection-screened; flagged text never reaches an agent prompt." />
                  </div>
                  <div className="vendor-notebook__log-input">
                    <textarea
                      className="textarea"
                      value={logInput}
                      onChange={(event) => setLogInput(event.target.value)}
                      placeholder="Paste the vendor's reply or add a note for future you."
                      disabled={busy}
                    />
                    <div className="cluster">
                      <select
                        className="input vendor-notebook__log-type"
                        value={logType}
                        onChange={(event) => setLogType(event.target.value as 'vendor_response_logged' | 'note')}
                        disabled={busy}
                        aria-label="Log entry type"
                      >
                        <option value="vendor_response_logged">Vendor response</option>
                        <option value="note">Note</option>
                      </select>
                      <button type="button" className="btn btn--primary btn--sm" onClick={handleAppendLog} disabled={busy || !logInput.trim()}>
                        Add to log
                      </button>
                    </div>
                  </div>
                  {logEntries.length === 0 ? (
                    <p className="small">Nothing logged yet.</p>
                  ) : (
                    <>
                      <ul className="vendor-notebook__entries">
                        {(logExpanded ? logEntries : logEntries.slice(0, LOG_PREVIEW_COUNT)).map((entry) => (
                          <li key={entry.id}>
                            <div className="vendor-notebook__entry-line">
                              <span className="badge badge--muted">{displayLabel(entry.type)}</span>
                              {entry.actor === 'agent' && <span className="badge badge--info">agent</span>}
                              {entry.injection_flags.length > 0 && (
                                <span className="badge badge--critical" title={`Withheld from agent prompts. Flags: ${entry.injection_flags.join(', ')}`}>
                                  injection-flagged
                                </span>
                              )}
                              <span className="small">{timestampLabel(entry.timestamp)}</span>
                            </div>
                            <p className="vendor-notebook__entry-title">{entry.title}</p>
                            {entry.body && <p className="small vendor-notebook__entry-body">{entry.body}</p>}
                          </li>
                        ))}
                      </ul>
                      {logEntries.length > LOG_PREVIEW_COUNT && (
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm vendor-notebook__log-toggle"
                          onClick={() => setLogExpanded((value) => !value)}
                        >
                          {logExpanded ? 'Show less' : `Show all ${logEntries.length} entries`}
                        </button>
                      )}
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {profileOpen && selected && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="vendor-profile-title">
          <div className="modal-card">
            <div className="war-panel__header">
              <h2 id="vendor-profile-title">{selected.name} — profile &amp; payment</h2>
              <span className="badge badge--muted">recorded only — never executed</span>
            </div>
            <div className="vendor-notebook__profile-grid">
              {([
                ['name', 'Vendor name', 'text'],
                ['contact_name', 'Contact name', 'text'],
                ['contact_email', 'Email', 'text'],
                ['contact_phone', 'Phone', 'text'],
                ['website', 'Website', 'text'],
                ['quoted_amount', `Quoted amount${currency ? ` (${currency})` : ''}`, 'text'],
                ['deposit_amount', `Deposit amount${currency ? ` (${currency})` : ''}`, 'text'],
                ['final_balance_amount', `Final balance${currency ? ` (${currency})` : ''}`, 'text'],
                ['payment_due_date', 'Payment due date', 'date'],
              ] as const).map(([key, label, type]) => (
                <label className="field-compact" key={key}>
                  <span>{label}</span>
                  <input
                    className="input"
                    type={type}
                    value={String(profileForm[key] ?? '')}
                    onChange={(event) => setProfileForm((current) => ({ ...current, [key]: event.target.value }))}
                    disabled={busy}
                  />
                </label>
              ))}
              <label className="field-compact">
                <span>Category</span>
                <select
                  className="input"
                  value={String(profileForm.category ?? 'other')}
                  onChange={(event) => setProfileForm((current) => ({ ...current, category: event.target.value }))}
                  disabled={busy}
                >
                  {CATEGORIES.map((category) => (
                    <option key={category} value={category}>{displayLabel(category)}</option>
                  ))}
                </select>
              </label>
              <label className="field-compact vendor-notebook__notes">
                <span>Notes</span>
                <textarea
                  className="textarea"
                  value={String(profileForm.notes ?? '')}
                  onChange={(event) => setProfileForm((current) => ({ ...current, notes: event.target.value }))}
                  disabled={busy}
                />
              </label>
              <label className="field-compact vendor-notebook__notes">
                <span>Payment notes (recorded only — never executed)</span>
                <textarea
                  className="textarea"
                  value={String(profileForm.payment_notes ?? '')}
                  onChange={(event) => setProfileForm((current) => ({ ...current, payment_notes: event.target.value }))}
                  disabled={busy}
                />
              </label>
            </div>
            <div className="cluster" style={{ marginTop: 'var(--space-3)' }}>
              <button type="button" className="btn btn--primary" onClick={handleSaveProfile} disabled={busy}>
                Save details
              </button>
              <button type="button" className="btn btn--ghost" onClick={() => setProfileOpen(false)}>
                Cancel
              </button>
              <button type="button" className="btn btn--reject btn--sm vendor-notebook__remove" onClick={() => handleDelete(selected.id)} disabled={busy}>
                Remove vendor
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
