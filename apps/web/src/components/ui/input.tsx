import { cn } from '@/lib/utils'
import { InputHTMLAttributes, forwardRef } from 'react'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="w-full space-y-1">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-mono font-medium text-foreground/80"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'w-full px-4 py-3 bg-background border-2 border-foreground/20',
            'text-foreground placeholder:text-foreground/40 font-mono',
            'focus:outline-none focus:border-accent transition-colors',
            error && 'border-red-500',
            className
          )}
          {...props}
        />
        {error && (
          <p className="text-sm font-mono text-red-500">{error}</p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'
export { Input }
