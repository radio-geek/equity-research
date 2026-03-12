/** Horizontal value chain flowchart: stages as nodes; highlight one or more company nodes; show 2–3 line description below. */
interface ValueChainFlowchartProps {
  stages: string[]
  companyStageIndex?: number
  companyStageIndices?: number[]
  companyPosition?: string
  companyPositionDescription?: string
}

function toHighlightSet(
  stages: string[],
  indices?: number[],
  single?: number
): Set<number> {
  const list = indices ?? (single != null && Number.isInteger(single) ? [single] : [])
  const set = new Set<number>()
  for (const i of list) {
    if (Number.isInteger(i) && i >= 0 && i < stages.length) set.add(i)
  }
  return set
}

export function ValueChainFlowchart({
  stages,
  companyStageIndex,
  companyStageIndices,
  companyPosition,
  companyPositionDescription,
}: ValueChainFlowchartProps) {
  if (!stages?.length) return null

  const highlightSet = toHighlightSet(stages, companyStageIndices, companyStageIndex)
  const spansAll = highlightSet.size === stages.length && stages.length > 0

  return (
    <div>
      {spansAll && (
        <p
          style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            color: 'var(--accent)',
            margin: '0 0 0.75rem 0',
            letterSpacing: '0.02em',
          }}
        >
          Spans full value chain
        </p>
      )}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.75rem',
          marginBottom: companyPositionDescription || companyPosition ? '1.25rem' : 0,
          ...(spansAll
            ? {
                padding: '0.75rem 1rem',
                borderRadius: 8,
                background: 'rgba(15, 118, 110, 0.06)',
                border: '1px solid rgba(15, 118, 110, 0.25)',
              }
            : {}),
        }}
      >
        {stages.map((stage, i) => {
          const isCompany = highlightSet.has(i)
          return (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span
                style={{
                  padding: '0.5rem 0.875rem',
                  borderRadius: 8,
                  fontSize: '0.9rem',
                  fontWeight: isCompany ? 600 : 500,
                  background: spansAll
                    ? 'rgba(15, 118, 110, 0.1)'
                    : isCompany
                      ? 'rgba(15, 118, 110, 0.14)'
                      : 'var(--surface)',
                  border: spansAll
                    ? '1px solid rgba(15, 118, 110, 0.3)'
                    : isCompany
                      ? '2px solid var(--accent)'
                      : '1px solid var(--border)',
                  color: 'var(--text)',
                  position: 'relative',
                }}
              >
                {stage}
                {isCompany && companyPosition && !spansAll && (
                  <span
                    style={{
                      display: 'block',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      color: 'var(--accent)',
                      marginTop: '0.2rem',
                      letterSpacing: '0.02em',
                    }}
                  >
                    — {companyPosition}
                  </span>
                )}
              </span>
              {i < stages.length - 1 && (
                <span style={{ color: 'var(--textMuted)', fontSize: '1rem' }} aria-hidden>→</span>
              )}
            </span>
          )
        })}
      </div>
      {companyPositionDescription && (
        <p
          style={{
            fontSize: '0.9rem',
            color: 'var(--text)',
            margin: 0,
            padding: '0.75rem 1rem',
            background: 'rgba(15, 118, 110, 0.06)',
            borderLeft: '4px solid var(--accent)',
            borderRadius: 4,
            lineHeight: 1.6,
          }}
        >
          {companyPositionDescription}
        </p>
      )}
    </div>
  )
}
