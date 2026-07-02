import { useEffect, useMemo, useState } from 'react'

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

interface DraftTask {
  id: string
  name: string
  start: string
  end: string
  duration: string
  owner: string
  dependencies: string
  status: string
  notes: string
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
  const taskNamesById = useMemo(() => {
    const entries = (schedule?.ordered_tasks || []).map((task) => [task.id, task.name] as const)
    return new Map(entries)
  }, [schedule])

  const sourceTasks = useMemo<DraftTask[]>(() => (schedule?.ordered_tasks || []).map((task, idx) => ({
    id: task.id || `task-${idx}`,
    name: task.name,
    start: task.earliest_start,
    end: task.earliest_finish,
    duration: String(task.duration),
    owner: task.anchor || 'Production',
    dependencies: task.dependencies.map((dependency) => taskNamesById.get(dependency) || dependency).join(', '),
    status: schedule?.critical_path?.includes(task.id) ? 'Critical path' : 'Scheduled',
    notes: task.lead_time ? `Lead time: ${task.lead_time}` : '',
  })), [schedule, taskNamesById])
  const [draftTasks, setDraftTasks] = useState<DraftTask[]>(sourceTasks)
  const [editing, setEditing] = useState<DraftTask | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    setDraftTasks(sourceTasks)
  }, [sourceTasks])

  const tasks = draftTasks
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

      <div className="block block--info">
        Schedule edits are frontend drafts for review. Backend recompute remains the source of deterministic schedule truth.
      </div>

      <table className="data-table run-sheet-table">
        <thead>
          <tr>
            <th scope="col">Task</th>
            <th scope="col">Window</th>
            <th scope="col">Duration</th>
            <th scope="col">Owner/Role</th>
            <th scope="col">Dependency</th>
            <th scope="col">Status</th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
        {tasks.map((task, idx) => {
          return (
            <tr
              key={task.id || idx}
              className={criticalPath.includes(task.id) ? 'run-sheet-row--critical' : ''}
            >
              <td data-label="Task"><button className="table-cell-button" type="button" onClick={() => setEditing(task)}>{task.name}</button></td>
              <td data-label="Window"><button className="table-cell-button mono" type="button" onClick={() => setEditing(task)}>{formatDate(task.start)} {formatTime(task.start)} - {formatTime(task.end)}</button></td>
              <td data-label="Duration"><button className="table-cell-button" type="button" onClick={() => setEditing(task)}>{task.duration}h</button></td>
              <td data-label="Owner/Role"><button className="table-cell-button" type="button" onClick={() => setEditing(task)}>{task.owner}</button></td>
              <td data-label="Dependency"><button className="table-cell-button" type="button" onClick={() => setEditing(task)}>{task.dependencies || '-'}</button></td>
              <td data-label="Status"><button className="table-cell-button" type="button" onClick={() => setEditing(task)}>{task.status}</button></td>
              <td data-label="Action"><button className="btn btn--ghost btn--sm" type="button" onClick={() => setEditing(task)}>Edit</button></td>
            </tr>
          )
        })}
        </tbody>
      </table>

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
      {editing && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="run-sheet-modal-title">
          <div className="modal-card">
            <div className="war-panel__header">
              <h2 id="run-sheet-modal-title">Edit Run Sheet Task</h2>
              <span className="badge badge--warn">draft only</span>
            </div>
            <div className="modal-grid">
              <label className="field-compact"><span>Task name</span><input className="input" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></label>
              <label className="field-compact"><span>Start time/window</span><input className="input" value={editing.start} onChange={(e) => setEditing({ ...editing, start: e.target.value })} /></label>
              <label className="field-compact"><span>End time/window</span><input className="input" value={editing.end} onChange={(e) => setEditing({ ...editing, end: e.target.value })} /></label>
              <label className="field-compact"><span>Duration</span><input className="input" value={editing.duration} onChange={(e) => setEditing({ ...editing, duration: e.target.value })} /></label>
              <label className="field-compact"><span>Owner/role</span><input className="input" value={editing.owner} onChange={(e) => setEditing({ ...editing, owner: e.target.value })} /></label>
              <label className="field-compact"><span>Dependencies</span><input className="input" value={editing.dependencies} onChange={(e) => setEditing({ ...editing, dependencies: e.target.value })} /></label>
              <label className="field-compact"><span>Status</span><input className="input" value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })} /></label>
              <label className="field-compact modal-grid__full"><span>Notes</span><textarea className="input" value={editing.notes} onChange={(e) => setEditing({ ...editing, notes: e.target.value })} rows={3} /></label>
            </div>
            {confirmDelete && <div className="block block--warn">Delete this draft row? This affects the visible draft table only.</div>}
            <div className="cluster">
              <button className="btn btn--primary" type="button" onClick={() => {
                setDraftTasks((prev) => prev.map((task) => task.id === editing.id ? editing : task))
                setEditing(null)
                setConfirmDelete(false)
              }}>Save</button>
              <button className="btn btn--reject" type="button" onClick={() => {
                if (!confirmDelete) {
                  setConfirmDelete(true)
                  return
                }
                setDraftTasks((prev) => prev.filter((task) => task.id !== editing.id))
                setEditing(null)
                setConfirmDelete(false)
              }}>Delete</button>
              <button className="btn btn--ghost" type="button" onClick={() => {
                setEditing(null)
                setConfirmDelete(false)
              }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
