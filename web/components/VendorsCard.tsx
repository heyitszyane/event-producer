import React, { useEffect, useState } from 'react'
import { displayLabel } from '../lib/humanize'

export interface Vendor {
  id: string
  name: string
  category: string
  contact_email: string
  contact_phone: string
  rating: string
  notes: string
  locked?: boolean
}

interface VendorsCardProps {
  vendors: Vendor[]
}

const blankVendor: Vendor = {
  id: '',
  name: '',
  category: '',
  contact_email: '',
  contact_phone: '',
  rating: '',
  notes: '',
  locked: false,
}

function renderStars(rating: string | number): React.ReactNode {
  const r = typeof rating === 'string' ? parseFloat(rating) : rating
  if (isNaN(r)) return null
  const stars = []
  for (let i = 1; i <= 5; i++) {
    stars.push(
      <span key={i} style={{ color: i <= Math.floor(r) ? 'var(--status-warn)' : 'var(--border-subtle)' }}>
        ★
      </span>
    )
  }
  return <span aria-label={`Sample fixture rating ${String(rating)} out of 5`}>{stars} <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-xs)' }}>(sample fixture rating {String(rating)})</span></span>
}

export default function VendorsCard({ vendors }: VendorsCardProps) {
  const [draftVendors, setDraftVendors] = useState<Vendor[]>(vendors || [])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<Vendor>(blankVendor)

  useEffect(() => {
    setDraftVendors(vendors || [])
  }, [vendors])

  function startAdd() {
    setDraft({
      ...blankVendor,
      id: `draft-${Date.now()}`,
    })
    setEditingId('new')
  }

  function startEdit(vendor: Vendor) {
    setDraft(vendor)
    setEditingId(vendor.id)
  }

  function saveDraft() {
    if (!draft.name.trim()) return
    if (editingId === 'new') {
      setDraftVendors((prev) => [...prev, draft])
    } else {
      setDraftVendors((prev) => prev.map((vendor) => vendor.id === draft.id ? draft : vendor))
    }
    setDraft(blankVendor)
    setEditingId(null)
  }

  function field(label: string, key: keyof Vendor, placeholder = '') {
    return (
      <label className="field-compact">
        <span>{label}</span>
        <input
          className="input"
          value={String(draft[key] ?? '')}
          placeholder={placeholder}
          onChange={(e) => setDraft((prev) => ({ ...prev, [key]: e.target.value }))}
        />
      </label>
    )
  }

  return (
    <section className="card" id="vendors" aria-labelledby="vendors-heading">
      <div className="card__header">
        <h2 id="vendors-heading">Vendors</h2>
        <div className="cluster">
          <span className="badge badge--info">{draftVendors.length}</span>
          <button className="btn btn--primary btn--sm" type="button" onClick={startAdd}>Add vendor</button>
        </div>
      </div>

      <div className="block block--info">
        Vendor rows are frontend-session drafts. They are not sent, persisted, or locked until a human approves a vendor-facing action.
      </div>

      {editingId && (
        <div className="vendor-editor">
          <div className="vendor-editor__grid">
            {field('Vendor name', 'name', 'Venue, caterer, AV supplier')}
            {field('Category', 'category', 'AV Equipment')}
            {field('Email', 'contact_email', 'name@example.com')}
            {field('Phone', 'contact_phone', '+65 ...')}
            {field('Rating', 'rating', '4.5')}
            {field('Notes', 'notes', 'Draft notes')}
          </div>
          <div className="cluster">
            <button className="btn btn--primary btn--sm" type="button" onClick={saveDraft}>Save vendor</button>
            <button className="btn btn--ghost btn--sm" type="button" onClick={() => setEditingId(null)}>Cancel</button>
          </div>
        </div>
      )}

      {draftVendors.length === 0 ? (
        <div className="empty-state">
          No vendors configured yet. Add vendors here as draft rows.
        </div>
      ) : (
        <div style={{ maxHeight: 420, overflowY: 'auto' }}>
          {draftVendors.map((vendor) => {
            const isLocked = vendor.locked === true
            const isPending = !isLocked

            return (
              <div
                key={vendor.id}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 'var(--space-2)',
                  backgroundColor: 'var(--surface-tertiary)',
                  borderLeft: `3px solid ${isLocked ? 'var(--status-ok)' : 'var(--status-warn)'}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                      {vendor.name}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                      {displayLabel(vendor.category)}
                      {isLocked && <span style={{ marginLeft: 'var(--space-2)', color: 'var(--status-ok)' }}>Locked</span>}
                      {isPending && <span style={{ marginLeft: 'var(--space-2)', color: 'var(--status-warn)' }}>Pending</span>}
                    </div>
                  </div>
                  <div style={{ marginLeft: 'var(--space-2)', flexShrink: 0 }}>
                    {renderStars(vendor.rating)}
                  </div>
                </div>

                {vendor.contact_email && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                    <span aria-hidden="true">✉</span> <a href={`mailto:${vendor.contact_email}`}>{vendor.contact_email}</a>
                  </div>
                )}
                {vendor.contact_phone && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                    <span aria-hidden="true">☎</span> {vendor.contact_phone}
                  </div>
                )}
                {vendor.notes && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)', fontStyle: 'italic' }}>
                    {vendor.notes}
                  </div>
                )}
                <div className="cluster" style={{ marginTop: 'var(--space-2)' }}>
                  <button className="btn btn--ghost btn--sm" type="button" onClick={() => startEdit(vendor)} aria-label={`Edit vendor draft: ${vendor.name}`}>Edit</button>
                  <button className="btn btn--ghost btn--sm" type="button" onClick={() => setDraftVendors((prev) => prev.filter((item) => item.id !== vendor.id))} aria-label={`Remove vendor draft: ${vendor.name}`}>Remove</button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
