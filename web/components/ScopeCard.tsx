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
}

export default function ScopeCard({ items }: ScopeCardProps) {
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
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx}>
              <td data-label="Name">{item.name}</td>
              <td data-label="Category">{item.category}</td>
              <td data-label="Tier">
                <span className={`badge badge--${item.tier}`}>
                  {item.tier}
                </span>
              </td>
              <td data-label="Qty">{String(item.qty)}</td>
              <td data-label="Cost">
                {item.currency} {String(item.estimated_cost)}
              </td>
              <td data-label="Selected">{item.selected ? 'Yes' : 'No'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
