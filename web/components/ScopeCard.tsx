import { useState } from 'react'
import { apiFetch } from '../lib/api'
import { displayLabel } from '../lib/humanize'
import InfoHint from './InfoHint'
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
  budget?: BudgetSummary | null
  currency?: string
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

type BudgetRowStatus = 'included' | 'user_excluded'

const BUDGET_STATUS_COPY: Record<BudgetRowStatus, string> = {
  included: 'Counted in budget',
  user_excluded: 'Not counted — excluded by you',
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
  budget,
  currency = 'USD',
  onMutation,
}: ScopeCardProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addItem, setAddItem] = useState<ItemForm>(blankForm)
  // Edit happens in a focused modal instead of exploding the table row.
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editItem, setEditItem] = useState<ItemForm>(blankForm)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  function budgetStatus(item: ScopeItem): BudgetRowStatus {
    // Include/Exclude is the only gate now — every included item counts.
    return item.selected ? 'included' : 'user_excluded'
  }

  async function mutate(url: string, init: RequestInit): Promise<void> {
    if (!eventId) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(url, init)
      const data: ScopeMutationResult = await res.json()
      onMutation?.(data)
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
        body: JSON.stringify({ ...addItem, currency }),
      })
      setShowAddForm(false)
      setAddItem(blankForm)
    } catch {
      // Preserve input for correction.
    }
  }

  async function saveEdit() {
    if (editingIndex === null || !eventId || !editItem.name.trim() || !editItem.estimated_cost.trim()) return
    try {
      await mutate(`/event/${eventId}/scope-items/${editingIndex}`, {
        method: 'PATCH',
        body: JSON.stringify(editItem),
      })
      setEditingIndex(null)
      setEditItem(blankForm)
    } catch {
      // Keep the edit modal open on failure.
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

  // Let the deterministic engine greedily trim the lowest-priority tiers until
  // the plan fits the spendable pool; items are excluded, never deleted.
  async function autoFit() {
    if (!eventId) return
    await mutate(`/event/${eventId}/scope-items/auto-fit`, { method: 'POST' })
  }

  const form = (state: ItemForm, setState: (patch: Partial<ItemForm>) => void) => (
    <div className="scope-form-grid">
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
        <input className="input" value={state.qty} onChange={(e) => setState({ qty: e.target.value })} placeholder="1" />
      </label>
      <label className="field-compact">
        <span>Unit cost ({currency})</span>
        <input className="input" value={state.estimated_cost} onChange={(e) => setState({ estimated_cost: e.target.value })} placeholder="65" />
      </label>
    </div>
  )

  return (
    <section className="card" id="scope" aria-labelledby="scope-heading">
      <div className="card__header">
        <h2 id="scope-heading">
          Scope{' '}
          <InfoHint text="Every included item counts toward the budget — headroom can go negative when the plan is over cap. Use Exclude to drop an item from the total, or Auto-fit to budget to let the deterministic engine trim the lowest-priority tiers until the plan fits. Tiers are priority labels, not silent budget gates." />
        </h2>
        <div style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center', flexWrap: 'wrap' }}>
          {budget && items && items.length > 0 && (
            <button
              onClick={autoFit}
              disabled={loading}
              className="btn btn--ghost btn--sm"
              type="button"
              title="Exclude the lowest-priority tiers that don't fit the budget"
            >
              Auto-fit to budget
            </button>
          )}
          <button
            onClick={() => setShowAddForm((v) => !v)}
            className="btn btn--primary btn--sm"
            type="button"
          >
            + Add rental / service / vendor
          </button>
        </div>
      </div>

      {error && <div className="error-bar" role="alert">{error}</div>}

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
                <td data-label="Item">{item.name}</td>
                <td data-label="Category">{displayLabel(item.category)}</td>
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
                  {!item.selected && (
                    <div className="tier-helper scope-budget-status scope-budget-status--user_excluded">
                      {BUDGET_STATUS_COPY[budgetStatus(item)]}
                    </div>
                  )}
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
                        className="btn btn--reject btn--sm"
                        type="button"
                        aria-label={`Delete scope item: ${item.name}`}
                      >
                        Delete
                      </button>
                    )}
                    <button
                      onClick={() => toggleItem(idx)}
                      disabled={loading}
                      className={`btn btn--sm ${item.selected ? 'btn--warn' : 'btn--approve'}`}
                      type="button"
                    >
                      {item.selected ? 'Exclude' : 'Include'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editingIndex !== null && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="scope-modal-title">
          <div className="modal-card">
            <div className="war-panel__header">
              <h2 id="scope-modal-title">Edit scope item</h2>
            </div>
            {form(editItem, updateEdit)}
            <div className="cluster" style={{ marginTop: 'var(--space-3)' }}>
              <button className="btn btn--primary" type="button" disabled={loading} onClick={saveEdit}>
                {loading ? 'Saving...' : 'Save'}
              </button>
              <button className="btn btn--ghost" type="button" onClick={() => setEditingIndex(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
