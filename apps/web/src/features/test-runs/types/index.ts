export type RunStatus = 'queued' | 'running' | 'passed' | 'failed'

export interface StepMarker {
  index: number
  description: string
  group: string | null
  status: string
  started_at_seconds: number
  duration_ms: number
  error: string | null
}

export interface PlayerRunResponse {
  id: string
  recording_url: string | null
  markers: StepMarker[]
}
export type GroupRunStatus = 'queued' | 'running' | 'passed' | 'failed' | 'partial'

export const TERMINAL_RUN_STATUSES: RunStatus[] = ['passed', 'failed']
export const TERMINAL_GROUP_STATUSES: GroupRunStatus[] = ['passed', 'failed', 'partial']

export interface StepResult {
  index: number
  action: string
  description: string
  group?: string | null
  status: string
  duration_ms: number
  logs: string[]
  screenshot_path?: string | null
  error?: string | null
}

export interface TestRunResponse {
  id: string
  test_case_id: string | null
  test_group_run_id: string | null
  status: RunStatus
  browser: string
  base_url_override: string | null
  viewport_width: number
  viewport_height: number
  step_results: StepResult[] | null
  recording_url: string | null
  trace_url: string | null
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface TestGroupRunResponse {
  id: string
  test_group_id: string | null
  status: GroupRunStatus
  browser: string
  base_url_override: string | null
  viewport_width: number
  viewport_height: number
  test_runs: TestRunResponse[]
  created_at: string
  updated_at: string
}
