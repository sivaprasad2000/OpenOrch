'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Plus, Trash2, GripVertical,
  ChevronDown, ChevronUp,
  Navigation, MousePointer, Type, List, Hand, Clock, Check,
} from 'lucide-react'

// ─── types ────────────────────────────────────────────────────────────────────

export interface StepDraft {
  id: string
  action: string
  description: string
}

export interface BuiltStep {
  action: string
  description: string
}

// ─── helpers ──────────────────────────────────────────────────────────────────

let _counter = 0
export function nextStepId() { return `step-${++_counter}` }

export function buildStep(draft: StepDraft): BuiltStep {
  return { action: draft.action, description: draft.description }
}

export function parseDraft(step: BuiltStep): StepDraft {
  return { id: nextStepId(), action: step.action, description: step.description }
}

// ─── constants ────────────────────────────────────────────────────────────────

const INPUT_CLS =
  'w-full px-3 py-2.5 bg-background border border-foreground/20 text-foreground placeholder:text-foreground/30 font-mono text-sm focus:outline-none focus:border-accent transition-colors'

// ─── ActionSelect ─────────────────────────────────────────────────────────────

const ACTION_META: Record<string, { icon: React.ReactNode; hint: string }> = {
  navigate: { icon: <Navigation  size={12} />, hint: 'go to a URL' },
  click:    { icon: <MousePointer size={12} />, hint: 'click an element' },
  type:     { icon: <Type         size={12} />, hint: 'enter text' },
  select:   { icon: <List         size={12} />, hint: 'choose an option' },
  hover:    { icon: <Hand         size={12} />, hint: 'hover over element' },
  wait:     { icon: <Clock        size={12} />, hint: 'pause execution' },
}

