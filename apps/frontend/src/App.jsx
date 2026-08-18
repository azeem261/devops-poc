import { useCallback, useEffect, useState } from 'react'

const STATUS_LABELS = {
  pending: 'Pending',
  processing: 'Processing…',
  done: 'Done',
}

export default function App() {
  const [tasks, setTasks] = useState([])
  const [title, setTitle] = useState('')
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
      body: JSON.stringify({ title: title.trim() }),
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
        <h4 className="subtitle">
          Create a task, watch the worker pick it up and complete it.
        </h4>
      </header>

      <form onSubmit={addTask} className="task-form">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What needs doing?"
          maxLength={200}
        />
        <button type="submit">Add task</button>
      </form>

      {error && <p className="error">Cannot reach API: {error}</p>}

      <ul className="task-list">
        {tasks.map((t) => (
          <li key={t.id} className={`task task-${t.status}`}>
            <span className="task-title">{t.title}</span>
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
