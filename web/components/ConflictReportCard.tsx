export interface Conflict {
  task_id: string
  conflicting_task_id?: string
  conflict_type: string
  message: string
}

export interface ConflictReport {
  lead_time_conflicts: Conflict[]
  anchor_conflicts: Conflict[]
  cycle: string[]
  conflicts?: Conflict[]
}

interface ConflictReportCardProps {
  report: ConflictReport
}

function conflictTypeLabel(type: string): string {
  switch (type) {
    case 'lead_time': return 'Lead Time Conflict'
    case 'anchor': return 'Anchor Conflict'
    case 'cycle': return 'Dependency Cycle'
    case 'missing_dependency': return 'Missing Dependency'
    case 'duplicate_id': return 'Duplicate Task ID'
    default: return type
  }
}

export default function ConflictReportCard({ report }: ConflictReportCardProps) {
  const allConflicts = [
    ...(report.conflicts || []),
    ...report.lead_time_conflicts,
    ...report.anchor_conflicts,
  ]

  const leadTimeConflicts = allConflicts.filter((c) => c.conflict_type === 'lead_time')
  const anchorConflicts = allConflicts.filter((c) => c.conflict_type === 'anchor')
  const otherConflicts = allConflicts.filter(
    (c) => c.conflict_type !== 'lead_time' && c.conflict_type !== 'anchor'
  )

  const totalConflicts = allConflicts.length + (report.cycle.length > 0 ? 1 : 0)

  return (
    <section
      className="card"
      id="conflicts"
      aria-labelledby="conflicts-heading"
      style={{
        borderColor: 'var(--status-critical)',
        backgroundColor: 'var(--status-critical-bg)',
      }}
    >
      <div className="card__header">
        <h2 id="conflicts-heading" style={{ color: 'var(--status-critical)' }}>
          Schedule Conflicts Detected
        </h2>
        <span className="badge badge--critical">{totalConflicts} conflict{totalConflicts !== 1 ? 's' : ''}</span>
      </div>

      <div className="card__body">
        {/* Lead Time Conflicts */}
        {leadTimeConflicts.length > 0 && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h3 style={{
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--status-critical)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 'var(--space-2)',
            }}>
              Lead Time Conflicts
            </h3>
            {leadTimeConflicts.map((c, idx) => (
              <div
                key={`lt-${idx}`}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 'var(--space-2)',
                  border: '1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)',
                  backgroundColor: 'var(--surface-primary)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--status-critical)' }}>
                  {conflictTypeLabel(c.conflict_type)}
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', marginTop: 'var(--space-1)' }}>
                  Task: <code>{c.task_id}</code>
                  {c.conflicting_task_id && (
                    <> &rarr; <code>{c.conflicting_task_id}</code></>
                  )}
                </div>
                {c.message && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                    {c.message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Anchor Conflicts */}
        {anchorConflicts.length > 0 && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h3 style={{
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--status-critical)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 'var(--space-2)',
            }}>
              Anchor Conflicts
            </h3>
            {anchorConflicts.map((c, idx) => (
              <div
                key={`anchor-${idx}`}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 'var(--space-2)',
                  border: '1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)',
                  backgroundColor: 'var(--surface-primary)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--status-critical)' }}>
                  {conflictTypeLabel(c.conflict_type)}
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', marginTop: 'var(--space-1)' }}>
                  Task: <code>{c.task_id}</code>
                  {c.conflicting_task_id && (
                    <> &rarr; <code>{c.conflicting_task_id}</code></>
                  )}
                </div>
                {c.message && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                    {c.message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Other conflicts */}
        {otherConflicts.length > 0 && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h3 style={{
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--status-critical)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 'var(--space-2)',
            }}>
              Other Conflicts
            </h3>
            {otherConflicts.map((c, idx) => (
              <div
                key={`other-${idx}`}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 'var(--space-2)',
                  border: '1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)',
                  backgroundColor: 'var(--surface-primary)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--status-critical)' }}>
                  {conflictTypeLabel(c.conflict_type)}
                </div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', marginTop: 'var(--space-1)' }}>
                  Task: <code>{c.task_id}</code>
                </div>
                {c.message && (
                  <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', marginTop: 'var(--space-1)' }}>
                    {c.message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Dependency Cycles */}
        {report.cycle.length > 0 && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h3 style={{
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--status-critical)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: 'var(--space-2)',
            }}>
              Dependency Cycles
            </h3>
            <div style={{
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)',
              backgroundColor: 'var(--surface-primary)',
            }}>
              <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--status-critical)', marginBottom: 'var(--space-1)' }}>
                Circular Dependency Detected
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {report.cycle.map((taskId, idx) => (
                  <span key={idx}>
                    <code>{taskId}</code>
                    {idx < report.cycle.length - 1 && (
                      <span style={{ color: 'var(--text-secondary)' }}> &rarr; </span>
                    )}
                  </span>
                ))}
                <span style={{ color: 'var(--text-secondary)' }}> &rarr; </span>
                <code>{report.cycle[0]}</code>
              </div>
            </div>
          </div>
        )}

        {/* Footer guidance */}
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', margin: 0 }}>
          Adjust task dependencies, lead times, or remove duplicate IDs and re-run.
        </p>
      </div>
    </section>
  )
}
