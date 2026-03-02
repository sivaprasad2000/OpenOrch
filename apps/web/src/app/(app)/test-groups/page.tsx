'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Plus, Play, Archive, Trash2, ArrowRight } from 'lucide-react'
import { testGroupService } from '@/features/test-groups/services/test-group.service'
import type { TestGroupResponse, RunConfig, RunBrowser } from '@/features/test-groups/types'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { EmptyState } from '@/components/ui/empty-state'
import { Modal } from '@/components/ui/modal'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { testGroupStatusToBadge } from '@/lib/status'
import { useRouter } from 'next/navigation'

type StatusFilter = 'all' | 'active' | 'archived'

export default function TestGroupsPage() {
  const router = useRouter()
  const [groups, setGroups] = useState<TestGroupResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  // Create modal
  const [createOpen, setCreateOpen] = useState(false)
  const [createName, setCreateName] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [createUrl, setCreateUrl] = useState('')
  const [createTags, setCreateTags] = useState('')
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState('')

  // Run modal
  const [runGroupId, setRunGroupId] = useState<string | null>(null)
  const [runBrowser, setRunBrowser] = useState<RunBrowser>('chromium')
  const [runWidth, setRunWidth] = useState('1280')
  const [runHeight, setRunHeight] = useState('720')
  const [runUrlOverride, setRunUrlOverride] = useState('')
  const [runLoading, setRunLoading] = useState(false)
  const [runError, setRunError] = useState('')

  // Delete dialog
  const [deleteId, setDeleteId] = useState<string | null>(null)

  function loadGroups() {
    setLoading(true)
    testGroupService
      .list()
      .then(setGroups)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadGroups() }, [])

  const filtered = groups.filter((g) => {
    const matchSearch = g.name.toLowerCase().includes(search.toLowerCase())
    const matchStatus = statusFilter === 'all' || g.status === statusFilter
    return matchSearch && matchStatus
  })

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!createName.trim()) return
    setCreateLoading(true)
    setCreateError('')
    try {
      await testGroupService.create({
        name: createName.trim(),
        description: createDesc.trim() || undefined,
        base_url: createUrl.trim() || undefined,
        tags: createTags ? createTags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      })
      setCreateOpen(false)
      setCreateName(''); setCreateDesc(''); setCreateUrl(''); setCreateTags('')
      loadGroups()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create')
    } finally {
      setCreateLoading(false)
    }
  }

  async function handleRun(e: React.FormEvent) {
    e.preventDefault()
    if (!runGroupId) return
    setRunLoading(true)
    setRunError('')
    const config: RunConfig = {
      browser: runBrowser,
      viewport_width: Number(runWidth),
      viewport_height: Number(runHeight),
      base_url_override: runUrlOverride.trim() || undefined,
    }
    try {
      const run = await testGroupService.run(runGroupId, config)
      setRunGroupId(null)
      router.push(`/group-runs/${run.id}`)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Failed to start run')
    } finally {
      setRunLoading(false)
    }
  }

  async function handleArchive(id: string, currentStatus: string) {
    try {
      await testGroupService.update(id, {
        status: currentStatus === 'active' ? 'archived' : 'active',
      })
      loadGroups()
    } catch { /* ignore */ }
  }

  async function handleDelete() {
    if (!deleteId) return
    try {
      await testGroupService.delete(deleteId)
      setDeleteId(null)
      loadGroups()
    } catch { /* ignore */ }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-mono text-3xl font-bold tracking-tight">Test Groups</h1>
          <p className="font-mono text-sm text-foreground/40 mt-1">
            {groups.length} group{groups.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black font-mono text-sm font-semibold hover:bg-accent/90 transition-colors"
        >
          <Plus size={14} strokeWidth={2} />
          New Test Group
        </button>
      </div>

      {error && (
        <div className="p-3 border-2 border-red-500 bg-red-500/10">
          <p className="font-mono text-sm text-red-500">{error}</p>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search groups..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-4 py-2.5 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/30 font-mono text-sm focus:outline-none focus:border-accent transition-colors"
        />
        <div className="flex border-2 border-foreground/20">
          {(['all', 'active', 'archived'] as StatusFilter[]).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-4 py-2.5 font-mono text-sm capitalize transition-colors ${
                statusFilter === s
                  ? 'bg-accent text-black font-semibold'
                  : 'text-foreground/50 hover:text-foreground'
              } ${s !== 'all' ? 'border-l border-foreground/20' : ''}`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <EmptyState
          title="No test groups found"
          description={
            search || statusFilter !== 'all'
              ? 'Try adjusting your filters.'
              : 'Create your first test group to get started.'
          }
          action={
            !search && statusFilter === 'all' ? (
              <button
                onClick={() => setCreateOpen(true)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black font-mono text-sm font-semibold hover:bg-accent/90 transition-colors"
              >
                <Plus size={14} strokeWidth={2} />
                New Test Group
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((group) => (
            <div key={group.id} className="border border-foreground/20 p-5 space-y-4 flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link
                    href={`/test-groups/${group.id}`}
                    className="font-mono font-semibold hover:text-accent transition-colors truncate block"
                  >
                    {group.name}
                  </Link>
                  {group.base_url && (
                    <p className="font-mono text-xs text-foreground/40 truncate mt-0.5">
                      {group.base_url}
                    </p>
                  )}
                </div>
                <Badge variant={testGroupStatusToBadge(group.status)} className="flex-shrink-0">
                  {group.status}
                </Badge>
              </div>

              {group.description && (
                <p className="font-mono text-sm text-foreground/60 line-clamp-2">
                  {group.description}
                </p>
              )}

              {group.tags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {group.tags.map((tag) => (
                    <span
                      key={tag}
                      className="border border-foreground/20 text-foreground/40 font-mono text-xs px-2 py-0.5"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-2 pt-1 mt-auto border-t border-border">
                <button
                  onClick={() => { setRunGroupId(group.id); setRunError('') }}
                  className="inline-flex items-center gap-1.5 text-xs font-mono text-foreground/50 hover:text-accent transition-colors"
                >
                  <Play size={11} strokeWidth={2} />
                  Run
                </button>
                <button
                  onClick={() => handleArchive(group.id, group.status)}
                  className="inline-flex items-center gap-1.5 text-xs font-mono text-foreground/50 hover:text-foreground transition-colors"
                >
                  <Archive size={11} strokeWidth={1.5} />
                  {group.status === 'active' ? 'Archive' : 'Restore'}
                </button>
                <button
                  onClick={() => setDeleteId(group.id)}
                  className="inline-flex items-center gap-1.5 text-xs font-mono text-foreground/50 hover:text-red-400 transition-colors"
                >
                  <Trash2 size={11} strokeWidth={1.5} />
                  Delete
                </button>
                <Link
                  href={`/test-groups/${group.id}`}
                  className="ml-auto inline-flex items-center gap-1 text-xs font-mono text-foreground/30 hover:text-accent transition-colors"
                >
                  Details <ArrowRight size={11} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New Test Group">
        <form onSubmit={handleCreate} className="space-y-5">
          <FieldRow label="Name *">
            <input
              required
              placeholder="Login flow"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              className={INPUT_CLS}
              autoFocus
            />
          </FieldRow>
          <FieldRow label="Description">
            <textarea
              placeholder="What does this group test?"
              value={createDesc}
              onChange={(e) => setCreateDesc(e.target.value)}
              rows={3}
              className={INPUT_CLS + ' resize-none'}
            />
          </FieldRow>
          <FieldRow label="Base URL">
            <input
              type="url"
              placeholder="https://example.com"
              value={createUrl}
              onChange={(e) => setCreateUrl(e.target.value)}
              className={INPUT_CLS}
            />
          </FieldRow>
          <FieldRow label="Tags (comma-separated)">
            <input
              placeholder="smoke, regression"
              value={createTags}
              onChange={(e) => setCreateTags(e.target.value)}
              className={INPUT_CLS}
            />
          </FieldRow>
          {createError && <ErrBox msg={createError} />}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setCreateOpen(false)} className={SEC_BTN}>
              Cancel
            </button>
            <button type="submit" disabled={createLoading} className={PRI_BTN}>
              {createLoading ? 'Creating...' : 'Create group'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Run Modal */}
      <Modal
        open={!!runGroupId}
        onClose={() => setRunGroupId(null)}
        title="Run Test Group"
      >
        <form onSubmit={handleRun} className="space-y-5">
          <FieldRow label="Browser">
            <select
              value={runBrowser}
              onChange={(e) => setRunBrowser(e.target.value as RunBrowser)}
              className={INPUT_CLS}
            >
              <option value="chromium">Chromium</option>
              <option value="firefox">Firefox</option>
              <option value="webkit">WebKit</option>
            </select>
          </FieldRow>
          <div className="grid grid-cols-2 gap-3">
            <FieldRow label="Viewport width">
              <input
                type="number"
                value={runWidth}
                onChange={(e) => setRunWidth(e.target.value)}
                className={INPUT_CLS}
              />
            </FieldRow>
            <FieldRow label="Viewport height">
              <input
                type="number"
                value={runHeight}
                onChange={(e) => setRunHeight(e.target.value)}
                className={INPUT_CLS}
              />
            </FieldRow>
          </div>
          <FieldRow label="Base URL override (optional)">
            <input
              type="url"
              placeholder="https://staging.example.com"
              value={runUrlOverride}
              onChange={(e) => setRunUrlOverride(e.target.value)}
              className={INPUT_CLS}
            />
          </FieldRow>
          {runError && <ErrBox msg={runError} />}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={() => setRunGroupId(null)} className={SEC_BTN}>
              Cancel
            </button>
            <button type="submit" disabled={runLoading} className={PRI_BTN}>
              {runLoading ? 'Starting...' : 'Run group →'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete Test Group"
        description="This will permanently delete the group and all test cases. This cannot be undone."
        confirmLabel="Delete"
        dangerous
      />
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

function ErrBox({ msg }: { msg: string }) {
  return (
    <div className="p-3 border-2 border-red-500 bg-red-500/10">
      <p className="font-mono text-sm text-red-500">{msg}</p>
    </div>
  )
}

const INPUT_CLS =
  'w-full px-3 py-2.5 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/30 font-mono text-sm focus:outline-none focus:border-accent transition-colors'
const PRI_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black font-mono text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
const SEC_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 border-2 border-foreground/30 text-foreground font-mono text-sm hover:bg-foreground/10 transition-colors'
