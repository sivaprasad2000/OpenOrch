'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Play, Archive, Trash2, Plus, Pencil, ArrowLeft, ArrowRight, ChevronRight } from 'lucide-react'
import { testGroupService } from '@/features/test-groups/services/test-group.service'
import { testCaseService } from '@/features/test-cases/services/test-case.service'
import type { TestGroupResponse, RunConfig, RunBrowser } from '@/features/test-groups/types'
import type { TestCaseResponse } from '@/features/test-cases/types'
import type { TestGroupRunResponse } from '@/features/test-runs/types'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { Modal } from '@/components/ui/modal'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { groupRunStatusToBadge, testGroupStatusToBadge } from '@/lib/status'
import { formatDateTime, shortId } from '@/lib/format'

const INPUT_CLS =
  'w-full px-3 py-2.5 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/30 font-mono text-sm focus:outline-none focus:border-accent transition-colors'
const PRI_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black font-mono text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
const SEC_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 border-2 border-foreground/30 text-foreground font-mono text-sm hover:bg-foreground/10 transition-colors'

function ErrBox({ msg }: { msg: string }) {
  return (
    <div className="p-3 border-2 border-red-500 bg-red-500/10">
      <p className="font-mono text-sm text-red-500">{msg}</p>
    </div>
  )
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block font-mono text-sm text-foreground/70">{label}</label>
      {children}
    </div>
  )
}

function RunConfigForm({
  onSubmit,
  onCancel,
  loading,
  error,
}: {
  onSubmit: (config: RunConfig) => void
  onCancel: () => void
  loading: boolean
  error: string
}) {
  const [browser, setBrowser] = useState<RunBrowser>('chromium')
  const [width, setWidth] = useState('1280')
  const [height, setHeight] = useState('720')
  const [urlOverride, setUrlOverride] = useState('')

  function handle(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({
      browser,
      viewport_width: Number(width),
      viewport_height: Number(height),
      base_url_override: urlOverride.trim() || undefined,
    })
  }

  return (
    <form onSubmit={handle} className="space-y-5">
      <FieldRow label="Browser">
        <select value={browser} onChange={(e) => setBrowser(e.target.value as RunBrowser)} className={INPUT_CLS}>
          <option value="chromium">Chromium</option>
          <option value="firefox">Firefox</option>
          <option value="webkit">WebKit</option>
        </select>
      </FieldRow>
      <div className="grid grid-cols-2 gap-3">
        <FieldRow label="Width">
          <input type="number" value={width} onChange={(e) => setWidth(e.target.value)} className={INPUT_CLS} />
        </FieldRow>
        <FieldRow label="Height">
          <input type="number" value={height} onChange={(e) => setHeight(e.target.value)} className={INPUT_CLS} />
        </FieldRow>
      </div>
      <FieldRow label="Base URL override (optional)">
        <input type="url" placeholder="https://staging.example.com" value={urlOverride} onChange={(e) => setUrlOverride(e.target.value)} className={INPUT_CLS} />
      </FieldRow>
      {error && <ErrBox msg={error} />}
      <div className="flex justify-end gap-3 pt-2">
        <button type="button" onClick={onCancel} className={SEC_BTN}>Cancel</button>
        <button type="submit" disabled={loading} className={PRI_BTN}>
          {loading ? 'Starting...' : 'Run →'}
        </button>
      </div>
    </form>
  )
}

function CaseStepsSummary({ testCase }: { testCase: TestCaseResponse }) {
  const items = testCase.payload?.steps ?? []
  const actions: string[] = []
  for (const item of items) {
    if ('type' in item && item.type === 'group') {
      for (const s of item.steps) actions.push(s.action)
    } else {
      actions.push((item as { action: string }).action)
    }
  }
  if (actions.length === 0) return <span className="font-mono text-xs text-foreground/30">no steps</span>
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {actions.map((action, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <code className="font-mono text-xs text-accent">{action}</code>
          {i < actions.length - 1 && <ChevronRight size={10} className="text-foreground/20" />}
        </span>
      ))}
    </div>
  )
}

