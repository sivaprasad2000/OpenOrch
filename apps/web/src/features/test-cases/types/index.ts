export interface TestCaseStep {
  action: string
  description: string
}

export interface StepGroup {
  type: 'group'
  name: string
  steps: TestCaseStep[]
}

export interface TestCasePayload {
  steps: (StepGroup | TestCaseStep)[]
}

export interface TestCaseResponse {
  id: string
  test_group_id: string
  payload: TestCasePayload
  created_at: string
  updated_at: string
}

export interface TestCaseCreate {
  payload: TestCasePayload
}

export interface TestCaseUpdate {
  payload: TestCasePayload
}
