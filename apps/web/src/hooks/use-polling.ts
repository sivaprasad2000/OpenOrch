'use client'

import { useEffect, useRef, useState } from 'react'

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  isTerminal: (data: T) => boolean,
  intervalMs = 2000
): { data: T | null; loading: boolean; error: string | null } {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isTerminalRef = useRef(isTerminal)
  isTerminalRef.current = isTerminal

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const result = await fetchFn()
        if (!cancelled) {
          setData(result)
          setError(null)
          if (isTerminalRef.current(result)) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current)
              intervalRef.current = null
            }
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    poll()
    intervalRef.current = setInterval(poll, intervalMs)

    return () => {
      cancelled = true
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs])

  return { data, loading, error }
}
