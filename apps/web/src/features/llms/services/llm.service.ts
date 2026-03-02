import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from '@/lib/api-client'
import type { LLMCreate, LLMUpdate, LLMResponse } from '../types'
import type { OrganizationResponse } from '@/features/users/types'

export const llmService = {
  list(): Promise<LLMResponse[]> {
    return apiGet<LLMResponse[]>('/api/v1/llms').catch((err: Error) => {
      if (err.message.includes('404')) return []
      throw err
    })
  },

  create(data: LLMCreate): Promise<LLMResponse> {
    return apiPost('/api/v1/llms', data)
  },

  update(id: string, data: LLMUpdate): Promise<LLMResponse> {
    return apiPatch(`/api/v1/llms/${id}`, data)
  },

  delete(id: string): Promise<void> {
    return apiDelete(`/api/v1/llms/${id}`)
  },

  setActive(orgId: string, llmId: string): Promise<OrganizationResponse> {
    return apiPut(`/api/v1/organizations/${orgId}/active-llm`, {
      llm_id: llmId,
    })
  },

  unsetActive(orgId: string): Promise<void> {
    return apiDelete(`/api/v1/organizations/${orgId}/active-llm`)
  },
}
