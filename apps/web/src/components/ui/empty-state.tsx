import { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="brutalist-border flex flex-col items-center justify-center space-y-4 p-12 text-center">
      <h3 className="font-mono text-lg font-bold">{title}</h3>
      <p className="max-w-sm font-mono text-sm text-foreground/60">
        {description}
      </p>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}
