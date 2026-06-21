interface SecurityBeatProps {
  securityBeat: { status: string; note: string } | null
}

export default function SecurityBeat({ securityBeat }: SecurityBeatProps) {
  if (!securityBeat) {
    return null
  }

  const isDeferred = securityBeat.status === 'deferred_to_p6f'

  return (
    <section
      className="card"
      id="security-beat"
      aria-labelledby="security-beat-heading"
    >
      <div className="card__header">
        <h2 id="security-beat-heading">
          🛡 Security Posture
        </h2>
        <span className={`badge ${isDeferred ? 'badge--warn' : 'badge--ok'}`}>
          {isDeferred ? 'Deferred' : 'Active'}
        </span>
      </div>

      <div className="security-beat__body">
        <div className="security-beat__gate-check">
          <span className="security-beat__check-icon">✅</span>
          <span>Structural action gate is active</span>
        </div>
        <div className="security-beat__gate-check">
          <span className="security-beat__check-icon">✅</span>
          <span>Vendor data treated as untrusted</span>
        </div>
        <div className="security-beat__gate-check">
          <span className="security-beat__check-icon">✅</span>
          <span>No external action executed without approval</span>
        </div>
        {isDeferred && (
          <div className="security-beat__deferred">
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', margin: 0 }}>
              {securityBeat.note}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
