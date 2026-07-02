import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { displayLabel } from '../lib/humanize'
import type { RecomputeNotice } from '../types/agentic'
import type { BudgetSummary } from './BudgetCard'
import type { ScheduleResult, CallSheetEntry } from './RunOfShowCard'

export interface ScopeItem {
  name: string
  description: string
  category: string
  tier: 'must' | 'should' | 'could' | 'wow'
  estimated_cost: string
  currency: string
  qty: string
  selected: boolean
}

export interface ScopeMutationResult {
  scope_items: ScopeItem[]
  budget_summary?: BudgetSummary
  schedule_result?: ScheduleResult | null
  call_sheet?: CallSheetEntry[]
  recompute_notice?: RecomputeNotice
}

interface ScopeCardProps {
  items: ScopeItem[]
  eventId?: string
  onMutation?: (result: ScopeMutationResult) => void
}

interface ItemForm {
  name: string
  description: string
  category: string
  tier: 'must' | 'should' | 'could' | 'wow'
  qty: string
  estimated_cost: string
  selected: boolean
}

const TIER_OPTIONS: Array<'must' | 'should' | 'could' | 'wow'> = ['must', 'should', 'could', 'wow']
const TIER_COPY: Record<ScopeItem['tier'], { label: string; helper: string }> = {
  must: { label: 'Essential', helper: 'Required for the event to work.' },
  should: { label: 'Recommended', helper: 'Strong value, keep if budget allows.' },
  could: { label: 'Optional', helper: 'Useful enhancement, easy to cut.' },
  wow: { label: 'Stretch', helper: 'Premium or brand-building upgrade.' },
}

const blankForm: ItemForm = {
  name: '',
  description: '',
  category: 'other',
  tier: 'could',
  qty: '1',
  estimated_cost: '',
  selected: true,
}

function formFromItem(item: ScopeItem): ItemForm {
  return {
    name: item.name,
    description: item.description,
    category: item.category,
    tier: item.tier,
    qty: String(item.qty || '1'),
    estimated_cost: String(item.estimated_cost || '0'),
    selected: Boolean(item.selected),
  }
}

