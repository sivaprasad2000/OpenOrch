import { cn } from '@/lib/utils'

export type BadgeVariant = 'success' | 'error' | 'warning' | 'neutral' | 'info'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
}

export function Badge({
  variant = 'neutral',
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center border-2 px-2 py-0.5 font-mono text-xs',
        {
          'border-green-500 bg-green-500/10 text-green-500':
            variant === 'success',
          'border-red-500 bg-red-500/10 text-red-500': variant === 'error',
          'border-yellow-500 bg-yellow-500/10 text-yellow-500':
            variant === 'warning',
          'border-foreground/30 text-foreground/60': variant === 'neutral',
          'border-accent bg-accent/10 text-accent': variant === 'info',
        },
        className
      )}
    >
      {children}
    </span>
  )
}