export default function TestGroupDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()

  const [group, setGroup] = useState<TestGroupResponse | null>(null)
  const [cases, setCases] = useState<TestCaseResponse[]>([])
  const [runs, setRuns] = useState<TestGroupRunResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'cases' | 'runs'>('cases')

  // Group run modal
  const [runOpen, setRunOpen] = useState(false)
  const [runLoading, setRunLoading] = useState(false)
  const [runError, setRunError] = useState('')

  // Case run modal
  const [caseRunId, setCaseRunId] = useState<string | null>(null)
  const [caseRunLoading, setCaseRunLoading] = useState(false)
  const [caseRunError, setCaseRunError] = useState('')

  // Delete
  const [deleteGroupOpen, setDeleteGroupOpen] = useState(false)
  const [deleteCaseId, setDeleteCaseId] = useState<string | null>(null)

  function load() {
    Promise.all([
      testGroupService.get(id),
      testCaseService.list(id),
      testGroupService.getRuns(id),
    ])
      .then(([g, c, r]) => {
        setGroup(g)
        setCases(c)
        setRuns(r.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  async function handleGroupRun(config: RunConfig) {
    setRunLoading(true)
    setRunError('')
    try {
      const run = await testGroupService.run(id, config)
      router.push(`/group-runs/${run.id}`)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Failed to start run')
      setRunLoading(false)
    }
  }

  async function handleCaseRun(config: RunConfig) {
    if (!caseRunId) return
    setCaseRunLoading(true)
    setCaseRunError('')
    try {
      const run = await testCaseService.run(caseRunId, config)
      router.push(`/runs/${run.id}`)
    } catch (err) {
      setCaseRunError(err instanceof Error ? err.message : 'Failed to start run')
      setCaseRunLoading(false)
    }
  }

  async function handleDeleteCase() {
    if (!deleteCaseId || !group) return
    try {
      await testCaseService.delete(group.id, deleteCaseId)
      setDeleteCaseId(null)
      load()
    } catch { /* ignore */ }
  }

  async function handleDeleteGroup() {
    try {
      await testGroupService.delete(id)
      router.push('/test-groups')
    } catch { /* ignore */ }
  }

  async function handleArchive() {
    if (!group) return
    try {
      await testGroupService.update(id, {
        status: group.status === 'active' ? 'archived' : 'active',
      })
      load()
    } catch { /* ignore */ }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
  }

  if (!group) {
    return (
      <div className="space-y-4">
        <p className="font-mono text-foreground/40">Group not found.</p>
        <Link href="/test-groups" className="font-mono text-sm text-accent hover:underline">
          ← Back to Test Groups
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm font-mono text-foreground/40">
        <Link href="/test-groups" className="hover:text-accent transition-colors inline-flex items-center gap-1">
          <ArrowLeft size={12} /> Test Groups
        </Link>
        <span>/</span>
        <span className="text-foreground">{group.name}</span>
      </div>

      {/* Group info panel */}
      <div className="border border-foreground/20 p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-3">
              <h1 className="font-mono text-2xl font-bold tracking-tight">{group.name}</h1>
              <Badge variant={testGroupStatusToBadge(group.status)}>{group.status}</Badge>
            </div>
            {group.base_url && (
              <p className="font-mono text-sm text-foreground/40">{group.base_url}</p>
            )}
            {group.description && (
              <p className="font-mono text-sm text-foreground/60 mt-1">{group.description}</p>
            )}
            {group.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {group.tags.map((tag) => (
                  <span key={tag} className="border border-foreground/20 text-foreground/40 font-mono text-xs px-2 py-0.5">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button onClick={() => setRunOpen(true)} className={PRI_BTN}>
              <Play size={13} strokeWidth={2} /> Run Group
            </button>
            <button onClick={handleArchive} className={SEC_BTN}>
              <Archive size={13} strokeWidth={1.5} />
              {group.status === 'active' ? 'Archive' : 'Restore'}
            </button>
            <button
              onClick={() => setDeleteGroupOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 border-2 border-red-500/30 text-red-400 font-mono text-sm hover:bg-red-500/10 transition-colors"
            >
              <Trash2 size={13} strokeWidth={1.5} />
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div>
        <div className="flex border-b border-border">
          {(['cases', 'runs'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-3 font-mono text-sm transition-colors border-b-2 -mb-px ${
                activeTab === tab
                  ? 'border-accent text-accent'
                  : 'border-transparent text-foreground/40 hover:text-foreground'
              }`}
            >
              {tab === 'cases'
                ? `Test Cases (${cases.length})`
                : `Run History (${runs.length})`}
            </button>
          ))}
        </div>

        {/* Test Cases Tab */}
        {activeTab === 'cases' && (
          <div className="pt-6 space-y-4">
            <div className="flex justify-end">
              <Link href={`/test-groups/${id}/test-cases/new`} className={PRI_BTN}>
                <Plus size={14} strokeWidth={2} /> Add Test Case
              </Link>
            </div>

            {cases.length === 0 ? (
              <div className="border-2 border-foreground/20 p-12 text-center">
                <p className="font-mono text-sm text-foreground/40">
                  No test cases yet. Add one to start testing.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {cases.map((c) => {
                  const steps = c.payload?.steps ?? []
                  return (
                    <div key={c.id} className="border-2 border-foreground/20 p-4 hover:border-foreground/40 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1 space-y-2">
                          <div className="flex items-center gap-3">
                            <code className="font-mono text-xs text-foreground/30">{shortId(c.id)}</code>
                            <span className="font-mono text-xs text-foreground/40">
                              {steps.length} step{steps.length !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <CaseStepsSummary testCase={c} />
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <button
                            onClick={() => { setCaseRunId(c.id); setCaseRunError('') }}
                            className="inline-flex items-center gap-1 text-xs font-mono text-foreground/40 hover:text-accent transition-colors"
                          >
                            <Play size={11} strokeWidth={2} /> Run
                          </button>
                          <Link
                            href={`/test-groups/${id}/test-cases/${c.id}`}
                            className="inline-flex items-center gap-1 text-xs font-mono text-foreground/40 hover:text-foreground transition-colors"
                          >
                            <Pencil size={11} strokeWidth={1.5} /> Edit
                          </Link>
                          <button
                            onClick={() => setDeleteCaseId(c.id)}
                            className="inline-flex items-center gap-1 text-xs font-mono text-foreground/40 hover:text-red-400 transition-colors"
                          >
                            <Trash2 size={11} strokeWidth={1.5} /> Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Run History Tab */}
        {activeTab === 'runs' && (
          <div className="pt-6">
            {runs.length === 0 ? (
              <div className="border-2 border-foreground/20 p-12 text-center">
                <p className="font-mono text-sm text-foreground/40">No runs yet.</p>
              </div>
            ) : (
              <div className="border border-foreground/20">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      {['Status', 'Browser', 'Results', 'Started', ''].map((h) => (
                        <th key={h} className="text-left px-5 py-3 text-xs font-mono uppercase tracking-wider text-foreground/30">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => {
                      const passed = run.test_runs.filter((r) => r.status === 'passed').length
                      const total = run.test_runs.length
                      return (
                        <tr key={run.id} className="border-b border-border last:border-0 hover:bg-foreground/[0.03]">
                          <td className="px-5 py-3">
                            <Badge variant={groupRunStatusToBadge(run.status)}>{run.status}</Badge>
                          </td>
                          <td className="px-5 py-3 font-mono text-sm text-foreground/60">{run.browser}</td>
                          <td className="px-5 py-3 font-mono text-sm">
                            <span className="text-green-500">{passed}</span>
                            <span className="text-foreground/30">/{total}</span>
                            <span className="text-foreground/40 text-xs ml-1">passed</span>
                          </td>
                          <td className="px-5 py-3 font-mono text-sm text-foreground/40">
                            {formatDateTime(run.created_at)}
                          </td>
                          <td className="px-5 py-3 text-right">
                            <Link href={`/group-runs/${run.id}`} className="inline-flex items-center gap-1 text-xs font-mono text-foreground/30 hover:text-accent transition-colors">
                              View <ArrowRight size={11} />
                            </Link>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Group Run Modal */}
      <Modal open={runOpen} onClose={() => setRunOpen(false)} title="Run Test Group">
        <RunConfigForm
          onSubmit={handleGroupRun}
          onCancel={() => setRunOpen(false)}
          loading={runLoading}
          error={runError}
        />
      </Modal>

      {/* Case Run Modal */}
      <Modal open={!!caseRunId} onClose={() => setCaseRunId(null)} title="Run Test Case">
        <RunConfigForm
          onSubmit={handleCaseRun}
          onCancel={() => setCaseRunId(null)}
          loading={caseRunLoading}
          error={caseRunError}
        />
      </Modal>

      {/* Delete Group */}
      <ConfirmDialog
        open={deleteGroupOpen}
        onClose={() => setDeleteGroupOpen(false)}
        onConfirm={handleDeleteGroup}
        title="Delete Test Group"
        description="This will permanently delete the group and all test cases. This cannot be undone."
        confirmLabel="Delete group"
        dangerous
      />

      {/* Delete Case */}
      <ConfirmDialog
        open={!!deleteCaseId}
        onClose={() => setDeleteCaseId(null)}
        onConfirm={handleDeleteCase}
        title="Delete Test Case"
        description="This test case will be permanently deleted."
        confirmLabel="Delete"
        dangerous
      />
    </div>
  )
}
