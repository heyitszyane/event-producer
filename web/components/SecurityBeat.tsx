import { displayLabel } from '../lib/humanize'

interface SecurityBeatFixture {
  id: string
  channel: string
  label: string
  content: string
  flags: string[]
  classifier_role: string
  blocked_by: string
  external_action_executed: boolean
  ocr_implemented?: boolean
}

interface SecurityBeatGate {
  name: string
  load_bearing_control: boolean
  reason: string
}

interface SecurityBeatProps {
  securityBeat: {
    status: string
    title?: string
    summary?: string
    source?: string
    external_action_executed?: boolean
    state_mutation_executed?: boolean
    blocked_actions?: string[]
    gate?: SecurityBeatGate
    fixtures?: SecurityBeatFixture[]
    approval_required?: boolean
    approval_id?: string
    notes?: string[]
    note?: string
  } | null
}

export default function SecurityBeat({ securityBeat }: SecurityBeatProps) {
  if (!securityBeat) {
    return null
  }

  const isDeferred = securityBeat.status === 'deferred_to_p6f'
  const isScripted = securityBeat.status === 'scripted_demo_ready'
  const fixtures = securityBeat.fixtures || []
  const gate = securityBeat.gate
  const blockedActions = securityBeat.blocked_actions || []
  const notes = securityBeat.notes || []
  const externalExecuted = securityBeat.external_action_executed
  const stateMutation = securityBeat.state_mutation_executed

  return (
    <section
      className="card"
      id="security-beat"
      aria-labelledby="security-beat-heading"
    >
      <div className="card__header">
        <h2 id="security-beat-heading">
          <span aria-hidden="true">🛡</span> Security Posture
        </h2>
        <span className={`badge ${isDeferred ? 'badge--warn' : isScripted ? 'badge--ok' : 'badge--warn'}`}>
          {isDeferred ? 'Deferred' : isScripted ? 'Scripted Demo' : securityBeat.status}
        </span>
      </div>

      <div className="security-beat__body">
        {/* Gate checks — always shown */}
        <div className="security-beat__gate-check">
          <span className="security-beat__check-icon" aria-hidden="true">✅</span>
          <span>Structural action gate is active</span>
        </div>
        <div className="security-beat__gate-check">
          <span className="security-beat__check-icon" aria-hidden="true">✅</span>
          <span>Vendor data treated as untrusted</span>
        </div>
        <div className="security-beat__gate-check">
          <span className="security-beat__check-icon" aria-hidden="true">✅</span>
          <span>No external action executed without approval</span>
        </div>

        {/* Deferred note (backward compat) */}
        {isDeferred && securityBeat.note && (
          <div className="security-beat__deferred">
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', margin: 0 }}>
              {securityBeat.note}
            </p>
          </div>
        )}

        {/* Scripted demo content */}
        {isScripted && (
          <>
            {/* Title + summary */}
            {securityBeat.title && (
              <div style={{ marginTop: 'var(--space-3)' }}>
                <p style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  {securityBeat.title}
                </p>
              </div>
            )}
            {securityBeat.summary && (
              <div style={{ marginTop: 'var(--space-2)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', margin: 0 }}>
                  {securityBeat.summary}
                </p>
              </div>
            )}

            {/* Gate + blocked actions */}
            <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--surface-secondary)', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-2)' }}>
                Structural Action Gate
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
                Vendor data is untrusted &middot; Human approval required
              </div>
              {gate && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)' }}>
                  {gate.reason}
                </div>
              )}
              {blockedActions.length > 0 && (
                <div style={{ marginTop: 'var(--space-2)' }}>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Blocked actions:
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)', marginTop: 'var(--space-1)' }}>
                    {blockedActions.map((a) => (
                      <span key={a} className="badge badge--critical" style={{ fontSize: 'var(--text-xs)' }}>
                        {displayLabel(a)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* No-execution status */}
            <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-2)', background: 'var(--surface-secondary)', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 'var(--text-sm)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-1)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>External action executed</span>
                <span style={{ fontWeight: 600, color: externalExecuted ? 'var(--status-critical)' : 'var(--status-ok)' }}>
                  {externalExecuted ? 'YES ⚠' : 'No'}
                </span>
              </div>
              <div style={{ fontSize: 'var(--text-sm)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-secondary)' }}>State mutation executed</span>
                <span style={{ fontWeight: 600, color: stateMutation ? 'var(--status-critical)' : 'var(--status-ok)' }}>
                  {stateMutation ? 'YES ⚠' : 'No'}
                </span>
              </div>
            </div>

            {/* Fixtures */}
            {fixtures.length > 0 && (
              <div style={{ marginTop: 'var(--space-3)' }}>
                <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-2)' }}>
                  Scripted Fixtures
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)' }}>
                  Scripted fixture — not live Telegram
                </div>
                {fixtures.map((f) => (
                  <div key={f.id} style={{ marginBottom: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--surface-secondary)', borderRadius: 6, border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                      <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {f.label}
                      </span>
                      <span className="badge badge--warn" style={{ fontSize: 'var(--text-xs)' }}>
                        {displayLabel(f.blocked_by)}
                      </span>
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)' }}>
                      Channel: {displayLabel(f.channel)} &middot; Classifier: {displayLabel(f.classifier_role)}
                      {f.ocr_implemented === false && ' &middot; OCR not implemented'}
                    </div>
                    <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', fontStyle: 'italic', padding: 'var(--space-2)', background: 'var(--surface-primary)', borderRadius: 4, border: '1px solid var(--border-subtle)' }}>
                      &ldquo;{f.content}&rdquo;
                    </div>
                    <div style={{ marginTop: 'var(--space-1)', display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
                      {f.flags.map((flag) => (
                        <span key={flag} className="badge" style={{ fontSize: 'var(--text-xs)', background: 'var(--surface-tertiary)', color: 'var(--text-secondary)' }}>
                          {displayLabel(flag)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Approval linkage */}
            {securityBeat.approval_required && securityBeat.approval_id && (
              <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                Pending approval: <code>{securityBeat.approval_id}</code>
              </div>
            )}

            {/* Notes */}
            {notes.length > 0 && (
              <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>
                <ul style={{ margin: 0, paddingLeft: 'var(--space-4)' }}>
                  {notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
