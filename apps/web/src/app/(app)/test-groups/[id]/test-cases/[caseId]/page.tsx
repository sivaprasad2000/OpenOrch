'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react'
import { testCaseService } from '@/features/test-cases/services/test-case.service'
import type { StepGroup, TestCaseStep, TestCasePayload } from '@/features/test-cases/types'
import { Spinner } from '@/components/ui/spinner'
import {
  StepBuilder,
  type StepDraft,
  nextStepId,
  buildStep,
  parseDraft,
} from '@/components/step-builder'

// ─── constants ────────────────────────────────────────────────────────────────

const PRI_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black font-mono text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
const SEC_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 border border-foreground/20 text-foreground font-mono text-sm hover:bg-foreground/10 transition-colors'

// ─── group draft ──────────────────────────────────────────────────────────────

interface GroupDraft {
  id: string
  name: string
  steps: StepDraft[]
  collapsed: boolean
}

let _groupCounter = 0
function nextGroupId() { return `group-${++_groupCounter}` }

function emptyGroup(name = '', steps?: StepDraft[]): GroupDraft {
  return {
    id: nextGroupId(),
    name,
    steps: steps ?? [{ id: nextStepId(), action: '', description: '' }],
    collapsed: false,
  }
}

function parseGroups(payload: TestCasePayload): GroupDraft[] {
  if (!payload?.steps?.length) return [emptyGroup()]

  const groups: GroupDraft[] = []
  let orphans: StepDraft[] = []

  for (const item of payload.steps) {
    if ('type' in item && item.type === 'group') {
      if (orphans.length > 0) {
        groups.push(emptyGroup('Steps', orphans))
        orphans = []
      }
      groups.push({
        id: nextGroupId(),
        name: item.name,
        steps: item.steps.map(parseDraft),
        collapsed: false,
      })
    } else {
      orphans.push(parseDraft(item as TestCaseStep))
    }
  }

  if (orphans.length > 0) {
    groups.push(emptyGroup('Steps', orphans))
  }

  return groups.length > 0 ? groups : [emptyGroup()]
}

function toApiPayload(groups: GroupDraft[]): TestCasePayload {
  return {
    steps: groups.map((g): StepGroup => ({
      type: 'group',
      name: g.name,
      steps: g.steps.map((draft) => buildStep(draft) as TestCaseStep),
    })),
  }
}

// ─── GroupCard ────────────────────────────────────────────────────────────────

function GroupCard({
  group,
  actions,
  onChange,
  onRemove,
  isOnly,
}: {
  group: GroupDraft
  actions: string[]
  onChange: (g: GroupDraft) => void
  onRemove: () => void
  isOnly: boolean
}) {
  const stepCount = group.steps.filter((s) => s.action).length

  return (
    <div className="border border-foreground/20">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-foreground/[0.02]">
        <button
          type="button"
          onClick={() => onChange({ ...group, collapsed: !group.collapsed })}
          className="text-foreground/40 hover:text-foreground transition-colors flex-shrink-0"
          title={group.collapsed ? 'Expand' : 'Collapse'}
        >
          {group.collapsed
            ? <ChevronRight size={14} strokeWidth={1.5} />
            : <ChevronDown size={14} strokeWidth={1.5} />
          }
        </button>

        <input
          type="text"
          value={group.name}
          onChange={(e) => onChange({ ...group, name: e.target.value })}
          placeholder="Group name..."
          className="flex-1 bg-transparent font-mono text-sm font-semibold text-foreground placeholder:text-foreground/30 focus:outline-none focus-visible:ring-0 min-w-0"
        />

        {group.collapsed && (
          <span className="font-mono text-xs text-foreground/30 flex-shrink-0">
            {stepCount} step{stepCount !== 1 ? 's' : ''}
          </span>
        )}

        <button
          type="button"
          onClick={onRemove}
          disabled={isOnly}
          className="text-foreground/20 hover:text-red-400 transition-colors disabled:opacity-20 disabled:cursor-not-allowed flex-shrink-0"
          title="Remove group"
        >
          <Trash2 size={14} strokeWidth={1.5} />
        </button>
      </div>

      {/* Body */}
      {!group.collapsed && (
        <div className="p-4 border-t border-border">
          <StepBuilder
            steps={group.steps}
            actions={actions}
            onChange={(steps) => onChange({ ...group, steps })}
          />
        </div>
      )}
    </div>
  )
}

