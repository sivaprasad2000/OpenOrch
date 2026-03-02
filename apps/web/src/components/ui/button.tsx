import { cn } from '@/lib/utils'
import {
  ButtonHTMLAttributes,
  forwardRef,
  ReactElement,
  cloneElement,
} from 'react'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      asChild,
      children,
      ...props
    },
    ref
  ) => {
    const classes = cn(
      'inline-flex items-center justify-center font-medium transition-all',
      'disabled:pointer-events-none disabled:opacity-50',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
      {
        // Variants
        'brutalist-border bg-accent text-background hover:bg-accent/90':
          variant === 'primary',
        'brutalist-border bg-background text-foreground hover:bg-foreground/5':
          variant === 'secondary',
        'border-0 hover:bg-foreground/10': variant === 'ghost',
        // Sizes
        'h-9 px-4 text-sm': size === 'sm',
        'h-12 px-6 text-base': size === 'md',
        'h-14 px-8 text-lg': size === 'lg',
      },
      className
    )

    if (asChild) {
      return cloneElement(children as ReactElement, {
        className: cn(classes, (children as ReactElement).props.className),
      })
    }

    return (
      <button ref={ref} className={classes} {...props}>
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'

export { Button }
