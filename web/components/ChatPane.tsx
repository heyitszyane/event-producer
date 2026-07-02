export interface ChatMessage {
  role: string
  content: string
  agent?: string
}

interface ChatPaneProps {
  messages: ChatMessage[]
  showHeader?: boolean
}

export default function ChatPane({ messages, showHeader = true }: ChatPaneProps) {
  return (
    <section className="chat-box" id="chat" aria-labelledby="chat-heading">
      {showHeader && (
        <div className="card__header" style={{ padding: 'var(--space-3)', paddingBottom: 0 }}>
          <h2 id="chat-heading" style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)' }}>
            Production Log
          </h2>
          {messages.length > 0 && (
            <span className="badge badge--info">{messages.length}</span>
          )}
        </div>
      )}

      <div style={{ padding: 'var(--space-3)' }}>
        <div
          className="chat-messages"
          role="log"
          aria-live="polite"
          aria-label="Production log messages"
        >
          {messages.length === 0 && (
            <p style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', margin: 0 }}>
              No messages — run the event to see the production log.
            </p>
          )}
          {messages.map((msg, idx) => {
            const isSystem = msg.role === 'system'
            const isAgent = msg.role === 'agent'
            const agentName = msg.agent || 'System'

            return (
              <div
                key={idx}
                style={{
                  marginBottom: 'var(--space-2)',
                  padding: 'var(--space-2) var(--space-3)',
                  fontSize: 'var(--text-sm)',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: isSystem ? 'var(--surface-tertiary)' : 'var(--accent-muted)',
                  color: 'var(--text-primary)',
                  borderLeft: isSystem
                    ? '3px solid var(--text-tertiary)'
                    : '3px solid var(--accent)',
                }}
              >
                <div style={{
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: isSystem ? 'var(--text-tertiary)' : 'var(--accent)',
                  marginBottom: 'var(--space-1)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.03em',
                }}>
                  {agentName}
                </div>
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {msg.content}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