// ─── page ─────────────────────────────────────────────────────────────────────

export default function TestCaseBuilderPage({
  params,
}: {
  params: Promise<{ id: string; caseId: string }>
}) {
  const { id: groupId, caseId } = use(params)
  const router = useRouter()
  const isNew = caseId === 'new'

  const [groups, setGroups] = useState<GroupDraft[]>([emptyGroup()])
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [stepActions, setStepActions] = useState<string[]>([])

  // Fetch available step actions from the API
  useEffect(() => {
    testCaseService.getStepActions().then(setStepActions).catch(() => {})
  }, [])

  useEffect(() => {
    if (isNew) return
    let cancelled = false
    testCaseService.get(groupId, caseId)
      .then((tc) => {
        if (!cancelled && tc?.payload) setGroups(parseGroups(tc.payload))
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [groupId, caseId, isNew])

  function addGroup() {
    setGroups((g) => [...g, emptyGroup()])
  }

  function removeGroup(i: number) {
    setGroups((g) => g.filter((_, idx) => idx !== i))
  }

  function updateGroup(i: number, updated: GroupDraft) {
    setGroups((g) => { const n = [...g]; n[i] = updated; return n })
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()

    const unnamedGroup = groups.findIndex((g) => !g.name.trim())
    if (unnamedGroup !== -1) {
      setError(`Group ${unnamedGroup + 1} needs a name.`)
      return
    }

    for (let gi = 0; gi < groups.length; gi++) {
      const emptyStep = groups[gi].steps.findIndex((s) => !s.action)
      if (emptyStep !== -1) {
        setError(`"${groups[gi].name}": step ${emptyStep + 1} — please select an action.`)
        return
      }
    }

    setSaving(true)
    setError('')
    const payload = toApiPayload(groups)

    try {
      if (isNew) {
        await testCaseService.create(groupId, { payload })
      } else {
        await testCaseService.update(groupId, caseId, { payload })
      }
      router.push(`/test-groups/${groupId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
  }

  return (
    <div className="space-y-8 max-w-3xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm font-mono text-foreground/40">
        <Link href="/test-groups" className="hover:text-accent transition-colors inline-flex items-center gap-1">
          <ArrowLeft size={12} /> Test Groups
        </Link>
        <span>/</span>
        <Link href={`/test-groups/${groupId}`} className="hover:text-accent transition-colors">
          Group
        </Link>
        <span>/</span>
        <span className="text-foreground">{isNew ? 'New Test Case' : 'Edit Test Case'}</span>
      </div>

      {/* Title */}
      <div>
        <h1 className="font-mono text-3xl font-bold tracking-tight">
          {isNew ? 'New Test Case' : 'Edit Test Case'}
        </h1>
        <p className="font-mono text-sm text-foreground/40 mt-1">
          Organise steps into named groups. Each step has an action type and a plain-English description for the LLM.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Groups */}
        <div className="space-y-3">
          {groups.map((group, i) => (
            <GroupCard
              key={group.id}
              group={group}
              actions={stepActions}
              onChange={(updated) => updateGroup(i, updated)}
              onRemove={() => removeGroup(i)}
              isOnly={groups.length === 1}
            />
          ))}
        </div>

        {/* Add group */}
        <button
          type="button"
          onClick={addGroup}
          className="w-full border border-dashed border-foreground/20 py-3 font-mono text-sm text-foreground/30 hover:border-accent hover:text-accent transition-colors inline-flex items-center justify-center gap-2"
        >
          <Plus size={14} strokeWidth={1.5} />
          Add group
        </button>

        {error && (
          <div className="p-3 border-2 border-red-500 bg-red-500/10">
            <p className="font-mono text-sm text-red-500">{error}</p>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-border">
          <Link href={`/test-groups/${groupId}`} className={SEC_BTN}>
            Cancel
          </Link>
          <button type="submit" disabled={saving} className={PRI_BTN}>
            {saving ? 'Saving...' : isNew ? 'Create test case' : 'Save changes'}
          </button>
        </div>
      </form>
    </div>
  )
}
