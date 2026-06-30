import { useState } from 'react'

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

interface ScopeCardProps {
  items: ScopeItem[]
  eventId?: string
  onItemsChange?: (items: ScopeItem[]) => void
}

interface EditState {
  editingIndex: number | null
  tier: 'must' | 'should' | 'could' | 'wow'
}

interface AddItemForm {
  name: string
  description: string
  category: string
  tier: 'must' | 'should' | 'could' | 'wow'
  estimated_cost: string
  qty: string
}

export default function ScopeCard({
  items,
  eventId,
  onItemsChange,
}: ScopeCardProps) {
  const [editState, setEditState] = useState<EditState>({
    editingIndex: null,
    tier: 'could',
  })
  const [loading, setLoading] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addItem, setAddItem] = useState<AddItemForm>({
    name: '',
    description: '',
    category: 'other',
    tier: 'could',
    estimated_cost: '',
    qty: '1',
  })
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

  if (!items || items.length === 0) {
    return (
      <section className="card" id="scope" aria-labelledby="scope-heading">
        <div className="card__header">
          <h2 id="scope-heading">Scope</h2>
        </div>
        <div className="empty-state">
          No scope items &mdash; Run the event to generate.
        </div>
      </section>
    )
  }

  async function toggleItem(idx: number) {
    if (!eventId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/event/${eventId}/scope-items/${idx}/toggle`, {
        method: 'POST',
        headers: { 'X-Demo-User': 'demo-user' },
      })
      if (res.ok) {
        const data = await res.json()
        onItemsChange?.(data.scope_items)
      }
    } finally {
      setLoading(false)
    }
  }

  async function changeTier(idx: number, newTier: 'must' | 'should' | 'could' | 'wow') {
    if (!eventId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/event/${eventId}/scope-items/${idx}/retier`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-User': 'demo-user' },
        body: JSON.stringify({ tier: newTier }),
      })
      if (res.ok) {
        const data = await res.json()
        onItemsChange?.(data.scope_items)
      }
    } finally {
      setLoading(false)
    }
  }

  async function deleteItem(idx: number) {
    if (!eventId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/event/${eventId}/scope-items/${idx}`, {
        method: 'DELETE',
        headers: { 'X-Demo-User': 'demo-user' },
      })
      if (res.ok) {
        const data = await res.json()
        onItemsChange?.(data.scope_items)
      }
    } finally {
      setLoading(false)
    }
  }

  // P7D: Add new scope item
  async function addScopeItem() {
    if (!eventId || !addItem.name.trim() || !addItem.estimated_cost) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/event/${eventId}/scope-items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-User': 'demo-user' },
        body: JSON.stringify({
          name: addItem.name,
          description: addItem.description,
          category: addItem.category,
          tier: addItem.tier,
          qty: addItem.qty,
          estimated_cost: addItem.estimated_cost,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        onItemsChange?.(data.scope_items)
        setShowAddForm(false)
        setAddItem({ name: '', description: '', category: 'other', tier: 'could', estimated_cost: '', qty: '1' })
      }
    } finally {
      setLoading(false)
    }
  }

  const TIER_OPTIONS: ('must' | 'should' | 'could' | 'wow')[] = ['must', 'should', 'could', 'wow']

  return (
    <section className="card" id="scope" aria-labelledby="scope-heading">
      <div className="card__header">
        <h2 id="scope-heading">Scope</h2>
        <div style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center' }}>
          <span className="badge badge--info">{items.length} items</span>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="btn btn--ghost btn--sm"
            title="Add scope item"
            type="button"
          >
            + Add
          </button>
        </div>
      </div>

      {/* P7D: Add item form */}
      {showAddForm && (
        <div style={{ padding: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-tertiary)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 'var(--space-2)' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-xs)' }}>Name</span>
              <input
                type="text"
                value={addItem.name}
                onChange={(e) => setAddItem({ ...addItem, name: e.target.value })}
                placeholder="Item name"
                className="input"
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-xs)' }}>Category</span>
              <input
                type="text"
                value={addItem.category}
                onChange={(e) => setAddItem({ ...addItem, category: e.target.value })}
                placeholder="Category"
                className="input"
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-xs)' }}>Cost</span>
              <input
                type="text"
                value={addItem.estimated_cost}
                onChange={(e) => setAddItem({ ...addItem, estimated_cost: e.target.value })}
                placeholder="e.g. 1000"
                className="input"
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-xs)' }}>Tier</span>
              <select
                value={addItem.tier}
                onChange={(e) => setAddItem({ ...addItem, tier: e.target.value as typeof addItem.tier })}
                className="select"
              >
                {TIER_OPTIONS.map((tier) => (
                  <option key={tier} value={tier}>{tier}</option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-2)' }}>
            <button onClick={addScopeItem} disabled={loading} className="btn btn--primary btn--sm">
              Add to scope
            </button>
            <button onClick={() => setShowAddForm(false)} className="btn btn--ghost btn--sm">
              Cancel
            </button>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Category</th>
            <th scope="col">Tier</th>
            <th scope="col">Qty</th>
            <th scope="col">Cost</th>
            <th scope="col">Selected</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx}>
              <td data-label="Name">{item.name}</td>
              <td data-label="Category">{item.category}</td>
              <td data-label="Tier">
                <select
                  value={item.tier}
                  onChange={(e) => changeTier(idx, e.target.value as typeof item.tier)}
                  disabled={loading}
                  style={{ fontSize: 'var(--text-sm)', padding: '2px 4px' }}
                >
                  {TIER_OPTIONS.map((tier) => (
                    <option key={tier} value={tier}>{tier}</option>
                  ))}
                </select>
              </td>
              <td data-label="Qty">{String(item.qty)}</td>
              <td data-label="Cost">
                {item.currency} {String(item.estimated_cost)}
              </td>
              <td data-label="Selected">
                <input
                  type="checkbox"
                  checked={item.selected}
                  onChange={() => toggleItem(idx)}
                  disabled={loading}
                />
              </td>
              <td data-label="Actions">
                <button
                  onClick={() => deleteItem(idx)}
                  disabled={loading}
                  className="btn btn--ghost btn--sm"
                  title="Delete item"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