function ActionSelect({
  value,
  actions,
  disabled,
  onChange,
}: {
  value: string
  actions: string[]
  disabled: boolean
  onChange: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on outside click or Escape
  useEffect(() => {
    if (!open) return
    function onMouse(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onMouse)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouse)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const meta = value ? ACTION_META[value] : null
  const hasLegacy = value && !actions.includes(value)

  return (
    <div ref={containerRef} className="relative flex-1 min-w-0">
      {/* Trigger */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={`w-full flex items-center gap-2 px-3 py-1.5 border font-mono text-sm transition-colors bg-background disabled:opacity-40 disabled:cursor-not-allowed ${
          open
            ? 'border-accent text-foreground'
            : 'border-foreground/20 hover:border-foreground/40 ' + (value ? 'text-foreground' : 'text-foreground/35')
        }`}
      >
        <span className={`flex-shrink-0 transition-colors ${value ? 'text-accent' : 'text-foreground/25'}`}>
          {meta?.icon ?? <MousePointer size={12} />}
        </span>
        <span className="flex-1 text-left truncate">
          {value || (disabled ? 'loading…' : 'select action…')}
        </span>
        <ChevronDown
          size={10}
          className={`flex-shrink-0 text-foreground/40 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Panel */}
      {open && !disabled && (
        <div className="absolute z-50 top-full left-0 right-0 mt-px border border-accent/40 bg-background">
          {/* Legacy value row */}
          {hasLegacy && (
            <button
              type="button"
              onClick={() => { onChange(value); setOpen(false) }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-left bg-accent/[0.06] border-b border-border hover:bg-accent/[0.10] transition-colors"
            >
              <span className="text-foreground/30 flex-shrink-0"><MousePointer size={12} /></span>
              <span className="font-mono text-sm text-foreground/60 flex-1 truncate">{value}</span>
              <span className="font-mono text-[10px] text-foreground/30 flex-shrink-0">legacy</span>
            </button>
          )}

          {/* Enum options */}
          {actions.map((a) => {
            const m = ACTION_META[a]
            const isSelected = a === value
            return (
              <button
                key={a}
                type="button"
                onClick={() => { onChange(a); setOpen(false) }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors group ${
                  isSelected
                    ? 'bg-accent/[0.08] text-accent'
                    : 'text-foreground/60 hover:bg-foreground/[0.05] hover:text-foreground'
                }`}
              >
                <span className={`flex-shrink-0 transition-colors ${isSelected ? 'text-accent' : 'text-foreground/25 group-hover:text-foreground/50'}`}>
                  {m?.icon ?? <MousePointer size={12} />}
                </span>
                <span className="font-mono text-sm flex-1">{a}</span>
                {m?.hint && (
                  <span className="font-mono text-[10px] text-foreground/25 flex-shrink-0 hidden group-hover:inline">
                    {m.hint}
                  </span>
                )}
                {isSelected && (
                  <Check size={10} className="text-accent flex-shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── StepCard ─────────────────────────────────────────────────────────────────

function StepCard({
  index,
  draft,
  actions,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
  isOnly,
  isFirst,
  isLast,
  isDragging,
  isDraggedOver,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: {
  index: number
  draft: StepDraft
  actions: string[]
  onChange: (updated: StepDraft) => void
  onRemove: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  isOnly: boolean
  isFirst: boolean
  isLast: boolean
  isDragging: boolean
  isDraggedOver: boolean
  onDragStart: () => void
  onDragOver: () => void
  onDrop: () => void
  onDragEnd: () => void
}) {
  const canDragRef = useRef(false)

  return (
    <div
      draggable
      onDragStart={(e) => {
        if (!canDragRef.current) { e.preventDefault(); return }
        onDragStart()
      }}
      onDragOver={(e) => { e.preventDefault(); onDragOver() }}
      onDrop={onDrop}
      onDragEnd={() => { canDragRef.current = false; onDragEnd() }}
      className={`border transition-all duration-100 ${
        isDragging ? 'opacity-30 scale-[0.99]' : ''
      } ${isDraggedOver ? 'border-accent/60 bg-accent/[0.02]' : 'border-foreground/20 hover:border-foreground/30'}`}
    >
      {/* Header row: grip, index, action input, move, remove */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-foreground/[0.02]">
        <div
          className="cursor-grab active:cursor-grabbing text-foreground/20 hover:text-foreground/50 transition-colors flex-shrink-0 select-none"
          onMouseDown={() => { canDragRef.current = true }}
          onMouseUp={() => { canDragRef.current = false }}
        >
          <GripVertical size={14} />
        </div>

        <span className="font-mono text-xs text-foreground/30 w-5 flex-shrink-0 select-none">
          {String(index + 1).padStart(2, '0')}
        </span>

        <ActionSelect
          value={draft.action}
          actions={actions}
          disabled={actions.length === 0}
          onChange={(a) => onChange({ ...draft, action: a })}
        />

        <div className="flex flex-col flex-shrink-0">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={isFirst}
            className="text-foreground/20 hover:text-foreground/60 transition-colors disabled:opacity-0 disabled:pointer-events-none"
            title="Move up"
          >
            <ChevronUp size={13} strokeWidth={1.5} />
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={isLast}
            className="text-foreground/20 hover:text-foreground/60 transition-colors disabled:opacity-0 disabled:pointer-events-none"
            title="Move down"
          >
            <ChevronDown size={13} strokeWidth={1.5} />
          </button>
        </div>

        <button
          type="button"
          onClick={onRemove}
          disabled={isOnly}
          className="text-foreground/20 hover:text-red-400 transition-colors disabled:opacity-20 disabled:cursor-not-allowed flex-shrink-0"
          title="Remove step"
        >
          <Trash2 size={14} strokeWidth={1.5} />
        </button>
      </div>

      {/* Description textarea */}
      <div className="px-4 py-3">
        <textarea
          value={draft.description}
          onChange={(e) => onChange({ ...draft, description: e.target.value })}
          placeholder="Describe what this step should do in plain English…"
          rows={2}
          className={INPUT_CLS + ' resize-none'}
        />
      </div>
    </div>
  )
}

// ─── StepBuilder (public) ─────────────────────────────────────────────────────

export function StepBuilder({
  steps,
  actions,
  onChange,
}: {
  steps: StepDraft[]
  actions: string[]
  onChange: (steps: StepDraft[]) => void
}) {
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null)
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null)

  function addStep() {
    onChange([...steps, { id: nextStepId(), action: '', description: '' }])
  }

  function removeStep(i: number) {
    onChange(steps.filter((_, idx) => idx !== i))
  }

  function updateStep(i: number, updated: StepDraft) {
    const next = [...steps]; next[i] = updated; onChange(next)
  }

  function moveStep(from: number, to: number) {
    if (to < 0 || to >= steps.length) return
    const next = [...steps]
    const [removed] = next.splice(from, 1)
    next.splice(to, 0, removed)
    onChange(next)
  }

  function handleDrop(toIdx: number) {
    if (draggedIdx !== null && draggedIdx !== toIdx) moveStep(draggedIdx, toIdx)
    setDraggedIdx(null)
    setDragOverIdx(null)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-mono uppercase tracking-wider text-foreground/30">
          Steps ({steps.length})
        </p>
        <button
          type="button"
          onClick={addStep}
          className="inline-flex items-center gap-1.5 text-xs font-mono text-accent hover:underline"
        >
          <Plus size={12} strokeWidth={2} />
          Add step
        </button>
      </div>

      <div className="space-y-3">
        {steps.map((step, i) => (
          <StepCard
            key={step.id}
            index={i}
            draft={step}
            actions={actions}
            onChange={(updated) => updateStep(i, updated)}
            onRemove={() => removeStep(i)}
            onMoveUp={() => moveStep(i, i - 1)}
            onMoveDown={() => moveStep(i, i + 1)}
            isOnly={steps.length === 1}
            isFirst={i === 0}
            isLast={i === steps.length - 1}
            isDragging={draggedIdx === i}
            isDraggedOver={dragOverIdx === i && draggedIdx !== i}
            onDragStart={() => setDraggedIdx(i)}
            onDragOver={() => setDragOverIdx(i)}
            onDrop={() => handleDrop(i)}
            onDragEnd={() => { setDraggedIdx(null); setDragOverIdx(null) }}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={addStep}
        className="w-full border border-dashed border-foreground/20 py-3 font-mono text-sm text-foreground/30 hover:border-accent hover:text-accent transition-colors inline-flex items-center justify-center gap-2"
      >
        <Plus size={14} strokeWidth={1.5} />
        Add step
      </button>
    </div>
  )
}
