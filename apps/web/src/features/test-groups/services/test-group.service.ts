import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api-client'
import type {
  TestGroupCreate,
  TestGroupResponse,
  TestGroupUpdate,
  RunConfig,
} from '../types'
import type { TestGroupRunResponse } from '@/features/test-runs/types'

export const testGroupService = {
  list(): Promise<TestGroupResponse[]> {
    return apiGet('/api/v1/test-groups')
  },

  get(id: string): Promise<TestGroupResponse> {
    return apiGet(`/api/v1/test-groups/${id}`)
  },

  create(data: TestGroupCreate): Promise<TestGroupResponse> {
    return apiPost('/api/v1/test-groups', data)
  },

  update(id: string, data: TestGroupUpdate): Promise<TestGroupResponse> {
    return apiPut(`/api/v1/test-groups/${id}`, data)
  },

  delete(id: string): Promise<void> {
    return apiDelete(`/api/v1/test-groups/${id}`)
  },

  run(id: string, config: RunConfig): Promise<TestGroupRunResponse> {
    return apiPost(`/api/v1/test-groups/${id}/run`, config)
  },

  getRuns(id: string): Promise<TestGroupRunResponse[]> {
    return apiGet(`/api/v1/test-groups/${id}/runs`)
  },
}
