export interface SignupRequest {
  email: string
  name: string
  password: string
}

export interface SignupResponse {
  message: string
  user_id: string
  email: string
}

export interface SigninRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: string
  email: string
  is_verified: boolean
}

export interface VerifyEmailRequest {
  email: string
  otp: string
}

export interface VerifyEmailResponse {
  message: string
  access_token: string
  token_type: string
}

export interface ResendOTPRequest {
  email: string
}

export interface ResendOTPResponse {
  message: string
}