export default function ScopeCard({
  items,
  eventId,
  onMutation,
}: ScopeCardProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addItem, setAddItem] = useState<ItemForm>(blankForm)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editItem, setEditItem] = useState<ItemForm>(blankForm)
  const [inlineEdit, setInlineEdit] = useState<{ idx: number; field: 'name' | 'category'; value: string } | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  async function mutate(url: string, init: RequestInit): Promise<void> {
    if (!eventId) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(url, init)
      const data: ScopeMutationResult = await res.json()
      onMutation?.(data)
      setFeedback(
        data.recompute_notice?.message ||
        (data.recompute_notice?.schedule_status === 'warning'
          ? 'Budget recalculated. Schedule warning: new item not yet scheduled.'
          : 'Budget recalculated. Schedule recomputed.')
      )
      setDeleteConfirm(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      throw err
    } finally {
      setLoading(false)
    }
  }

  function updateAdd(patch: Partial<ItemForm>) {
    setAddItem((prev) => ({ ...prev, ...patch }))
  }

  function updateEdit(patch: Partial<ItemForm>) {
    setEditItem((prev) => ({ ...prev, ...patch }))
  }

  async function addScopeItem() {
    if (!eventId || !addItem.name.trim() || !addItem.estimated_cost.trim()) return
    try {
      await mutate(`/event/${eventId}/scope-items`, {
      method: 'POST',
      body: JSON.stringify(addItem),
      })
      setShowAddForm(false)
      setAddItem(blankForm)
    } catch {
      // Preserve input for correction.
    }
  }

  async function saveEdit(idx: number) {
    if (!eventId || !editItem.name.trim() || !editItem.estimated_cost.trim()) return
    try {
      await mutate(`/event/${eventId}/scope-items/${idx}`, {
      method: 'PATCH',
      body: JSON.stringify(editItem),
      })
      setEditingIndex(null)
      setEditItem(blankForm)
    } catch {
      // Keep the edit form open on failure.
    }
  }

  async function saveInlineEdit() {
    if (!inlineEdit) return
    const current = items[inlineEdit.idx]
    if (!current) return
    try {
      await mutate(`/event/${eventId}/scope-items/${inlineEdit.idx}`, {
      method: 'PATCH',
      body: JSON.stringify({
        ...formFromItem(current),
        [inlineEdit.field]: inlineEdit.value,
      }),
      })
      setInlineEdit(null)
    } catch {
      // Keep the inline editor open on failure.
    }
  }

  async function toggleItem(idx: number) {
    if (!eventId) return
    await mutate(`/event/${eventId}/scope-items/${idx}/toggle`, {
      method: 'POST',
    })
  }

  async function changeTier(idx: number, newTier: ScopeItem['tier']) {
    if (!eventId) return
    await mutate(`/event/${eventId}/scope-items/${idx}/retier`, {
      method: 'POST',
      body: JSON.stringify({ tier: newTier }),
    })
  }

  async function deleteItem(idx: number) {
    if (!eventId) return
    await mutate(`/event/${eventId}/scope-items/${idx}`, {
      method: 'DELETE',
    })
  }

  const form = (state: ItemForm, setState: (patch: Partial<ItemForm>) => void) => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 'var(--space-2)' }}>
      <label className="field-compact">
        <span>Name</span>
        <input className="input" value={state.name} onChange={(e) => setState({ name: e.target.value })} placeholder="Vendor/service name" />
      </label>
      <label className="field-compact">
        <span>Category</span>
        <input className="input" value={state.category} onChange={(e) => setState({ category: e.target.value })} placeholder="catering" />
      </label>
      <label className="field-compact">
        <span>Tier</span>
        <select className="select" value={state.tier} onChange={(e) => setState({ tier: e.target.value as ItemForm['tier'] })}>
          {TIER_OPTIONS.map((tier) => <option key={tier} value={tier}>{TIER_COPY[tier].label}</option>)}
        </select>
      </label>
      <label className="field-compact">
        <span>Quantity</span>
        <input className="input" value={state.qty} onChange={(e) => setState({ qty: e.target.value })} placeholder="100" />
      </label>
      <label className="field-compact">
        <span>Unit cost</span>
        <input className="input" value={state.estimated_cost} onChange={(e) => setState({ estimated_cost: e.target.value })} placeholder="65" />
      </label>
    </div>
  )

  return (
    <section className="card" id="scope" aria-labelledby="scope-heading">
      <div className="card__header">
        <h2 id="scope-heading">Scope</h2>
        <div style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => setShowAddForm((v) => !v)}
            className="btn btn--primary btn--sm"
            type="button"
          >
            + Add rental / service / vendor
          </button>
          <button
            className="btn btn--ghost btn--sm"
            type="button"
            disabled={loading || items.length === 0}
            onClick={() => setFeedback('Budget recalculated. Schedule recomputed.')}
          >
            Recompute
          </button>
        </div>
      </div>

      {error && <div className="error-bar" role="alert">{error}</div>}
      {feedback && <div className="block block--info" aria-live="polite">{feedback}</div>}

      {showAddForm && (
        <div style={{ padding: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-tertiary)' }}>
          {form(addItem, updateAdd)}
          <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-2)' }}>
            <button onClick={addScopeItem} disabled={loading} className="btn btn--primary btn--sm" type="button">
              Add to scope
            </button>
            <button onClick={() => setShowAddForm(false)} className="btn btn--ghost btn--sm" type="button">
              Cancel
            </button>
          </div>
        </div>
      )}

      {!items || items.length === 0 ? (
        <div className="empty-state">No scope items. Add a rental, service, vendor, or run the brief.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
          <th scope="col">Item</th>
          <th scope="col">Category</th>
          <th scope="col">Tier</th>
          <th scope="col">Qty</th>
          <th scope="col">Unit cost</th>
              <th scope="col">Total</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr key={`${item.name}-${idx}`}>
                {editingIndex === idx ? (
                  <td colSpan={7} data-label="Edit">
                    {form(editItem, updateEdit)}
                    <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-2)' }}>
                      <button className="btn btn--primary btn--sm" disabled={loading} onClick={() => saveEdit(idx)} type="button">Save</button>
                      <button className="btn btn--ghost btn--sm" onClick={() => setEditingIndex(null)} type="button">Cancel</button>
                    </div>
                  </td>
                ) : (
                  <>
                    <td data-label="Item">
                      {inlineEdit?.idx === idx && inlineEdit.field === 'name' ? (
                        <input
                          className="input input--inline"
                          value={inlineEdit.value}
                          autoFocus
                          onChange={(e) => setInlineEdit({ ...inlineEdit, value: e.target.value })}
                          onBlur={saveInlineEdit}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveInlineEdit()
                            if (e.key === 'Escape') setInlineEdit(null)
                          }}
                        />
                      ) : (
                        <button className="inline-edit-button" type="button" onClick={() => setInlineEdit({ idx, field: 'name', value: item.name })}>
                          {item.name}
                        </button>
                      )}
                    </td>
                    <td data-label="Category">
                      {inlineEdit?.idx === idx && inlineEdit.field === 'category' ? (
                        <input
                          className="input input--inline"
                          value={inlineEdit.value}
                          autoFocus
                          onChange={(e) => setInlineEdit({ ...inlineEdit, value: e.target.value })}
                          onBlur={saveInlineEdit}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveInlineEdit()
                            if (e.key === 'Escape') setInlineEdit(null)
                          }}
                        />
                      ) : (
                        <button className="inline-edit-button" type="button" onClick={() => setInlineEdit({ idx, field: 'category', value: item.category })}>
                          {displayLabel(item.category)}
                        </button>
                      )}
                    </td>
                    <td data-label="Tier">
                      <select
                        value={item.tier}
                        onChange={(e) => changeTier(idx, e.target.value as ScopeItem['tier'])}
                        disabled={loading}
                        className="select select--compact"
                        aria-label={`Change tier for ${item.name}`}
                      >
                        {TIER_OPTIONS.map((tier) => <option key={tier} value={tier}>{TIER_COPY[tier].label}</option>)}
                      </select>
                      <div className="muted tier-helper">{TIER_COPY[item.tier].helper}</div>
                    </td>
                    <td data-label="Qty">{String(item.qty)}</td>
                    <td data-label="Unit cost">{item.currency} {String(item.estimated_cost)}</td>
                    <td data-label="Total">
                      {item.currency} {(Number(item.qty || 0) * Number(item.estimated_cost || 0)).toLocaleString()}
                    </td>
                    <td data-label="Actions">
                      <div style={{ display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
                        <button
                          onClick={() => {
                            setEditingIndex(idx)
                            setEditItem(formFromItem(item))
                          }}
                          disabled={loading}
                          className="btn btn--ghost btn--sm"
                          type="button"
                        >
                          Edit
                        </button>
                        {deleteConfirm === idx ? (
                          <span className="confirm-inline">
                            <span>Delete?</span>
                            <button
                              onClick={() => deleteItem(idx)}
                              disabled={loading}
                              className="btn btn--reject btn--sm"
                              type="button"
                              aria-label={`Confirm delete scope item: ${item.name}`}
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setDeleteConfirm(null)}
                              className="btn btn--ghost btn--sm"
                              type="button"
                            >
                              Cancel
                            </button>
                          </span>
                        ) : (
                          <button
                            onClick={() => setDeleteConfirm(idx)}
                            disabled={loading}
                            className="btn btn--ghost btn--sm"
                            type="button"
                            aria-label={`Delete scope item: ${item.name}`}
                          >
                            Delete
                          </button>
                        )}
                        <button onClick={() => toggleItem(idx)} disabled={loading} className="btn btn--ghost btn--sm" type="button">
                          {item.selected ? 'Exclude' : 'Include'}
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
