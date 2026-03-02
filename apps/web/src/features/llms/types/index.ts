export type LLMProvider =
  | 'openai'
  | 'anthropic'
  | 'google'
  | 'mistral'
  | 'cohere'
  | 'meta'
  | 'open_router'

export interface LLMResponse {
  id: string
  name: string
  provider: LLMProvider
  model_name: string
  is_active: boolean
  organization_id: string
  created_at: string
  updated_at: string
}

export interface LLMCreate {
  name: string
  provider: LLMProvider
  api_key: string
  model_name: string
}

export interface LLMUpdate {
  name?: string
  api_key?: string
  model_name?: string
}
