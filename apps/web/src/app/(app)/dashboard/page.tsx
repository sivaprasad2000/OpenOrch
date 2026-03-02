'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { FlaskConical, Bot, ArrowRight, TrendingUp } from 'lucide-react'
import { userService } from '@/features/users/services/user.service'
import { testGroupService } from '@/features/test-groups/services/test-group.service'
import type { UserMeResponse } from '@/features/users/types'
import type { TestGroupResponse } from '@/features/test-groups/types'
import type { TestGroupRunResponse } from '@/features/test-runs/types'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { groupRunStatusToBadge } from '@/lib/status'
import { formatRelativeTime } from '@/lib/format'

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export default function DashboardPage() {
  const [user, setUser] = useState<UserMeResponse | null>(null)
  const [groups, setGroups] = useState<TestGroupResponse[]>([])
  const [recentRuns, setRecentRuns] = useState<TestGroupRunResponse[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [me, groupList] = await Promise.all([
          userService.getMe(),
          testGroupService.list(),
        ])
        if (cancelled) return
        setUser(me)
        setGroups(groupList)

        const top5 = groupList.slice(0, 5)
        const runArrays = await Promise.all(
          top5.map((g) =>
            testGroupService
              .getRuns(g.id)
              .catch(() => [] as TestGroupRunResponse[])
          )
        )
        if (cancelled) return
        const allRuns = runArrays
          .flat()
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime()
          )
        setRecentRuns(allRuns.slice(0, 10))
      } catch {
        // layout handles auth redirect
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const activeGroups = groups.filter((g) => g.status === 'active').length
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000
  const runsThisWeek = recentRuns.filter(
    (r) => new Date(r.created_at).getTime() >= sevenDaysAgo
  ).length
  const passedRuns = recentRuns.filter((r) => r.status === 'passed').length
  const passRate =
    recentRuns.length > 0
      ? Math.round((passedRuns / recentRuns.length) * 100)
      : 0

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-10">
      {/* Welcome */}
      <div className="border-b border-border pb-8">
        <p className="mb-2 font-mono text-xs uppercase tracking-wider text-foreground/30">
          {user?.active_organization?.name}
        </p>
        <h1 className="font-mono text-4xl font-bold tracking-tight">
          {getGreeting()}, {user?.name ?? 'there'}.
        </h1>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 border border-foreground/20 lg:grid-cols-4">
        {[
          { label: 'Total Groups', value: groups.length },
          { label: 'Active Groups', value: activeGroups },
          { label: 'Runs (7 days)', value: runsThisWeek },
          { label: 'Pass Rate', value: `${passRate}%` },
        ].map((stat, i) => (
          <div
            key={stat.label}
            className={`space-y-2 p-6 ${i < 3 ? 'border-r border-border' : ''}`}
          >
            <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
              {stat.label}
            </p>
            <p className="font-mono text-3xl font-bold text-accent">
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* Recent Runs */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
            Recent Group Runs
          </p>
          <Link
            href="/test-groups"
            className="flex items-center gap-1 font-mono text-xs text-foreground/40 transition-colors hover:text-accent"
          >
            View all <ArrowRight size={11} />
          </Link>
        </div>

        <div className="border border-foreground/20">
          {recentRuns.length === 0 ? (
            <div className="border-b border-border p-12 text-center">
              <TrendingUp
                size={32}
                strokeWidth={1}
                className="mx-auto mb-3 text-foreground/20"
              />
              <p className="font-mono text-sm text-foreground/40">
                No runs yet. Create a test group and run it.
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  {['Status', 'Group', 'Browser', 'Started', ''].map((h) => (
                    <th
                      key={h}
                      className="px-5 py-3 text-left font-mono text-xs uppercase tracking-wider text-foreground/30"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => {
                  const group = groups.find((g) => g.id === run.test_group_id)
                  return (
                    <tr
                      key={run.id}
                      className="border-b border-border last:border-0 hover:bg-foreground/[0.03]"
                    >
                      <td className="px-5 py-3">
                        <Badge variant={groupRunStatusToBadge(run.status)}>
                          {run.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 font-mono text-sm">
                        {group ? (
                          <Link
                            href={`/test-groups/${group.id}`}
                            className="transition-colors hover:text-accent"
                          >
                            {group.name}
                          </Link>
                        ) : (
                          <span className="text-foreground/30">
                            {run.test_group_id?.slice(0, 8) ?? '—'}
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 font-mono text-sm text-foreground/40">
                        {run.browser}
                      </td>
                      <td className="px-5 py-3 font-mono text-sm text-foreground/40">
                        {formatRelativeTime(run.created_at)}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Link
                          href={`/group-runs/${run.id}`}
                          className="inline-flex items-center gap-1 font-mono text-xs text-foreground/40 transition-colors hover:text-accent"
                        >
                          View <ArrowRight size={11} />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <p className="mb-4 font-mono text-xs uppercase tracking-wider text-foreground/30">
          Quick Actions
        </p>
        <div className="grid grid-cols-1 border border-foreground/20 sm:grid-cols-3">
          {[
            {
              href: '/test-groups',
              Icon: FlaskConical,
              label: 'New Test Group',
              sub: 'Create and run automated tests',
            },
            {
              href: '/llms',
              Icon: Bot,
              label: 'Configure LLM',
              sub: 'Add an AI provider API key',
            },
          ].map(({ href, Icon, label, sub }, i) => (
            <Link
              key={href}
              href={href}
              className={`flex items-start gap-4 p-6 transition-colors hover:bg-foreground/[0.03] ${
                i < 1 ? 'border-r border-border' : ''
              }`}
            >
              <Icon
                size={18}
                strokeWidth={1.5}
                className="mt-0.5 flex-shrink-0 text-accent"
              />
              <div>
                <p className="mb-0.5 font-mono text-sm font-semibold">
                  {label}
                </p>
                <p className="font-mono text-xs text-foreground/40">{sub}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
