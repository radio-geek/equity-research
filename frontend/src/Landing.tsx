import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { suggest, type SymbolSuggestion } from './api'
import { trackEvent } from './analytics'
import { INDICES, REVIEWS } from './landingData'

const DEBOUNCE_MS = 280
const CAROUSEL_MS = 5000

export default function Landing() {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<SymbolSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const [reviewIndex, setReviewIndex] = useState(0)
  const navigate = useNavigate()
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const listRef = useRef<HTMLUListElement>(null)

  const fetchSuggestions = useCallback(async (q: string) => {
    if (!q.trim()) {
      setSuggestions([])
      return
    }
    setLoading(true)
    try {
      const list = await suggest(q)
      setSuggestions(list)
      setHighlight(0)
      setOpen(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => fetchSuggestions(query), DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, fetchSuggestions])

  useEffect(() => {
    const t = setInterval(() => {
      setReviewIndex((i) => (i + 1) % REVIEWS.length)
    }, CAROUSEL_MS)
    return () => clearInterval(t)
  }, [])

  const select = (s: SymbolSuggestion) => {
    setOpen(false)
    trackEvent('Report Requested', { symbol: s.symbol })
    navigate(`/${encodeURIComponent(s.symbol)}/report`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || suggestions.length === 0) {
      if (e.key === 'Enter' && query.trim()) fetchSuggestions(query.trim())
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((h) => (h < suggestions.length - 1 ? h + 1 : 0))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => (h > 0 ? h - 1 : suggestions.length - 1))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      select(suggestions[highlight])
      return
    }
    if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${highlight}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [highlight])

  const review = REVIEWS[reviewIndex]

  return (
    <div className="landing">
      <div className="landing-ticker">
        <div className="landing-ticker-inner">
          {INDICES.map((idx) => (
            <span key={idx.name} className="landing-ticker-item">
              <span className="ticker-name">{idx.name}</span>
              <span className="ticker-value">{idx.value}</span>
              <span className={`ticker-change ${idx.positive ? 'up' : 'down'}`}>{idx.change}</span>
            </span>
          ))}
        </div>
      </div>

      <header className="landing-header">
        <h1>Equity Research</h1>
        <p className="tagline">Search for a stock to generate a report</p>
      </header>

      <div className="search-wrap">
        <div className="search-inner">
          <input
            type="text"
            className="search-input"
            placeholder="Search by symbol or company name..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => suggestions.length > 0 && setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 200)}
            onKeyDown={handleKeyDown}
            aria-label="Search stocks"
            aria-autocomplete="list"
            aria-expanded={open}
            aria-controls="suggestions-list"
            id="search-input"
          />
          {loading && <span className="search-spinner" aria-hidden />}
        </div>
        {open && suggestions.length > 0 && (
          <ul
            id="suggestions-list"
            ref={listRef}
            className="suggestions-list"
            role="listbox"
            aria-label="Stock suggestions"
          >
            {suggestions.map((s, i) => (
              <li
                key={`${s.symbol}-${i}`}
                role="option"
                data-index={i}
                aria-selected={i === highlight}
                className={`suggestion-item ${i === highlight ? 'highlight' : ''}`}
                onMouseDown={(e) => {
                  e.preventDefault()
                  select(s)
                }}
              >
                <span className="suggestion-symbol">{s.symbol}</span>
                <span className="suggestion-name">{s.name}</span>
                <span className="suggestion-badge">NSE</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <section className="landing-reviews" aria-label="User reviews">
        <div className="review-card">
          <blockquote className="review-quote">"{review.quote}"</blockquote>
          <footer className="review-footer">
            <strong>{review.author}</strong>
            <span className="review-role">{review.role}</span>
          </footer>
        </div>
        <div className="review-dots">
          {REVIEWS.map((_, i) => (
            <button
              key={i}
              type="button"
              className={`review-dot ${i === reviewIndex ? 'active' : ''}`}
              onClick={() => setReviewIndex(i)}
              aria-label={`Review ${i + 1}`}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
