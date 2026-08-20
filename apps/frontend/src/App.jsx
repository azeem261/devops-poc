import { useCallback, useEffect, useState } from 'react'

const STATUS_LABELS = {
  pending: 'Pending',
  processing: 'Processing…',
  done: 'Done',
  failed: 'Failed',
}

const PRIORITY_LABELS = { high: 'High', normal: 'Normal', low: 'Low' }

function StatCard({ label, value, tone }) {
  return (
    <div className={`stat-card ${tone ? `stat-${tone}` : ''}`}>
      <span className="stat-value">{value ?? '—'}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

export default function App() {
  const [tasks, setTasks] = useState([])
  const [stats, setStats] = useState(null)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState('normal')
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/tasks')
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      setTasks(await res.json())
      setError(null)
    } catch (err) {
      setError(err.message)
    }
    try {
      const res = await fetch('/api/stats')
      setStats(res.ok ? await res.json() : null)
    } catch {
      setStats(null)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 2500)
    return () => clearInterval(id)
  }, [refresh])

  async function addTask(e) {
    e.preventDefault()
    if (!title.trim()) return
    await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title.trim(), priority }),
    })
    setTitle('')
    refresh()
  }

  async function deleteTask(id) {
    await fetch(`/api/tasks/${id}`, { method: 'DELETE' })
    refresh()
  }

  return (
    <main className="container">
      <header>
        <h1>TaskFlow</h1>
        <h3 className="subtitle">
          Create a task, watch the worker pick it up — some fail and retry.
        </h3>
      </header>

      <div className="stats-row">
        <StatCard label="Total" value={stats?.total} />
        <StatCard label="Pending" value={stats?.pending} tone="pending" />
        <StatCard label="Processing" value={stats?.processing} tone="processing" />
        <StatCard label="Done" value={stats?.done} tone="done" />
        <StatCard label="Failed" value={stats?.failed} tone="failed" />
        <StatCard
          label="Avg completion"
          value={
            stats?.avg_completion_seconds != null
              ? `${stats.avg_completion_seconds}s`
              : null
          }
        />
      </div>

      <form onSubmit={addTask} className="task-form">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What needs doing?"
          maxLength={200}
        />
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>
        <button type="submit">Add task</button>
      </form>

      {error && <p className="error">Cannot reach API: {error}</p>}

      <ul className="task-list">
        {tasks.map((t) => (
          <li key={t.id} className={`task task-${t.status}`}>
            <span className={`prio prio-${t.priority}`}>
              {PRIORITY_LABELS[t.priority] ?? t.priority}
            </span>
            <span className="task-title" title={t.error ?? undefined}>
              {t.title}
              {t.attempts > 1 && (
                <span className="attempts"> · attempt {t.attempts}</span>
              )}
            </span>
            <span className={`badge badge-${t.status}`}>
              {STATUS_LABELS[t.status] ?? t.status}
            </span>
            <button className="delete" onClick={() => deleteTask(t.id)} title="Delete">
              ✕
            </button>
          </li>
        ))}
        {tasks.length === 0 && !error && (
          <li className="empty">No tasks yet — add one above.</li>
        )}
      </ul>
    </main>
  )
}
