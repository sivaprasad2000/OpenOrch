import { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="brutalist-border p-12 flex flex-col items-center justify-center text-center space-y-4">
      <h3 className="text-lg font-bold font-mono">{title}</h3>
      <p className="text-foreground/60 font-mono text-sm max-w-sm">{description}</p>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}
