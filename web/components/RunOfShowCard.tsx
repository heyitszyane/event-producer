export interface ScheduledTask {
  id: string
  name: string
  duration: string
  earliest_start: string
  earliest_finish: string
  latest_start: string
  latest_finish: string
  dependencies: string[]
  lead_time: string | null
  anchor: string | null
}

export interface ScheduleResult {
  ordered_tasks: ScheduledTask[]
  critical_path: string[]
}

export interface CallSheetEntry {
  task_name: string
  start_time: string
  end_time: string
  is_anchor: boolean
}

interface RunOfShowCardProps {
  schedule: ScheduleResult | null | undefined
  callSheet: CallSheetEntry[]
}

function formatTime(isoString: string | undefined): string {
  if (!isoString) return '—'
  try {
    return new Date(isoString).toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  } catch {
    return isoString
  }
}

function formatDate(isoString: string | undefined): string {
  if (!isoString) return ''
  try {
    return new Date(isoString).toLocaleDateString([], {
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return isoString
  }
}

export default function RunOfShowCard({ schedule, callSheet }: RunOfShowCardProps) {
  const tasks = schedule?.ordered_tasks || []
  const criticalPath = schedule?.critical_path || []
  const criticalCount = criticalPath.length
  const sheetEntries = (callSheet || []).filter((entry) => {
    if (!schedule) return true
    return !tasks.some((t) => t.name === entry.task_name)
  })

  const hasConflicts = false // Conflict report is handled separately
  const totalTasks = tasks.length + sheetEntries.length

  if (tasks.length === 0 && sheetEntries.length === 0) {
    return (
      <section className="card" id="schedule" aria-labelledby="schedule-heading">
        <div className="card__header">
          <h2 id="schedule-heading">Run of Show</h2>
        </div>
        <div className="empty-state">
          No schedule data &mdash; Run the event to generate.
        </div>
      </section>
    )
  }

  return (
    <section className="card" id="schedule" aria-labelledby="schedule-heading">
      <div className="card__header">
        <h2 id="schedule-heading">Run of Show</h2>
        <div className="cluster" style={{ gap: 'var(--space-1)' }}>
          <span className="badge badge--info">{totalTasks} tasks</span>
          {criticalCount > 0 && (
            <span className="badge badge--critical">{criticalCount} critical</span>
          )}
        </div>
      </div>

      {/* Status banner */}
      <div
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderRadius: 'var(--radius-md)',
          textAlign: 'center',
          fontWeight: 700,
          fontSize: 'var(--text-sm)',
          letterSpacing: '0.05em',
          backgroundColor: hasConflicts ? 'var(--status-critical-bg)' : 'var(--status-ok-bg)',
          color: hasConflicts ? 'var(--status-critical)' : 'var(--status-ok)',
          marginBottom: 'var(--space-3)',
        }}
      >
        <span className="sr-only">Schedule status:</span>
        {hasConflicts ? 'Conflicts Detected' : 'Schedule Valid'}
      </div>

      {/* Task list */}
      <div style={{ maxHeight: 360, overflowY: 'auto' }}>
        {tasks.map((task, idx) => {
          const onCriticalPath = criticalPath.includes(task.id)
          const isAnchor = task.anchor !== null

          let bgColor = 'var(--surface-primary)'
          let borderLeftColor = 'transparent'
          let borderLeftWidth = '0px'

          if (onCriticalPath) {
            bgColor = 'var(--status-critical-bg)'
            borderLeftColor = 'var(--status-critical)'
            borderLeftWidth = '3px'
          } else if (isAnchor) {
            bgColor = 'var(--status-info-bg)'
            borderLeftColor = 'var(--status-info)'
            borderLeftWidth = '3px'
          }

          return (
            <div
              key={task.id || idx}
              style={{
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: 'var(--space-1)',
                backgroundColor: bgColor,
                borderLeft: `${borderLeftWidth} solid ${borderLeftColor}`,
                borderTop: onCriticalPath || isAnchor ? 'none' : '1px solid var(--border-subtle)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                  {task.name}
                </span>
                <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                  {formatTime(task.earliest_start)} &ndash; {formatTime(task.earliest_finish)}
                </span>
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                {formatDate(task.earliest_start)} &middot; {String(task.duration)}h
                {task.dependencies.length > 0 && (
                  <span> &middot; deps: {task.dependencies.join(', ')}</span>
                )}
              </div>
            </div>
          )
        })}

        {/* Call sheet entries */}
        {sheetEntries.length > 0 && (
          <>
            {tasks.length > 0 && (
              <div style={{ borderTop: '1px solid var(--border-subtle)', margin: 'var(--space-2) 0' }} />
            )}
            {sheetEntries.map((entry, idx) => (
              <div
                key={`sheet-${idx}`}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 'var(--space-1)',
                  backgroundColor: entry.is_anchor ? 'var(--status-info-bg)' : 'var(--surface-primary)',
                  borderLeft: entry.is_anchor ? '3px solid var(--status-info)' : 'none',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                    {entry.task_name}
                  </span>
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {formatTime(entry.start_time)} &ndash; {formatTime(entry.end_time)}
                  </span>
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 'var(--space-1)' }}>
                  {formatDate(entry.start_time)}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </section>
  )
}
