export interface OrganizationResponse {
  id: string
  name: string
  active_llm_id: string | null
  created_at: string
  updated_at: string
}

export interface UserMeResponse {
  id: string
  name: string
  email: string
  is_verified: boolean
  active_organization: OrganizationResponse | null
  organizations: OrganizationResponse[]
}

export interface CreateOrganizationRequest {
  name: string
}

export interface SetActiveOrgRequest {
  organization_id: string
}

export interface AssignRoleRequest {
  user_id: string
  role: string
}
