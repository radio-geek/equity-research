import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { submitContactMessage } from '../api'

interface ContactModalProps {
  onClose: () => void
}

export function ContactModal({ onClose }: ContactModalProps) {
  const { user } = useAuth()

  const [name, setName] = useState(user?.name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<'form' | 'submitting' | 'done'>('form')

  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const handleSubmit = async () => {
    setError(null)
    if (!name.trim() || !email.trim() || !message.trim()) {
      setError('All fields are required.')
      return
    }
    setPhase('submitting')
    try {
      await submitContactMessage({ name: name.trim(), email: email.trim(), message: message.trim() })
      setPhase('done')
      setTimeout(() => onClose(), 2200)
    } catch (e: unknown) {
      setPhase('form')
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: 'var(--bg, #0f0f17)',
    border: '1px solid var(--border, #374151)',
    borderRadius: 6,
    padding: '0.6rem 0.75rem',
    fontSize: '0.88rem',
    color: 'var(--text)',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Contact Support"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.55)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        style={{
          background: 'var(--surface, #1e1e2e)',
          border: '1px solid var(--border, #374151)',
          borderRadius: 12,
          width: '100%',
          maxWidth: 480,
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: '1.75rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem',
        }}
      >
        {phase === 'done' ? (
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>✅</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>
              Message sent!
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--textMuted)', marginTop: '0.4rem' }}>
              We'll get back to you shortly.
            </div>
          </div>
        ) : phase === 'submitting' ? (
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <div className="loader-chart-bars" aria-hidden style={{ justifyContent: 'center', display: 'flex', gap: 4 }}>
              <span /><span /><span /><span /><span />
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--textMuted)', marginTop: '1rem' }}>
              Sending…
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text)' }}>
                Contact Support
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '1.2rem',
                  color: 'var(--textMuted)',
                  lineHeight: 1,
                }}
              >
                ×
              </button>
            </div>

            <div style={{ fontSize: '0.82rem', color: 'var(--textMuted)' }}>
              Have a question or issue? Fill in the form and we'll get back to you.
            </div>

            {/* Name */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
                Name <span style={{ color: '#e57' }}>*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                style={inputStyle}
              />
            </div>

            {/* Email */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
                Email <span style={{ color: '#e57' }}>*</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                style={inputStyle}
              />
            </div>

            {/* Message */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
                Message <span style={{ color: '#e57' }}>*</span>
              </label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                placeholder="Describe your question or issue…"
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            </div>

            {/* Error */}
            {error && (
              <div style={{ fontSize: '0.85rem', color: '#f87171' }}>
                {error}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '0.45rem 1rem',
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  color: 'var(--text)',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                style={{
                  background: 'var(--accent, #6366f1)',
                  border: 'none',
                  borderRadius: 6,
                  padding: '0.45rem 1.25rem',
                  fontSize: '0.88rem',
                  cursor: 'pointer',
                  color: '#fff',
                  fontWeight: 600,
                }}
              >
                Send
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
