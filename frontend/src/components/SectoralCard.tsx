import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface SectoralCardProps {
  headwinds?: string[]
  tailwinds?: string[]
  style?: React.CSSProperties
}

function MarkdownBullet({ text }: { text: string }) {
  return (
    <div className="report-markdown sectoral-bullet">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  )
}

export function SectoralCard({ headwinds, tailwinds, style = {} }: SectoralCardProps) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', ...style }}>
      <div style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 8, padding: '1rem' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--green)' }}>Tailwinds</div>
        <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem', color: 'var(--text)' }}>
          {(tailwinds || []).map((t, i) => (
            <li key={i}>
              <MarkdownBullet text={t} />
            </li>
          ))}
        </ul>
      </div>
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '1rem' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--red)' }}>Headwinds</div>
        <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem', color: 'var(--text)' }}>
          {(headwinds || []).map((h, i) => (
            <li key={i}>
              <MarkdownBullet text={h} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
