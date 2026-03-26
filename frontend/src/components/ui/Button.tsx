import { type ButtonHTMLAttributes, forwardRef } from 'react'
import { cn } from '../../lib/cn'

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: 'default' | 'large'
  children: React.ReactNode
  className?: string
}

const base =
  'font-bold uppercase tracking-widest rounded-full transition-all duration-300 ease-out focus:outline-none focus:ring-4 focus:ring-offset-4 disabled:opacity-50 disabled:cursor-not-allowed'

const variants: Record<ButtonVariant, string> = {
  primary:
    'bg-gradient-to-r from-accent via-quinary to-secondary border-4 border-tertiary text-background shadow-multi glow-accent hover:scale-110 hover:shadow-multi-lg focus:ring-accent focus:ring-offset-quaternary active:scale-95',
  secondary:
    'bg-transparent border-4 border-dashed border-accent text-foreground hover:bg-accent hover:border-solid hover:scale-105 focus:ring-secondary focus:ring-offset-muted',
  outline:
    'bg-muted/50 border-4 border-accent text-foreground shadow-multi hover:-translate-x-1 hover:-translate-y-1 hover:shadow-multi-lg active:translate-x-0 active:translate-y-0 active:shadow-none focus:ring-quinary focus:ring-offset-secondary',
  ghost:
    'border-0 underline decoration-accent decoration-2 underline-offset-4 text-foreground hover:scale-105 focus:ring-secondary',
}

const sizes: Record<string, string> = {
  default: 'h-14 px-10 text-base',
  large: 'h-16 px-12 text-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'default', className, children, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      className={cn(base, variants[variant], sizes[size], className)}
      {...props}
    >
      {children}
    </button>
  )
)
Button.displayName = 'Button'
