import { useEffect, useRef, useState } from 'react'
import {
  getTradeJournalEntries,
  addTradeJournalEntry,
  suggest,
  TradeJournalEntry,
  type SymbolSuggestion,
} from '../api'

const DEBOUNCE_MS = 200

interface TradeJournalModalProps {
  onClose: () => void
}

export function TradeJournalModal({ onClose }: TradeJournalModalProps) {
  const [entries, setEntries] = useState<TradeJournalEntry[]>([])
  const [loadPhase, setLoadPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [view, setView] = useState<'list' | 'add'>('list')

  // Symbol search
  const [symbolQuery, setSymbolQuery] = useState('')
  const [symbol, setSymbol] = useState('')
  const [suggestions, setSuggestions] = useState<SymbolSuggestion[]>([])
  const [suggestOpen, setSuggestOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [action, setAction] = useState<'buy' | 'sell'>('buy')
  const [tradeDate, setTradeDate] = useState('')
  const [thesis, setThesis] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [formPhase, setFormPhase] = useState<'idle' | 'submitting'>('idle')

  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  useEffect(() => {
    getTradeJournalEntries()
      .then((data) => { setEntries(data); setLoadPhase('ready') })
      .catch(() => setLoadPhase('error'))
  }, [])

  // Debounced suggest fetch
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const q = symbolQuery.trim()
    if (q.length < 1) { setSuggestions([]); setSuggestOpen(false); return }
    debounceRef.current = setTimeout(async () => {
      const list = await suggest(q).catch(() => [])
      setSuggestions(list)
      setHighlight(0)
      setSuggestOpen(list.length > 0)
    }, DEBOUNCE_MS)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [symbolQuery])

  const selectSuggestion = (s: SymbolSuggestion) => {
    setSymbol(s.symbol)
    setSymbolQuery(`${s.symbol} — ${s.name}`)
    setSuggestOpen(false)
    setSuggestions([])
  }

  const handleSymbolKeyDown = (e: React.KeyboardEvent) => {
    if (!suggestOpen || suggestions.length === 0) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight((h) => (h < suggestions.length - 1 ? h + 1 : 0)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight((h) => (h > 0 ? h - 1 : suggestions.length - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); selectSuggestion(suggestions[highlight]) }
    else if (e.key === 'Escape') { setSuggestOpen(false) }
  }

  const symbolsWithBuy = new Set(entries.filter((e) => e.action === 'buy').map((e) => e.symbol))

  const grouped: Record<string, TradeJournalEntry[]> = {}
  for (const entry of entries) {
    if (!grouped[entry.symbol]) grouped[entry.symbol] = []
    grouped[entry.symbol].push(entry)
  }
  const symbols = Object.keys(grouped).sort()

  const resetForm = () => {
    setSymbol(''); setSymbolQuery(''); setSuggestions([]); setSuggestOpen(false)
    setAction('buy'); setTradeDate(''); setThesis(''); setFormError(null)
  }

  const handleAdd = async () => {
    setFormError(null)
    const sym = symbol.trim().toUpperCase()
    if (!sym)           { setFormError('Please search and select a stock.'); return }
    if (!tradeDate)     { setFormError('Trade date is required.'); return }
    if (!thesis.trim()) { setFormError('Thesis is required.'); return }
    if (action === 'sell' && !symbolsWithBuy.has(sym)) {
      setFormError(`No buy entry exists for ${sym}. Add a buy entry first.`)
      return
    }
    setFormPhase('submitting')
    try {
      const { entry } = await addTradeJournalEntry({ symbol: sym, action, trade_date: tradeDate, thesis: thesis.trim() })
      setEntries((prev) => [...prev, entry])
      resetForm()
      setView('list')
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setFormPhase('idle')
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 6,
    padding: '0.6rem 0.75rem',
    fontSize: '0.88rem',
    color: '#e2e8f0',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  }

  const labelStyle: React.CSSProperties = {
    fontSize: '0.82rem',
    fontWeight: 600,
    color: '#94a3b8',
    marginBottom: '0.35rem',
    display: 'block',
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Trade Journal"
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.6)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: '#1a1a2e',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 12,
        width: '100%', maxWidth: 540,
        maxHeight: '88vh', overflowY: 'auto',
        padding: '1.75rem',
        display: 'flex', flexDirection: 'column', gap: '1.25rem',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {view === 'add' && (
              <button type="button" onClick={() => { setView('list'); setFormError(null) }}
                aria-label="Back" style={{ background: 'none', border: 'none', cursor: 'pointer',
                  color: '#94a3b8', fontSize: '1.1rem', padding: '0 0.25rem' }}>
                ←
              </button>
            )}
            <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#f1f5f9' }}>
              {view === 'list' ? 'Trade Journal' : 'Log Entry'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {view === 'list' && (
              <button type="button" onClick={() => setView('add')} style={{
                background: '#4f46e5', border: 'none', borderRadius: 6,
                padding: '0.35rem 0.85rem', fontSize: '0.82rem',
                cursor: 'pointer', color: '#fff', fontWeight: 600,
              }}>
                + Log entry
              </button>
            )}
            <button type="button" onClick={onClose} aria-label="Close" style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: '1.3rem', color: '#64748b', lineHeight: 1, padding: '0 0.2rem',
            }}>
              ×
            </button>
          </div>
        </div>

        {/* List view */}
        {view === 'list' && (
          <>
            {loadPhase === 'loading' && (
              <div style={{ textAlign: 'center', padding: '2.5rem 0', color: '#64748b', fontSize: '0.9rem' }}>
                Loading…
              </div>
            )}
            {loadPhase === 'error' && (
              <div style={{ color: '#f87171', fontSize: '0.85rem' }}>
                Failed to load journal. Please close and try again.
              </div>
            )}
            {loadPhase === 'ready' && symbols.length === 0 && (
              <div style={{ color: '#64748b', fontSize: '0.88rem', textAlign: 'center', padding: '2.5rem 0' }}>
                No entries yet. Click "+ Log entry" to record your first trade.
              </div>
            )}
            {loadPhase === 'ready' && symbols.map((sym) => (
              <div key={sym} style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '1rem' }}>
                <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#f1f5f9', marginBottom: '0.5rem' }}>
                  {sym}
                </div>
                {grouped[sym].map((entry) => (
                  <div key={entry.id} style={{
                    padding: '0.6rem 0',
                    borderTop: '1px solid rgba(255,255,255,0.06)',
                    display: 'flex', flexDirection: 'column', gap: '0.3rem',
                  }}>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span style={{
                        fontSize: '0.72rem', fontWeight: 700,
                        padding: '0.15rem 0.5rem', borderRadius: 4,
                        background: entry.action === 'buy' ? 'rgba(22,101,52,0.6)' : 'rgba(127,29,29,0.6)',
                        color: entry.action === 'buy' ? '#86efac' : '#fca5a5',
                      }}>
                        {entry.action.toUpperCase()}
                      </span>
                      <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{entry.trade_date}</span>
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.5 }}>
                      {entry.thesis}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </>
        )}

        {/* Add form */}
        {view === 'add' && (
          <>
            {/* Symbol search */}
            <div style={{ display: 'flex', flexDirection: 'column', position: 'relative' }}>
              <label style={labelStyle}>Stock <span style={{ color: '#f87171' }}>*</span></label>
              <input
                type="text"
                value={symbolQuery}
                onChange={(e) => { setSymbolQuery(e.target.value); setSymbol('') }}
                onKeyDown={handleSymbolKeyDown}
                onFocus={() => suggestions.length > 0 && setSuggestOpen(true)}
                placeholder="Search by name or symbol…"
                style={inputStyle}
                autoComplete="off"
              />
              {suggestOpen && suggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
                  background: '#1e1e2e', border: '1px solid rgba(255,255,255,0.12)',
                  borderRadius: 6, marginTop: 4, maxHeight: 220, overflowY: 'auto',
                }}>
                  {suggestions.map((s, i) => (
                    <div
                      key={s.symbol}
                      onMouseDown={() => selectSuggestion(s)}
                      style={{
                        padding: '0.55rem 0.75rem',
                        cursor: 'pointer',
                        background: i === highlight ? 'rgba(79,70,229,0.25)' : 'transparent',
                        display: 'flex', gap: '0.6rem', alignItems: 'center',
                        borderBottom: i < suggestions.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                      }}
                      onMouseEnter={() => setHighlight(i)}
                    >
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#f1f5f9', minWidth: 80 }}>
                        {s.symbol}
                      </span>
                      <span style={{ fontSize: '0.82rem', color: '#94a3b8', overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.name}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Action */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={labelStyle}>Action <span style={{ color: '#f87171' }}>*</span></label>
              <select value={action} onChange={(e) => setAction(e.target.value as 'buy' | 'sell')}
                style={inputStyle}>
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
              {action === 'sell' && symbol && !symbolsWithBuy.has(symbol) && (
                <div style={{ fontSize: '0.78rem', color: '#fbbf24', marginTop: '0.35rem' }}>
                  No buy entry for {symbol} yet — a sell requires at least one prior buy.
                </div>
              )}
            </div>

            {/* Trade date */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={labelStyle}>Trade date <span style={{ color: '#f87171' }}>*</span></label>
              <input type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)}
                style={inputStyle} />
            </div>

            {/* Thesis */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={labelStyle}>Thesis <span style={{ color: '#f87171' }}>*</span></label>
              <textarea value={thesis} onChange={(e) => setThesis(e.target.value)}
                rows={4} placeholder="Why did you make this trade?"
                style={{ ...inputStyle, resize: 'vertical' }} />
            </div>

            {formError && (
              <div style={{ fontSize: '0.85rem', color: '#f87171' }}>{formError}</div>
            )}

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button type="button" onClick={() => { resetForm(); setView('list') }} style={{
                background: 'transparent', border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: 6, padding: '0.45rem 1rem',
                fontSize: '0.88rem', cursor: 'pointer', color: '#94a3b8',
              }}>
                Cancel
              </button>
              <button type="button" onClick={handleAdd} disabled={formPhase === 'submitting'} style={{
                background: '#4f46e5', border: 'none', borderRadius: 6,
                padding: '0.45rem 1.25rem', fontSize: '0.88rem',
                cursor: formPhase === 'submitting' ? 'not-allowed' : 'pointer',
                color: '#fff', fontWeight: 600,
                opacity: formPhase === 'submitting' ? 0.6 : 1,
              }}>
                {formPhase === 'submitting' ? 'Saving…' : 'Save'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
