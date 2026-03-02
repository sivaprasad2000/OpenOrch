import type { BadgeVariant } from '@/components/ui/badge'
import type { RunStatus, GroupRunStatus } from '@/features/test-runs/types'
import type { TestGroupStatus } from '@/features/test-groups/types'

export function runStatusToBadge(status: RunStatus): BadgeVariant {
  switch (status) {
    case 'passed': return 'success'
    case 'failed': return 'error'
    case 'running': return 'info'
    case 'queued': return 'neutral'
    default: return 'neutral'
  }
}

export function groupRunStatusToBadge(status: GroupRunStatus): BadgeVariant {
  switch (status) {
    case 'passed': return 'success'
    case 'failed': return 'error'
    case 'partial': return 'warning'
    case 'running': return 'info'
    case 'queued': return 'neutral'
    default: return 'neutral'
  }
}

export function testGroupStatusToBadge(status: TestGroupStatus): BadgeVariant {
  switch (status) {
    case 'active': return 'success'
    case 'archived': return 'neutral'
    default: return 'neutral'
  }
}
