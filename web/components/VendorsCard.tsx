import React from 'react'

export interface Vendor {
  id: string
  name: string
  category: string
  contact_email: string
  contact_phone: string
  rating: string
  notes: string
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
      <span key={i} style={{ color: i <= Math.floor(r) ? '#f59e0b' : '#d1d5db' }}>
        ★
      </span>
    )
  }
  return <span>{stars} <span style={{ color: '#6b7280', fontSize: 12 }}>({String(rating)})</span></span>
}

export default function VendorsCard({ vendors }: VendorsCardProps) {
  if (!vendors || vendors.length === 0) {
    return (
      <div style={cardStyle}>
        <h2 style={headingStyle}>Vendors</h2>
        <p style={emptyStyle}>No vendors</p>
      </div>
    )
  }

  return (
    <div style={cardStyle}>
      <h2 style={headingStyle}>Vendors</h2>

      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {vendors.map((vendor) => (
          <div key={vendor.id} style={vendorItemStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={vendorNameStyle}>{vendor.name}</div>
                <div style={vendorCategoryStyle}>{vendor.category}</div>
              </div>
              <div style={{ marginLeft: 8 }}>{renderStars(vendor.rating)}</div>
            </div>
            {vendor.contact_email && (
              <div style={contactStyle}>
                ✉ <a href={`mailto:${vendor.contact_email}`} style={linkStyle}>{vendor.contact_email}</a>
              </div>
            )}
            {vendor.contact_phone && (
              <div style={contactStyle}>
                ☎ {vendor.contact_phone}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  padding: 16,
  marginBottom: 16,
  backgroundColor: '#ffffff',
}

const headingStyle: React.CSSProperties = {
  margin: '0 0 12px 0',
  fontSize: 18,
  fontWeight: 600,
  color: '#111827',
}

const emptyStyle: React.CSSProperties = {
  color: '#6b7280',
  fontSize: 14,
  margin: 0,
}

const vendorItemStyle: React.CSSProperties = {
  padding: '10px 12px',
  borderRadius: 6,
  marginBottom: 6,
  backgroundColor: '#f9fafb',
  border: '1px solid #e5e7eb',
}

const vendorNameStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 14,
  color: '#111827',
}

const vendorCategoryStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#6b7280',
  textTransform: 'capitalize',
}

const contactStyle: React.CSSProperties = {
  fontSize: 12,
  color: '#4b5563',
  marginTop: 2,
}

const linkStyle: React.CSSProperties = {
  color: '#2563eb',
  textDecoration: 'none',
}
