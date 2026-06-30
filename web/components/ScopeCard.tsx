import { useState } from 'react'
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
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'
  const [loading, setLoading] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addItem, setAddItem] = useState<ItemForm>(blankForm)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editItem, setEditItem] = useState<ItemForm>(blankForm)

  async function mutate(url: string, init: RequestInit): Promise<void> {
    if (!eventId) return
    setLoading(true)
    try {
      const res = await fetch(url, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          'X-Demo-User': 'demo-user',
          ...(init.headers || {}),
        },
      })
      if (res.ok) {
        onMutation?.(await res.json())
      }
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
    await mutate(`${API_BASE}/event/${eventId}/scope-items`, {
      method: 'POST',
      body: JSON.stringify(addItem),
    })
    setShowAddForm(false)
    setAddItem(blankForm)
  }

  async function saveEdit(idx: number) {
    if (!eventId || !editItem.name.trim() || !editItem.estimated_cost.trim()) return
    await mutate(`${API_BASE}/event/${eventId}/scope-items/${idx}`, {
      method: 'PATCH',
      body: JSON.stringify(editItem),
    })
    setEditingIndex(null)
    setEditItem(blankForm)
  }

  async function toggleItem(idx: number) {
    if (!eventId) return
    await mutate(`${API_BASE}/event/${eventId}/scope-items/${idx}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
    })
  }

  async function changeTier(idx: number, newTier: ScopeItem['tier']) {
    if (!eventId) return
    await mutate(`${API_BASE}/event/${eventId}/scope-items/${idx}/retier`, {
      method: 'POST',
      body: JSON.stringify({ tier: newTier }),
    })
  }

  async function deleteItem(idx: number) {
    if (!eventId) return
    await mutate(`${API_BASE}/event/${eventId}/scope-items/${idx}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'text/plain' },
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
          {TIER_OPTIONS.map((tier) => <option key={tier} value={tier}>{tier}</option>)}
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
      <label className="field-compact field-compact--checkbox">
        <input type="checkbox" checked={state.selected} onChange={(e) => setState({ selected: e.target.checked })} />
        <span>Selected</span>
      </label>
    </div>
  )

  return (
    <section className="card" id="scope" aria-labelledby="scope-heading">
      <div className="card__header">
        <h2 id="scope-heading">Scope</h2>
        <div style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="badge badge--info">{items.length} items</span>
          <button
            onClick={() => setShowAddForm((v) => !v)}
            className="btn btn--primary btn--sm"
            type="button"
          >
            + Add rental / service / vendor
          </button>
        </div>
      </div>

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
              <th scope="col">Name</th>
              <th scope="col">Category</th>
              <th scope="col">Tier</th>
              <th scope="col">Qty</th>
              <th scope="col">Unit cost</th>
              <th scope="col">Selected</th>
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
                    <td data-label="Name">{item.name}</td>
                    <td data-label="Category">{item.category}</td>
                    <td data-label="Tier">
                      <select
                        value={item.tier}
                        onChange={(e) => changeTier(idx, e.target.value as ScopeItem['tier'])}
                        disabled={loading}
                        className="select select--compact"
                      >
                        {TIER_OPTIONS.map((tier) => <option key={tier} value={tier}>{tier}</option>)}
                      </select>
                    </td>
                    <td data-label="Qty">{String(item.qty)}</td>
                    <td data-label="Unit cost">{item.currency} {String(item.estimated_cost)}</td>
                    <td data-label="Selected">
                      <input type="checkbox" checked={item.selected} onChange={() => toggleItem(idx)} disabled={loading} />
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
                        <button onClick={() => deleteItem(idx)} disabled={loading} className="btn btn--ghost btn--sm" type="button">
                          Delete
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
