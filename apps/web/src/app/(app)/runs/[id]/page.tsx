'use client'

import { use, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  Video,
} from 'lucide-react'
import { testRunService } from '@/features/test-runs/services/test-run.service'
import { TERMINAL_RUN_STATUSES } from '@/features/test-runs/types'
import type { StepMarker, StepResult } from '@/features/test-runs/types'
import { usePolling } from '@/hooks/use-polling'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { runStatusToBadge } from '@/lib/status'
import { formatDateTime, shortId } from '@/lib/format'
import { VideoPlayer, formatTime } from '@/components/ui/video-player'
import type { VideoPlayerHandle } from '@/components/ui/video-player'

// ─── Step list panel ─────────────────────────────────────────────────────────

interface StepGroup {
  name: string | null
  items: StepMarker[]
}

function buildGroups(markers: StepMarker[]): StepGroup[] {
  const groups: StepGroup[] = []
  for (const m of markers) {
    const last = groups[groups.length - 1]
    if (last && last.name === m.group) {
      last.items.push(m)
    } else {
      groups.push({ name: m.group, items: [m] })
    }
  }
  return groups
}

function getActiveIndex(markers: StepMarker[], currentTime: number): number {
  for (let i = 0; i < markers.length; i++) {
    const start = markers[i].started_at_seconds
    const end =
      i < markers.length - 1 ? markers[i + 1].started_at_seconds : Infinity
    if (currentTime >= start && currentTime < end) return i
  }
  return -1
}

