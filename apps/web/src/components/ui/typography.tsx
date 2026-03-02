import { cn } from '@/lib/utils'
import { HTMLAttributes, forwardRef } from 'react'

export interface HeadingProps extends HTMLAttributes<HTMLHeadingElement> {
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
}

const Heading = forwardRef<HTMLHeadingElement, HeadingProps>(
  ({ as: Component = 'h2', className, ...props }, ref) => {
    return (
      <Component
        ref={ref}
        className={cn(
          'font-bold tracking-tight',
          {
            'text-5xl sm:text-6xl lg:text-7xl': Component === 'h1',
            'text-4xl sm:text-5xl lg:text-6xl': Component === 'h2',
            'text-3xl sm:text-4xl lg:text-5xl': Component === 'h3',
            'text-2xl sm:text-3xl': Component === 'h4',
            'text-xl sm:text-2xl': Component === 'h5',
            'text-lg sm:text-xl': Component === 'h6',
          },
          className
        )}
        {...props}
      />
    )
  }
)

Heading.displayName = 'Heading'

export interface TextProps extends HTMLAttributes<HTMLParagraphElement> {
  variant?: 'body' | 'large' | 'small' | 'muted'
}

const Text = forwardRef<HTMLParagraphElement, TextProps>(
  ({ variant = 'body', className, ...props }, ref) => {
    return (
      <p
        ref={ref}
        className={cn(
          {
            'text-base leading-relaxed': variant === 'body',
            'text-lg leading-relaxed': variant === 'large',
            'text-sm': variant === 'small',
            'text-base text-muted': variant === 'muted',
          },
          className
        )}
        {...props}
      />
    )
  }
)

Text.displayName = 'Text'

export { Heading, Text }
