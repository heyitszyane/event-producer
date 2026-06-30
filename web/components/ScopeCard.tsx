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

  const TIER_OPTIONS: ('must' | 'should' | 'could' | 'wow')[] = ['must', 'should', 'could', 'wow']

  return (
    <section className="card" id="scope" aria-labelledby="scope-heading">
      <div className="card__header">
        <h2 id="scope-heading">Scope</h2>
        <span className="badge badge--info">{items.length} items</span>
      </div>

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
