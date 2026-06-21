import { useState } from 'react'

// In production, set NEXT_PUBLIC_API_BASE_URL to the Cloud Run backend URL.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPane() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  async function handleSend() {
    const trimmed = input.trim()
    if (!trimmed) return

    const userMessage: ChatMessage = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Demo-User': 'demo-user',
        },
        body: JSON.stringify({ message: trimmed }),
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = await res.json()
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: data.reply || 'No response',
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !loading) {
      handleSend()
    }
  }

  return (
    <section className="chat-box" id="chat" aria-labelledby="chat-heading">
      {/* Collapsible header */}
      <button
        onClick={() => setExpanded((prev) => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          background: 'none',
          border: 'none',
          padding: 'var(--space-3)',
          cursor: 'pointer',
        }}
        aria-expanded={expanded}
      >
        <h2 id="chat-heading" style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)' }}>
          Chat
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          {messages.length > 0 && (
            <span className="badge badge--info">{messages.length}</span>
          )}
          <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>
            {expanded ? '▲' : '▼'}
          </span>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div style={{ padding: '0 var(--space-3) var(--space-3)' }}>
          <div
            className="chat-messages"
            role="log"
            aria-live="polite"
            aria-label="Chat messages"
          >
            {messages.length === 0 && (
              <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', margin: 0 }}>
                No messages yet. Type something to get started.
              </p>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  marginBottom: 'var(--space-2)',
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div className={`chat-msg ${msg.role === 'user' ? 'chat-msg--user' : 'chat-msg--assistant'}`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', margin: 0, fontStyle: 'italic' }}>
                Thinking...
              </p>
            )}
          </div>

          {error && (
            <div className="error-bar">
              <span>{error}</span>
              <button
                onClick={() => setError(null)}
                style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 'var(--text-md)', lineHeight: 1 }}
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}

          <div className="chat-input-row">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              disabled={loading}
              className="input"
              aria-label="Chat message input"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="btn btn--primary"
            >
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
