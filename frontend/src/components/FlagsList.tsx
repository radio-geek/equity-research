interface FlagsListProps {
  greenFlags?: string[]
  redFlags?: string[]
  style?: React.CSSProperties
}

export function FlagsList({ greenFlags, redFlags, style = {} }: FlagsListProps) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', ...style }}>
      <div style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.25)', borderRadius: 8, padding: '1rem' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--green)' }}>Green flags</div>
        <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
          {(greenFlags || []).map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      </div>
      <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 8, padding: '1rem' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--red)' }}>Red flags</div>
        <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
          {(redFlags || []).map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      </div>
    </div>
  )
}
