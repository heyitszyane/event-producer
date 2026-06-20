import { useState } from 'react'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPane() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSend() {
    const trimmed = input.trim()
    if (!trimmed) return

    const userMessage: ChatMessage = { role: 'user', content: trimmed }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
    <div
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: 16,
        marginTop: 24,
        backgroundColor: '#ffffff',
      }}
    >
      <h2 style={{ margin: '0 0 12px 0', fontSize: 18, fontWeight: 600, color: '#111827' }}>
        Chat
      </h2>

      <div
        style={{
          border: '1px solid #e5e7eb',
          borderRadius: 6,
          padding: 12,
          minHeight: 160,
          maxHeight: 300,
          overflowY: 'auto',
          marginBottom: 12,
          backgroundColor: '#f9fafb',
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: '#9ca3af', fontSize: 14, margin: 0 }}>
            No messages yet. Type something to get started.
          </p>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              marginBottom: 8,
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                display: 'inline-block',
                padding: '8px 12px',
                borderRadius: 12,
                maxWidth: '80%',
                fontSize: 14,
                backgroundColor: msg.role === 'user' ? '#2563eb' : '#e5e7eb',
                color: msg.role === 'user' ? '#ffffff' : '#111827',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <p style={{ color: '#9ca3af', fontSize: 13, margin: 0 }}>Thinking...</p>
        )}
      </div>

      {error && (
        <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 8 }}>
          Error: {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          disabled={loading}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid #d1d5db',
            borderRadius: 6,
            fontSize: 14,
            outline: 'none',
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            padding: '8px 16px',
            backgroundColor: loading || !input.trim() ? '#9ca3af' : '#2563eb',
            color: '#ffffff',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
