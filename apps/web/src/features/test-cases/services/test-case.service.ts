import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api-client'
import type { TestCaseCreate, TestCaseResponse, TestCaseUpdate } from '../types'
import type { RunConfig } from '@/features/test-groups/types'
import type { TestRunResponse } from '@/features/test-runs/types'

export const testCaseService = {
  list(groupId: string): Promise<TestCaseResponse[]> {
    return apiGet(`/api/v1/test-groups/${groupId}/test-cases`)
  },

  get(groupId: string, id: string): Promise<TestCaseResponse> {
    return apiGet(`/api/v1/test-groups/${groupId}/test-cases/${id}`)
  },

  create(groupId: string, data: TestCaseCreate): Promise<TestCaseResponse> {
    return apiPost(`/api/v1/test-groups/${groupId}/test-cases`, data)
  },

  update(
    groupId: string,
    id: string,
    data: TestCaseUpdate
  ): Promise<TestCaseResponse> {
    return apiPut(`/api/v1/test-groups/${groupId}/test-cases/${id}`, data)
  },

  delete(groupId: string, id: string): Promise<void> {
    return apiDelete(`/api/v1/test-groups/${groupId}/test-cases/${id}`)
  },

  run(id: string, config: RunConfig): Promise<TestRunResponse> {
    return apiPost(`/api/v1/test-cases/${id}/run`, config)
  },

  getRuns(id: string): Promise<TestRunResponse[]> {
    return apiGet(`/api/v1/test-cases/${id}/runs`)
  },

  getStepActions(): Promise<string[]> {
    return apiGet('/api/v1/step-actions')
  },
}
