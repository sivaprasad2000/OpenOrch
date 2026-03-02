'use client'

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import {
  Loader2,
  Maximize,
  Minimize,
  Pause,
  Play,
  Volume2,
  VolumeX,
} from 'lucide-react'
import type { StepMarker } from '@/features/test-runs/types'

export function formatTime(seconds: number): string {
  if (isNaN(seconds) || !isFinite(seconds) || seconds < 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

const SPEEDS = [0.5, 1, 1.5, 2]

export interface VideoPlayerHandle {
  seekTo: (seconds: number) => void
}

interface VideoPlayerProps {
  src: string
  markers?: StepMarker[]
  onTimeUpdate?: (currentTime: number) => void
  className?: string
}

export const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(
  function VideoPlayer({ src, markers = [], onTimeUpdate, className = '' }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const seekBarRef = useRef<HTMLDivElement>(null)
    const volumeBarRef = useRef<HTMLDivElement>(null)
    const controlsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const wasPlayingRef = useRef(false)

    const [playing, setPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(0)
    const [metadataLoaded, setMetadataLoaded] = useState(false)
    const [buffered, setBuffered] = useState(0)
    const [volume, setVolume] = useState(1)
    const [muted, setMuted] = useState(false)
    const [fullscreen, setFullscreen] = useState(false)
    const [loading, setLoading] = useState(false)
    const [controlsVisible, setControlsVisible] = useState(true)
    const [isSeeking, setIsSeeking] = useState(false)
    const [isVolumeDragging, setIsVolumeDragging] = useState(false)
    const [seekHover, setSeekHover] = useState(false)
    const [volumeHover, setVolumeHover] = useState(false)
    const [speedIndex, setSpeedIndex] = useState(1) // default 1×
    const [hoveredMarker, setHoveredMarker] = useState<number | null>(null)

    // — Expose seekTo imperatively —
    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        const v = videoRef.current
        if (!v) return
        v.currentTime = seconds
        setCurrentTime(seconds)
      },
    }), [])

    // — Controls auto-hide —
    const scheduleHide = useCallback(() => {
      if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current)
      controlsTimerRef.current = setTimeout(() => setControlsVisible(false), 3000)
    }, [])

    const revealControls = useCallback(() => {
      setControlsVisible(true)
      if (videoRef.current && !videoRef.current.paused) scheduleHide()
    }, [scheduleHide])

    useEffect(() => {
      if (playing) scheduleHide()
      else {
        setControlsVisible(true)
        if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current)
      }
      return () => {
        if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current)
      }
    }, [playing, scheduleHide])

    // — Video event listeners —
    useEffect(() => {
      const v = videoRef.current
      if (!v) return

      const onPlay = () => setPlaying(true)
      const onPause = () => setPlaying(false)
      const onTimeUpdateEv = () => {
        setCurrentTime(v.currentTime)
        onTimeUpdate?.(v.currentTime)
      }
      const onLoadedMetadata = () => {
        setDuration(v.duration)
        setMetadataLoaded(true)
      }
      const onVolumeChange = () => {
        setVolume(v.volume)
        setMuted(v.muted)
      }
      const onWaiting = () => setLoading(true)
      const onCanPlay = () => setLoading(false)
      const onEnded = () => setPlaying(false)
      const onProgress = () => {
        if (v.buffered.length > 0 && v.duration) {
          setBuffered(v.buffered.end(v.buffered.length - 1) / v.duration)
        }
      }

      v.addEventListener('play', onPlay)
      v.addEventListener('pause', onPause)
      v.addEventListener('timeupdate', onTimeUpdateEv)
      v.addEventListener('loadedmetadata', onLoadedMetadata)
      v.addEventListener('volumechange', onVolumeChange)
      v.addEventListener('waiting', onWaiting)
      v.addEventListener('canplay', onCanPlay)
      v.addEventListener('ended', onEnded)
      v.addEventListener('progress', onProgress)

      // Seed state if metadata already available (e.g. cached video)
      if (v.readyState >= 1 && v.duration) {
        setDuration(v.duration)
        setMetadataLoaded(true)
      }

      return () => {
        v.removeEventListener('play', onPlay)
        v.removeEventListener('pause', onPause)
        v.removeEventListener('timeupdate', onTimeUpdateEv)
        v.removeEventListener('loadedmetadata', onLoadedMetadata)
        v.removeEventListener('volumechange', onVolumeChange)
        v.removeEventListener('waiting', onWaiting)
        v.removeEventListener('canplay', onCanPlay)
        v.removeEventListener('ended', onEnded)
        v.removeEventListener('progress', onProgress)
      }
    // onTimeUpdate is stable from parent; eslint can't verify, intentional dep omission
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    // — Fullscreen listener —
    useEffect(() => {
      const onFsChange = () => setFullscreen(!!document.fullscreenElement)
      document.addEventListener('fullscreenchange', onFsChange)
      return () => document.removeEventListener('fullscreenchange', onFsChange)
    }, [])

    // — Seek bar —
    const getSeekPct = useCallback((e: MouseEvent | React.MouseEvent) => {
      if (!seekBarRef.current) return 0
      const rect = seekBarRef.current.getBoundingClientRect()
      return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    }, [])

    const applySeek = useCallback((pct: number) => {
      const v = videoRef.current
      if (!v || !v.duration) return
      const t = pct * v.duration
      v.currentTime = t
      setCurrentTime(t)
    }, [])

    const onSeekMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault()
      const v = videoRef.current
      if (!v) return
      wasPlayingRef.current = !v.paused
      v.pause()
      setIsSeeking(true)
      applySeek(getSeekPct(e))
    }, [applySeek, getSeekPct])

    useEffect(() => {
      if (!isSeeking) return
      const onMove = (e: MouseEvent) => applySeek(getSeekPct(e))
      const onUp = () => {
        setIsSeeking(false)
        if (wasPlayingRef.current) videoRef.current?.play()
      }
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
      return () => {
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
    }, [isSeeking, applySeek, getSeekPct])

    // — Volume bar —
    const getVolumePct = useCallback((e: MouseEvent | React.MouseEvent) => {
      if (!volumeBarRef.current) return 0
      const rect = volumeBarRef.current.getBoundingClientRect()
      return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    }, [])

    const applyVolume = useCallback((pct: number) => {
      const v = videoRef.current
      if (!v) return
      v.volume = pct
      v.muted = pct === 0
      setVolume(pct)
      setMuted(pct === 0)
    }, [])

    const onVolumeMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsVolumeDragging(true)
      applyVolume(getVolumePct(e))
    }, [applyVolume, getVolumePct])

    useEffect(() => {
      if (!isVolumeDragging) return
      const onMove = (e: MouseEvent) => applyVolume(getVolumePct(e))
      const onUp = () => setIsVolumeDragging(false)
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
      return () => {
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
    }, [isVolumeDragging, applyVolume, getVolumePct])

    // — Control actions —
    const togglePlay = useCallback(() => {
      const v = videoRef.current
      if (!v) return
      if (v.paused) v.play()
      else v.pause()
    }, [])

    const toggleMute = useCallback(() => {
      const v = videoRef.current
      if (!v) return
      v.muted = !v.muted
      setMuted(v.muted)
    }, [])

    const toggleFullscreen = useCallback(() => {
      const c = containerRef.current
      if (!c) return
      if (!document.fullscreenElement) c.requestFullscreen()
      else document.exitFullscreen()
    }, [])

    const cycleSpeed = useCallback(() => {
      const next = (speedIndex + 1) % SPEEDS.length
      setSpeedIndex(next)
      const v = videoRef.current
      if (v) v.playbackRate = SPEEDS[next]
    }, [speedIndex])

    // — Keyboard shortcuts —
    const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
      const v = videoRef.current
      if (!v) return
      switch (e.key) {
        case ' ':
        case 'k':
          e.preventDefault()
          togglePlay()
          break
        case 'ArrowLeft':
          e.preventDefault()
          v.currentTime = Math.max(0, v.currentTime - 5)
          break
        case 'ArrowRight':
          e.preventDefault()
          v.currentTime = Math.min(v.duration || 0, v.currentTime + 5)
          break
        case 'm':
        case 'M':
          e.preventDefault()
          toggleMute()
          break
        case 'f':
        case 'F':
          e.preventDefault()
          toggleFullscreen()
          break
      }
    }, [togglePlay, toggleMute, toggleFullscreen])

    const playedPct = duration > 0 ? (currentTime / duration) * 100 : 0
    const effectiveVolume = muted ? 0 : volume

    return (
      <div
        ref={containerRef}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onMouseMove={revealControls}
        className={`relative bg-black border border-foreground/20 outline-none focus:ring-1 focus:ring-accent/50 aspect-video ${className}`}
        style={{ cursor: controlsVisible ? 'default' : 'none' }}
      >
        {/* Native video element */}
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video
          ref={videoRef}
          src={src}
          className="absolute inset-0 w-full h-full object-contain"
          onClick={togglePlay}
          style={{ cursor: 'pointer' }}
        />

        {/* Buffering spinner */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <Loader2 size={32} className="text-accent animate-spin opacity-80" />
          </div>
        )}

        {/* Paused overlay */}
        {!playing && !loading && (
          <div
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
            aria-hidden="true"
          >
            <div className="w-16 h-16 bg-black/40 border border-foreground/20 flex items-center justify-center">
              <Play size={28} className="text-foreground/70 translate-x-0.5" />
            </div>
          </div>
        )}

        {/* Controls overlay */}
        <div
          className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent px-4 pb-3 pt-10 transition-opacity duration-300"
          style={{ opacity: controlsVisible ? 1 : 0, pointerEvents: controlsVisible ? 'auto' : 'none' }}
        >
          {/* Seek bar */}
          <div
            ref={seekBarRef}
            className="w-full mb-3 cursor-pointer relative"
            style={{ height: seekHover || isSeeking ? 10 : 4, transition: 'height 0.15s ease' }}
            onMouseDown={onSeekMouseDown}
            onMouseEnter={() => setSeekHover(true)}
            onMouseLeave={() => { setSeekHover(false); setHoveredMarker(null) }}
          >
            {/* Track */}
            <div className="absolute inset-0 bg-foreground/10" />
            {/* Buffered */}
            <div
              className="absolute top-0 left-0 h-full bg-foreground/25"
              style={{ width: `${buffered * 100}%`, transition: 'width 0.2s linear' }}
            />
            {/* Played */}
            <div
              className="absolute top-0 left-0 h-full bg-[#A7C7FF]"
              style={{ width: `${playedPct}%` }}
            />

            {/* Step markers — deferred until loadedmetadata */}
            {metadataLoaded && markers.map((m, i) => {
              const pct = (m.started_at_seconds / duration) * 100
              const isHovered = hoveredMarker === i
              // Clamp tooltip so it doesn't go off left/right edges
              const tooltipAlign = pct < 15 ? '0%' : pct > 85 ? '-100%' : '-50%'

              return (
                <div
                  key={i}
                  className="absolute top-0 h-full"
                  style={{ left: `${pct}%`, transform: 'translateX(-50%)', zIndex: 10, width: 8 }}
                  onMouseEnter={(e) => { e.stopPropagation(); setHoveredMarker(i) }}
                  onMouseLeave={(e) => { e.stopPropagation(); setHoveredMarker(null) }}
                  onMouseDown={(e) => {
                    e.stopPropagation()
                    e.preventDefault()
                    const v = videoRef.current
                    if (!v) return
                    wasPlayingRef.current = !v.paused
                    v.pause()
                    v.currentTime = m.started_at_seconds
                    setCurrentTime(m.started_at_seconds)
                    onTimeUpdate?.(m.started_at_seconds)
                    v.addEventListener('seeked', function onSeeked() {
                      v.removeEventListener('seeked', onSeeked)
                      if (wasPlayingRef.current) v.play()
                    }, { once: true })
                  }}
                >
                  {/* Tick line */}
                  <div
                    className={`absolute left-1/2 -translate-x-1/2 top-0 h-full w-px ${
                      m.status === 'failed' ? 'bg-red-400' : 'bg-white/60'
                    }`}
                  />

                  {/* Tooltip */}
                  {isHovered && (
                    <div
                      className="absolute bottom-full mb-3 font-mono bg-[#0a0a0a] border border-foreground/20 p-2 text-xs pointer-events-none z-50"
                      style={{
                        left: '50%',
                        transform: `translateX(${tooltipAlign})`,
                        minWidth: 180,
                        maxWidth: 260,
                      }}
                    >
                      <div className="text-foreground/40 mb-0.5 text-[10px] uppercase tracking-wider">
                        Step {m.index + 1}
                      </div>
                      {m.group && (
                        <div className="text-foreground/40 mb-0.5 truncate">{m.group} ›</div>
                      )}
                      <div className="text-foreground font-semibold mb-2 whitespace-normal leading-tight">
                        {m.description}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`border text-[10px] px-1 py-px ${
                            m.status === 'passed'
                              ? 'border-green-500 text-green-400'
                              : 'border-red-500 text-red-400'
                          }`}
                        >
                          {m.status}
                        </span>
                        <span className="text-foreground/40 tabular-nums">
                          {formatTime(m.started_at_seconds)}
                        </span>
                        <span className="text-foreground/30">{m.duration_ms}ms</span>
                      </div>
                      {m.error && (
                        <div className="mt-1.5 text-red-400 text-[11px] whitespace-normal leading-tight">
                          {m.error}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Scrubber thumb */}
            <div
              className="absolute top-1/2 w-3 h-3 bg-[#A7C7FF] border border-black/40 pointer-events-none transition-opacity duration-150"
              style={{
                left: `${playedPct}%`,
                transform: 'translate(-50%, -50%)',
                opacity: seekHover || isSeeking ? 1 : 0,
                zIndex: 20,
              }}
            />
          </div>

          {/* Bottom controls row */}
          <div className="flex items-center gap-1">
            {/* Play / Pause */}
            <button
              onClick={togglePlay}
              className="p-1.5 text-foreground/70 hover:text-foreground transition-colors cursor-pointer"
              aria-label={playing ? 'Pause' : 'Play'}
            >
              {playing ? <Pause size={15} /> : <Play size={15} />}
            </button>

            {/* Time display */}
            <span className="text-xs font-mono text-foreground/50 select-none ml-1 tabular-nums">
              {formatTime(currentTime)}&nbsp;/&nbsp;{formatTime(duration)}
            </span>

            <div className="flex-1" />

            {/* Playback speed */}
            <button
              onClick={cycleSpeed}
              className="p-1.5 text-foreground/70 hover:text-foreground transition-colors cursor-pointer font-mono text-xs tabular-nums min-w-[28px] text-center"
              aria-label="Cycle playback speed"
              title={`Playback speed: ${SPEEDS[speedIndex]}×`}
            >
              {SPEEDS[speedIndex]}×
            </button>

            {/* Volume section */}
            <div
              className="flex items-center gap-1.5"
              onMouseEnter={() => setVolumeHover(true)}
              onMouseLeave={() => setVolumeHover(false)}
            >
              <button
                onClick={toggleMute}
                className="p-1.5 text-foreground/70 hover:text-foreground transition-colors cursor-pointer"
                aria-label={muted ? 'Unmute' : 'Mute'}
              >
                {muted || volume === 0 ? <VolumeX size={15} /> : <Volume2 size={15} />}
              </button>

              {/* Volume bar */}
              <div
                ref={volumeBarRef}
                className="relative cursor-pointer flex-shrink-0"
                style={{
                  width: 72,
                  height: volumeHover || isVolumeDragging ? 8 : 3,
                  transition: 'height 0.15s ease',
                }}
                onMouseDown={onVolumeMouseDown}
              >
                <div className="absolute inset-0 bg-foreground/10" />
                <div
                  className="absolute top-0 left-0 h-full bg-[#A7C7FF]"
                  style={{ width: `${effectiveVolume * 100}%` }}
                />
                <div
                  className="absolute top-1/2 w-2.5 h-2.5 bg-[#A7C7FF] border border-black/40 transition-opacity duration-150"
                  style={{
                    left: `${effectiveVolume * 100}%`,
                    transform: 'translate(-50%, -50%)',
                    opacity: volumeHover || isVolumeDragging ? 1 : 0,
                  }}
                />
              </div>
            </div>

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              className="p-1.5 text-foreground/70 hover:text-foreground transition-colors cursor-pointer ml-1"
              aria-label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            >
              {fullscreen ? <Minimize size={15} /> : <Maximize size={15} />}
            </button>
          </div>
        </div>
      </div>
    )
  }
)
