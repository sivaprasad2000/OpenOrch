import { apiGet, apiPost, apiPut } from '@/lib/api-client'
import type {
  UserMeResponse,
  OrganizationResponse,
  CreateOrganizationRequest,
  SetActiveOrgRequest,
  AssignRoleRequest,
} from '../types'

export const userService = {
  getMe(): Promise<UserMeResponse> {
    return apiGet('/api/v1/users/me')
  },

  setActiveOrganization(orgId: string): Promise<UserMeResponse> {
    const body: SetActiveOrgRequest = { organization_id: orgId }
    return apiPut('/api/v1/users/me/active-organization', body)
  },

  createOrganization(data: CreateOrganizationRequest): Promise<OrganizationResponse> {
    return apiPost('/api/v1/organizations', data)
  },

  assignRole(orgId: string, data: AssignRoleRequest): Promise<void> {
    return apiPost(`/api/v1/organizations/${orgId}/members`, data)
  },
}
