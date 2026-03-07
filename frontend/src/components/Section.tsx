import { ReactNode } from 'react'

interface SectionProps {
  title?: string
  children?: ReactNode
  id?: string
  className?: string
}

export function Section({ title, children, id, className = '' }: SectionProps) {
  return (
    <section id={id} className={className} style={{ marginBottom: '2rem' }}>
      {title && (
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem', color: 'inherit' }}>
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}
