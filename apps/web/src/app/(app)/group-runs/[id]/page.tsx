'use client'

import { use } from 'react'
import Link from 'next/link'
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react'
import { testRunService } from '@/features/test-runs/services/test-run.service'
import { TERMINAL_GROUP_STATUSES } from '@/features/test-runs/types'
import { usePolling } from '@/hooks/use-polling'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { groupRunStatusToBadge, runStatusToBadge } from '@/lib/status'
import { formatDateTime, shortId } from '@/lib/format'

export default function GroupRunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)

  const { data: run, loading, error } = usePolling(
    () => testRunService.getGroupRun(id),
    (data) => TERMINAL_GROUP_STATUSES.includes(data.status)
  )

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
  }

  if (error || !run) {
    return (
      <div className="space-y-4">
        <div className="p-3 border-2 border-red-500 bg-red-500/10">
          <p className="font-mono text-sm text-red-500">{error ?? 'Run not found'}</p>
        </div>
        <Link href="/test-groups" className="font-mono text-sm text-accent hover:underline inline-flex items-center gap-1">
          <ArrowLeft size={12} /> Back to Test Groups
        </Link>
      </div>
    )
  }

  const isLive = !TERMINAL_GROUP_STATUSES.includes(run.status)
  const passed = run.test_runs.filter((r) => r.status === 'passed').length
  const failed = run.test_runs.filter((r) => r.status === 'failed').length
  const total = run.test_runs.length

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm font-mono text-foreground/40">
        <Link href="/test-groups" className="hover:text-accent transition-colors inline-flex items-center gap-1">
          <ArrowLeft size={12} /> Test Groups
        </Link>
        <span>/</span>
        {run.test_group_id ? (
          <Link href={`/test-groups/${run.test_group_id}`} className="hover:text-accent transition-colors">
            {run.test_group_id.slice(0, 8)}
          </Link>
        ) : (
          <span>Group</span>
        )}
        <span>/</span>
        <span className="text-foreground">Run {shortId(run.id)}</span>
      </div>

      {/* Header */}
      <div className={`border p-6 space-y-4 ${isLive ? 'border-accent/70' : 'border-foreground/20'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
                Group Run
              </p>
              <code className="font-mono text-xs text-foreground/40">{shortId(run.id)}</code>
              {isLive && (
                <span className="inline-flex items-center gap-1.5 text-xs font-mono text-accent">
                  <Loader2 size={11} className="animate-spin" />
                  Polling...
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={groupRunStatusToBadge(run.status)}>{run.status}</Badge>
              <span className="font-mono text-sm text-foreground/40">{run.browser}</span>
              <span className="font-mono text-sm text-foreground/40">
                {run.viewport_width}×{run.viewport_height}
              </span>
            </div>
          </div>
          <div className="text-right space-y-1">
            <p className="font-mono text-xs text-foreground/30">Created</p>
            <p className="font-mono text-sm">{formatDateTime(run.created_at)}</p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 border border-foreground/20">
        {[
          { label: 'Total', value: total, color: 'text-foreground' },
          { label: 'Passed', value: passed, color: 'text-green-500' },
          { label: 'Failed', value: failed, color: 'text-red-500' },
        ].map((s, i) => (
          <div key={s.label} className={`p-6 space-y-2 ${i < 2 ? 'border-r border-border' : ''}`}>
            <p className="text-xs font-mono uppercase tracking-wider text-foreground/30">{s.label}</p>
            <p className={`font-mono text-3xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Child Runs */}
      <div>
        <p className="text-xs font-mono uppercase tracking-wider text-foreground/30 mb-4">
          Test Runs ({run.test_runs.length})
        </p>
        {run.test_runs.length === 0 ? (
          <div className="border-2 border-foreground/20 p-12 text-center">
            <p className="font-mono text-sm text-foreground/40">No test runs yet.</p>
          </div>
        ) : (
          <div className="border border-foreground/20 space-y-0">
            {run.test_runs.map((tr, i) => (
              <div
                key={tr.id}
                className={`p-5 flex items-start justify-between gap-4 ${
                  i < run.test_runs.length - 1 ? 'border-b border-border' : ''
                } hover:bg-foreground/[0.03]`}
              >
                <div className="space-y-2 min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <Badge variant={runStatusToBadge(tr.status)}>{tr.status}</Badge>
                    <code className="font-mono text-xs text-foreground/40">{tr.test_case_id ? shortId(tr.test_case_id) : '—'}</code>
                    <span className="font-mono text-xs text-foreground/30">
                      {tr.step_results?.length ?? 0} step{(tr.step_results?.length ?? 0) !== 1 ? 's' : ''}
                    </span>
                  </div>
                  {tr.error && (
                    <p className="font-mono text-xs text-red-400 truncate">{tr.error}</p>
                  )}
                </div>
                <Link
                  href={`/runs/${tr.id}`}
                  className="inline-flex items-center gap-1 text-xs font-mono text-foreground/30 hover:text-accent transition-colors flex-shrink-0"
                >
                  View <ArrowRight size={11} />
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
