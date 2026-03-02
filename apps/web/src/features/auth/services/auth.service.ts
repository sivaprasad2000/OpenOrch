import type {
  SignupRequest,
  SignupResponse,
  SigninRequest,
  TokenResponse,
  VerifyEmailRequest,
  VerifyEmailResponse,
  ResendOTPRequest,
  ResendOTPResponse,
} from '../types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  const data = await res.json()

  if (!res.ok) {
    // FastAPI detail can be a string or a validation error array
    const message =
      typeof data.detail === 'string'
        ? data.detail
        : Array.isArray(data.detail)
          ? (data.detail[0]?.msg ?? 'Something went wrong')
          : 'Something went wrong'
    throw new Error(message)
  }

  return data as T
}

export const authService = {
  signup(data: SignupRequest): Promise<SignupResponse> {
    return post('/api/v1/auth/signup', data)
  },

  signin(data: SigninRequest): Promise<TokenResponse> {
    return post('/api/v1/auth/signin', data)
  },

  verifyEmail(data: VerifyEmailRequest): Promise<VerifyEmailResponse> {
    return post('/api/v1/auth/verify-email', data)
  },

  resendOtp(data: ResendOTPRequest): Promise<ResendOTPResponse> {
    return post('/api/v1/auth/resend-otp', data)
  },
}