function StepListPanel({
  markers,
  stepResults,
  currentTime,
  onSeekTo,
  isLoading,
}: {
  markers: StepMarker[]
  stepResults: StepResult[]
  currentTime: number
  onSeekTo: (seconds: number) => void
  isLoading: boolean
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set())
  const stepRefs = useRef<(HTMLDivElement | null)[]>([])
  const didAutoScrollRef = useRef(-1)

  const stepResultMap = useMemo(() => {
    const map = new Map<number, StepResult>()
    for (const s of stepResults) map.set(s.index, s)
    return map
  }, [stepResults])

  const activeIndex = useMemo(
    () => getActiveIndex(markers, currentTime),
    [markers, currentTime]
  )

  // Auto-scroll active step into view
  useEffect(() => {
    if (activeIndex >= 0 && activeIndex !== didAutoScrollRef.current) {
      didAutoScrollRef.current = activeIndex
      stepRefs.current[activeIndex]?.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      })
    }
  }, [activeIndex])

  const toggleGroup = useCallback((name: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }, [])

  const toggleStep = useCallback((index: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }, [])

  if (isLoading) {
    return (
      <div className="space-y-px">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse border-b border-border bg-foreground/[0.04]"
            style={{ opacity: 1 - i * 0.15 }}
          />
        ))}
      </div>
    )
  }

  if (markers.length === 0) {
    return (
      <div className="p-6 text-center">
        <p className="font-mono text-sm text-foreground/30">
          Steps will appear as the run progresses...
        </p>
      </div>
    )
  }

  const groups = buildGroups(markers)

  return (
    <div>
      {groups.map((group, gi) => (
        <div key={gi}>
          {/* Named group header */}
          {group.name && (
            <button
              onClick={() => toggleGroup(group.name!)}
              className="sticky top-0 z-10 flex w-full items-center gap-2 border-b border-border bg-foreground/[0.03] px-4 py-2 text-left transition-colors hover:bg-foreground/[0.06]"
            >
              {collapsed.has(group.name) ? (
                <ChevronRight
                  size={11}
                  className="flex-shrink-0 text-foreground/30"
                />
              ) : (
                <ChevronDown
                  size={11}
                  className="flex-shrink-0 text-foreground/30"
                />
              )}
              <span className="truncate font-mono text-xs text-foreground/50">
                {group.name}
              </span>
              <span className="ml-auto flex-shrink-0 font-mono text-[10px] text-foreground/25">
                {group.items.length}
              </span>
            </button>
          )}

          {/* Step rows */}
          {!collapsed.has(group.name ?? '') &&
            group.items.map((m) => {
              const isActive = m.index === activeIndex
              const result = stepResultMap.get(m.index)
              const logs = result?.logs ?? []
              const isExpanded = expandedSteps.has(m.index)
              const hasLogs = logs.length > 0 || !!result?.error

              return (
                <div
                  key={m.index}
                  ref={(el) => {
                    stepRefs.current[m.index] = el
                  }}
                  className={`border-b border-border ${
                    isActive
                      ? 'border-l-2 border-l-accent bg-accent/[0.06]'
                      : 'border-l-2 border-l-transparent'
                  }`}
                >
                  {/* Main step row */}
                  <div className="flex items-center gap-1">
                    {/* Expand toggle */}
                    <button
                      onClick={() => toggleStep(m.index)}
                      className={`flex h-full w-7 flex-shrink-0 items-center justify-center py-3 pl-2 transition-colors ${
                        hasLogs
                          ? 'text-foreground/30 hover:text-foreground/60'
                          : 'cursor-default text-foreground/10'
                      }`}
                      disabled={!hasLogs}
                      aria-label={isExpanded ? 'Collapse logs' : 'Expand logs'}
                    >
                      {isExpanded ? (
                        <ChevronDown size={10} />
                      ) : (
                        <ChevronRight size={10} />
                      )}
                    </button>

                    {/* Seek area */}
                    <button
                      onClick={() => onSeekTo(m.started_at_seconds)}
                      className="flex min-w-0 flex-1 items-center gap-3 py-3 pr-4 text-left transition-colors hover:bg-foreground/[0.04]"
                    >
                      {/* Step number */}
                      <span className="w-5 flex-shrink-0 font-mono text-[10px] tabular-nums text-foreground/25">
                        {String(m.index + 1).padStart(2, '0')}
                      </span>

                      {/* Description */}
                      <span
                        className={`flex-1 truncate font-mono text-xs ${
                          isActive ? 'text-foreground' : 'text-foreground/70'
                        }`}
                      >
                        {m.description}
                      </span>

                      {/* Status chip */}
                      <span
                        className={`flex-shrink-0 border px-1 py-px font-mono text-[10px] ${
                          m.status === 'passed'
                            ? 'border-green-500/50 text-green-400'
                            : m.status === 'failed'
                              ? 'border-red-500/50 text-red-400'
                              : 'border-foreground/20 text-foreground/40'
                        }`}
                      >
                        {m.status}
                      </span>

                      {/* Timestamp */}
                      <span className="w-10 flex-shrink-0 text-right font-mono text-[10px] tabular-nums text-foreground/30">
                        {formatTime(m.started_at_seconds)}
                      </span>
                    </button>
                  </div>

                  {/* Logs panel */}
                  {isExpanded && hasLogs && (
                    <div className="ml-7 mr-0 space-y-1 border-t border-border bg-foreground/[0.02] px-4 py-3">
                      {result?.error && (
                        <p className="mb-2 font-mono text-[11px] text-red-400">
                          {result.error}
                        </p>
                      )}
                      {logs.length > 0 ? (
                        logs.map((line, li) => (
                          <p
                            key={li}
                            className="whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-foreground/50"
                          >
                            {line}
                          </p>
                        ))
                      ) : (
                        <p className="font-mono text-[11px] text-foreground/25">
                          No log lines.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
        </div>
      ))}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const playerRef = useRef<VideoPlayerHandle>(null)
  const [videoTime, setVideoTime] = useState(0)

  const {
    data: run,
    loading: runLoading,
    error: runError,
  } = usePolling(
    () => testRunService.getRun(id),
    (data) => TERMINAL_RUN_STATUSES.includes(data.status)
  )

  const {
    data: playerData,
    loading: playerLoading,
    error: playerError,
  } = usePolling(
    () => testRunService.getRunPlayer(id),
    () => (run ? TERMINAL_RUN_STATUSES.includes(run.status) : false)
  )

  const handleSeekTo = useCallback((seconds: number) => {
    playerRef.current?.seekTo(seconds)
  }, [])

  // ── Loading state ──
  if (runLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  // ── Error / not found ──
  if (runError || !run) {
    return (
      <div className="space-y-4">
        <div className="border-2 border-red-500 bg-red-500/10 p-3">
          <p className="font-mono text-sm text-red-500">
            {runError ?? 'Run not found'}
          </p>
        </div>
        <Link
          href="/test-groups"
          className="inline-flex items-center gap-1 font-mono text-sm text-accent hover:underline"
        >
          <ArrowLeft size={12} /> Back
        </Link>
      </div>
    )
  }

  const isLive = !TERMINAL_RUN_STATUSES.includes(run.status)
  const markers = playerData?.markers ?? []
  const recordingUrl = playerData?.recording_url ?? run.recording_url

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 font-mono text-sm text-foreground/40">
        <Link
          href="/test-groups"
          className="inline-flex items-center gap-1 transition-colors hover:text-accent"
        >
          <ArrowLeft size={12} /> Test Groups
        </Link>
        <span>/</span>
        <span className="text-foreground">Run {shortId(id)}</span>
      </div>

      {/* Header */}
      <div
        className={`space-y-4 border p-6 ${isLive ? 'border-accent/70' : 'border-foreground/20'}`}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={runStatusToBadge(run.status)}>{run.status}</Badge>
              <span className="font-mono text-sm text-foreground/40">
                {run.browser}
              </span>
              <span className="font-mono text-sm text-foreground/40">
                {run.viewport_width}×{run.viewport_height}
              </span>
              {isLive && (
                <span className="inline-flex items-center gap-1.5 font-mono text-xs text-accent">
                  <Loader2 size={11} className="animate-spin" />
                  Polling...
                </span>
              )}
            </div>
            <div className="flex gap-6 font-mono text-sm">
              {run.started_at && (
                <div>
                  <span className="mb-0.5 block text-xs uppercase tracking-wider text-foreground/30">
                    Started
                  </span>
                  <span className="text-foreground/70">
                    {formatDateTime(run.started_at)}
                  </span>
                </div>
              )}
              {run.completed_at && (
                <div>
                  <span className="mb-0.5 block text-xs uppercase tracking-wider text-foreground/30">
                    Completed
                  </span>
                  <span className="text-foreground/70">
                    {formatDateTime(run.completed_at)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Error box */}
      {run.error && (
        <div className="border-2 border-red-500 bg-red-500/10 p-4">
          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-red-500/60">
            Error
          </p>
          <p className="font-mono text-sm text-red-400">{run.error}</p>
        </div>
      )}

      {/* Player + Step list */}
      <div className="flex flex-col items-start gap-6 lg:flex-row">
        {/* Left: video player */}
        <div className="w-full min-w-0 space-y-3 lg:flex-[2]">
          <div className="flex items-center gap-2">
            <Video size={13} className="text-foreground/40" />
            <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
              Recording
            </p>
          </div>

          {/* Player area */}
          {playerLoading && !playerData ? (
            /* Skeleton while first player fetch is in-flight */
            <div className="flex aspect-video items-center justify-center border border-foreground/20 bg-foreground/[0.03]">
              <Spinner size="lg" />
            </div>
          ) : playerError ? (
            /* 404 or fetch error */
            <div className="flex aspect-video flex-col items-center justify-center gap-3 border border-foreground/20 bg-foreground/[0.03]">
              <Video size={32} className="text-foreground/20" />
              <p className="font-mono text-sm text-foreground/40">
                Recording not found
              </p>
            </div>
          ) : !recordingUrl ? (
            /* recording_url is null */
            <div className="flex aspect-video flex-col items-center justify-center gap-3 border border-foreground/20 bg-foreground/[0.03]">
              <Video size={32} className="text-foreground/20" />
              <p className="font-mono text-sm text-foreground/40">
                Recording not available
              </p>
            </div>
          ) : (
            <VideoPlayer
              ref={playerRef}
              src={recordingUrl}
              markers={markers}
              onTimeUpdate={setVideoTime}
              className="w-full"
            />
          )}

          {/* Trace URL */}
          {run.trace_url && (
            <div className="flex items-center justify-between border border-foreground/20 px-4 py-3">
              <div className="flex items-center gap-2">
                <ExternalLink size={13} className="text-foreground/40" />
                <span className="font-mono text-xs uppercase tracking-wider text-foreground/30">
                  Playwright Trace
                </span>
              </div>
              <a
                href={`https://trace.playwright.dev/?trace=${encodeURIComponent(run.trace_url)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono text-xs text-accent hover:underline"
              >
                Open in Trace Viewer <ExternalLink size={10} />
              </a>
            </div>
          )}
        </div>

        {/* Right: step list */}
        <div
          className="max-h-80 w-full min-w-0 overflow-y-auto border border-foreground/20 lg:max-h-none lg:flex-1 lg:self-stretch"
          style={{ scrollbarWidth: 'thin' }}
        >
          <div className="sticky top-0 z-20 flex items-center gap-2 border-b border-border bg-background px-4 py-3">
            <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
              Steps
            </p>
            {markers.length > 0 && (
              <span className="font-mono text-xs text-foreground/25">
                ({markers.length})
              </span>
            )}
          </div>
          <StepListPanel
            markers={markers}
            stepResults={run.step_results ?? []}
            currentTime={videoTime}
            onSeekTo={handleSeekTo}
            isLoading={playerLoading && !playerData}
          />
        </div>
      </div>
    </div>
  )
}
