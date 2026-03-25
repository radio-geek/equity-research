import { useState, useEffect } from 'react'
import { submitDetailedFeedback } from '../api'

const REPORT_SECTIONS = [
  'Company Overview',
  'Management & Board',
  'Governance & auditor review',
  '5-Year Financial Trend',
  'Concall Evaluation',
  'Sectoral Headwinds & Tailwinds',
  'Green & Red Flags in Financial Data',
]

interface FeedbackModalProps {
  symbol: string
  onClose: () => void
}

function StarRating({
  value,
  onChange,
}: {
  value: number
  onChange: (v: number) => void
}) {
  const [hovered, setHovered] = useState(0)
  const active = hovered || value
  return (
    <div style={{ display: 'flex', gap: '0.25rem' }}>
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          aria-label={`${star} star`}
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '0 1px',
            fontSize: '1.35rem',
            color: star <= active ? 'var(--accent, #f59e0b)' : 'var(--border, #d1d5db)',
            transition: 'color 0.1s',
          }}
        >
          ★
        </button>
      ))}
    </div>
  )
}

export function FeedbackModal({ symbol, onClose }: FeedbackModalProps) {
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [suggestion, setSuggestion] = useState('')
  const [phase, setPhase] = useState<'form' | 'submitting' | 'done'>('form')

  const setRating = (section: string, value: number) => {
    setRatings((prev) => ({ ...prev, [section]: value }))
  }

  const handleSubmit = async () => {
    setPhase('submitting')
    try {
      await submitDetailedFeedback({
        symbol,
        section_ratings: ratings,
        suggestion: suggestion.trim() || null,
      })
    } catch {
      // ignore — still show thank-you
    }
    setPhase('done')
    setTimeout(() => onClose(), 2200)
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Feedback"
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
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🎉</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>
              Thank you for your feedback!
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--textMuted)', marginTop: '0.4rem' }}>
              Closing in a moment…
            </div>
          </div>
        ) : phase === 'submitting' ? (
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <div className="loader-chart-bars" aria-hidden style={{ justifyContent: 'center', display: 'flex', gap: 4 }}>
              <span /><span /><span /><span /><span />
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--textMuted)', marginTop: '1rem' }}>
              Submitting…
            </div>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text)' }}>
                Rate this report
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
              Rate each section from 1 (poor) to 5 (excellent). Ratings are optional.
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {REPORT_SECTIONS.map((section) => (
                <div
                  key={section}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem',
                  }}
                >
                  <span style={{ fontSize: '0.88rem', color: 'var(--text)', flex: 1 }}>
                    {section}
                  </span>
                  <StarRating
                    value={ratings[section] ?? 0}
                    onChange={(v) => setRating(section, v)}
                  />
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label
                style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}
              >
                Suggestions or improvements
              </label>
              <textarea
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                rows={3}
                placeholder="Tell us what we could improve or add…"
                style={{
                  width: '100%',
                  background: 'var(--bg, #0f0f17)',
                  border: '1px solid var(--border, #374151)',
                  borderRadius: 6,
                  padding: '0.6rem 0.75rem',
                  fontSize: '0.88rem',
                  color: 'var(--text)',
                  resize: 'vertical',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
              />
            </div>

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
                Submit
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
