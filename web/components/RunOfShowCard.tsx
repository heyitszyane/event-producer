import React from 'react'

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
      hour: '2-digit',
      minute: '2-digit',
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
  if (!schedule && (!callSheet || callSheet.length === 0)) {
    return (
      <div style={cardStyle}>
        <h2 style={headingStyle}>Run of Show</h2>
        <p style={emptyStyle}>No schedule data</p>
      </div>
    )
  }

  const tasks = schedule?.ordered_tasks || []
  const sheetEntries = (callSheet || []).filter((entry) => {
    if (!schedule) return true
    return !tasks.some((t) => t.name === entry.task_name)
  })

  if (tasks.length === 0 && sheetEntries.length === 0) {
    return (
      <div style={cardStyle}>
        <h2 style={headingStyle}>Run of Show</h2>
        <p style={emptyStyle}>No tasks scheduled</p>
      </div>
    )
  }

  return (
    <div style={cardStyle}>
      <h2 style={headingStyle}>Run of Show</h2>

      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {tasks.map((task, idx) => {
          const onCriticalPath = schedule?.critical_path.includes(task.id)

          return (
            <div
              key={task.id || idx}
              style={{
                ...taskStyle,
                backgroundColor: onCriticalPath ? '#fef2f2' : '#f9fafb',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={taskNameStyle}>
                  {task.name}
                  {onCriticalPath && (
                    <span style={{ ...criticalBadge, marginLeft: 6 }}>critical</span>
                  )}
                </span>
                <span style={timeStyle}>
                  {formatTime(task.earliest_start)} – {formatTime(task.earliest_finish)}
                </span>
              </div>
              <div style={metaStyle}>
                {formatDate(task.earliest_start)} &middot; {String(task.duration)}h
                {task.dependencies.length > 0 && (
                  <span> &middot; deps: {task.dependencies.join(', ')}</span>
                )}
              </div>
            </div>
          )
        })}

        {sheetEntries.map((entry, idx) => (
          <div key={`sheet-${idx}`} style={{ ...taskStyle, backgroundColor: entry.is_anchor ? '#eff6ff' : '#f9fafb' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={taskNameStyle}>
                {entry.task_name}
                {entry.is_anchor && <span style={{ ...anchorBadge, marginLeft: 6 }}>anchor</span>}
              </span>
              <span style={timeStyle}>
                {formatTime(entry.start_time)} – {formatTime(entry.end_time)}
              </span>
            </div>
            <div style={metaStyle}>{formatDate(entry.start_time)}</div>
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

const taskStyle: React.CSSProperties = {
  padding: '10px 12px',
  borderRadius: 6,
  marginBottom: 6,
  border: '1px solid #e5e7eb',
}

const taskNameStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 14,
  color: '#111827',
}

const timeStyle: React.CSSProperties = {
  fontSize: 13,
  color: '#374151',
  fontFamily: 'monospace',
}

const metaStyle: React.CSSProperties = {
  fontSize: 11,
  color: '#6b7280',
  marginTop: 4,
}

const criticalBadge: React.CSSProperties = {
  display: 'inline-block',
  backgroundColor: '#dc2626',
  color: '#ffffff',
  fontSize: 10,
  padding: '1px 6px',
  borderRadius: 4,
  fontWeight: 600,
}

const anchorBadge: React.CSSProperties = {
  display: 'inline-block',
  backgroundColor: '#2563eb',
  color: '#ffffff',
  fontSize: 10,
  padding: '1px 6px',
  borderRadius: 4,
  fontWeight: 600,
}
