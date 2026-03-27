import { type InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '../../lib/cn'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  className?: string
  inputClassName?: string
}

const inputBase =
  'w-full px-6 py-4 text-lg font-bold text-foreground bg-muted/50 backdrop-blur-sm border-4 border-accent rounded-full placeholder:text-white/40 transition-all duration-300 focus:border-secondary focus:shadow-[0_0_20px_rgba(0,245,212,0.5)] focus:ring-4 focus:ring-accent/30 focus:ring-offset-2 focus:ring-offset-secondary focus:bg-muted'

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, inputClassName, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className={cn('space-y-2', className)}>
        {label && (
          <label
            htmlFor={inputId}
            className="block font-display text-secondary text-sm uppercase tracking-widest rotate-1"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(inputBase, inputClassName)}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="text-red text-sm" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  }
)
Input.displayName = 'Input'
