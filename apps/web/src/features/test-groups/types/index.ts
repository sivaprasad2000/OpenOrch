export type TestGroupStatus = 'active' | 'archived'

export type RunBrowser = 'chromium' | 'firefox' | 'webkit'

export interface RunConfig {
  browser: RunBrowser
  viewport_width?: number
  viewport_height?: number
  base_url_override?: string
}

export interface TestGroupResponse {
  id: string
  name: string
  description?: string
  base_url?: string
  tags: string[]
  status: TestGroupStatus
  org_id: string
  user_id: string
  created_at: string
  updated_at: string
}

export interface TestGroupCreate {
  name: string
  description?: string
  base_url?: string
  tags?: string[]
}

export interface TestGroupUpdate {
  name?: string
  description?: string
  base_url?: string
  tags?: string[]
  status?: TestGroupStatus
}
