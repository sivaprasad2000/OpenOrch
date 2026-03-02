import { apiGet } from '@/lib/api-client'
import type { TestRunResponse, TestGroupRunResponse, PlayerRunResponse } from '../types'

export const testRunService = {
  getRun(id: string): Promise<TestRunResponse> {
    return apiGet(`/api/v1/test-runs/${id}`)
  },

  getRunPlayer(id: string): Promise<PlayerRunResponse> {
    return apiGet(`/api/v1/test-runs/${id}/player`)
  },

  getGroupRun(id: string): Promise<TestGroupRunResponse> {
    return apiGet(`/api/v1/test-group-runs/${id}`)
  },
}
