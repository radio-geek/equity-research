import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { accentByIndex } from '../../design-tokens'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  accentIndex?: number
  children: ReactNode
  dashed?: boolean
}

const cardBase =
  'rounded-3xl border-4 p-8 md:p-10 bg-muted/80 backdrop-blur-sm transition-all duration-300 ease-out hover:scale-[1.02] hover:rotate-1'

export function Card({ accentIndex = 0, dashed = false, className, style, children, ...props }: CardProps) {
  const borderColor = accentByIndex(accentIndex)
  const shadowColor1 = accentByIndex(accentIndex + 1)
  const shadowColor2 = accentByIndex(accentIndex + 2)
  return (
    <div
      className={cn(cardBase, dashed ? 'border-dashed' : 'border-solid')}
      style={{
        ...style,
        borderColor,
        boxShadow: `8px 8px 0 ${shadowColor1}, 16px 16px 0 ${shadowColor2}`,
      }}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('border-b-4 border-dashed pb-4 mb-6', className)}
      style={{ borderColor: 'var(--color-secondary)' }}
      {...props}
    />
  )
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        'font-black text-2xl uppercase tracking-tight text-foreground text-shadow-double',
        className
      )}
      style={{ fontFamily: 'var(--font-heading)' }}
      {...props}
    />
  )
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-lg text-white/80', className)} {...props} />
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-6', className)} {...props} />
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('pt-4 mt-4 border-t-2 border-dashed', className)}
      style={{ borderColor: 'var(--color-muted)' }}
      {...props}
    />
  )
}
