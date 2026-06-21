import React from 'react'

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
  return <span>{stars} <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-xs)' }}>({String(rating)})</span></span>
}

export default function VendorsCard({ vendors }: VendorsCardProps) {
  if (!vendors || vendors.length === 0) {
    return (
      <section className="card" id="vendors" aria-labelledby="vendors-heading">
        <div className="card__header">
          <h2 id="vendors-heading">Vendors</h2>
        </div>
        <div className="empty-state">
          No vendors configured &mdash; Add vendors via chat command.
        </div>
      </section>
    )
  }

  return (
    <section className="card" id="vendors" aria-labelledby="vendors-heading">
      <div className="card__header">
        <h2 id="vendors-heading">Vendors</h2>
        <span className="badge badge--info">{vendors.length}</span>
      </div>

      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {vendors.map((vendor) => {
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
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', textTransform: 'capitalize' }}>
                    {vendor.category}
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
                  ✉ <a href={`mailto:${vendor.contact_email}`}>{vendor.contact_email}</a>
                </div>
              )}
              {vendor.contact_phone && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                  ☎ {vendor.contact_phone}
                </div>
              )}
              {vendor.notes && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)', fontStyle: 'italic' }}>
                  {vendor.notes}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
