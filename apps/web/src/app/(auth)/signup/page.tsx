'use client'

import { useState, FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authService } from '@/features/auth/services/auth.service'
import { tokenStorage } from '@/lib/token'

type Step = 'register' | 'verify'

export default function SignupPage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>('register')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resendMsg, setResendMsg] = useState('')

  async function handleRegister(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const form = e.currentTarget
    const name = (form.elements.namedItem('name') as HTMLInputElement).value
    const emailVal = (form.elements.namedItem('email') as HTMLInputElement)
      .value
    const password = (form.elements.namedItem('password') as HTMLInputElement)
      .value

    try {
      await authService.signup({ name, email: emailVal, password })
      setEmail(emailVal)
      setStep('verify')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerify(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const form = e.currentTarget
    const otp = (form.elements.namedItem('otp') as HTMLInputElement).value

    try {
      const data = await authService.verifyEmail({ email, otp })
      tokenStorage.set(data.access_token)
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    setResendMsg('')
    setError('')
    try {
      const data = await authService.resendOtp({ email })
      setResendMsg(data.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6 py-24">
      <div className="w-full max-w-md space-y-12">
        {/* Back Link */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 font-mono text-sm text-foreground/60 transition-colors hover:text-accent"
        >
          ← Back to home
        </Link>

        {/* Logo/Brand */}
        <Link href="/" className="block transition-colors hover:text-accent">
          <h1 className="font-mono text-6xl tracking-tight">OpenOrch</h1>
        </Link>

        {step === 'register' ? (
          <>
            <div className="space-y-2">
              <h2 className="font-mono text-3xl">Create account</h2>
              <p className="font-mono text-sm text-foreground/60">
                Start testing your UI with AI
              </p>
            </div>

            <form onSubmit={handleRegister} className="space-y-6">
              <div className="space-y-2">
                <label htmlFor="name" className="block font-mono text-sm">
                  Name
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  required
                  placeholder="Jane Smith"
                  className="w-full border-2 border-foreground/20 bg-background px-4 py-3 font-mono text-foreground transition-colors placeholder:text-foreground/40 focus:border-accent focus:outline-none"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="email" className="block font-mono text-sm">
                  Email
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  placeholder="you@example.com"
                  className="w-full border-2 border-foreground/20 bg-background px-4 py-3 font-mono text-foreground transition-colors placeholder:text-foreground/40 focus:border-accent focus:outline-none"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="block font-mono text-sm">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  minLength={8}
                  placeholder="••••••••"
                  className="w-full border-2 border-foreground/20 bg-background px-4 py-3 font-mono text-foreground transition-colors placeholder:text-foreground/40 focus:border-accent focus:outline-none"
                />
                <p className="font-mono text-xs text-foreground/40">
                  Minimum 8 characters
                </p>
              </div>

              {error && (
                <div className="border-2 border-red-500 bg-red-500/10 p-3">
                  <p className="font-mono text-sm text-red-500">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full border-2 border-transparent bg-accent px-8 py-4 font-mono text-lg font-semibold text-black transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? 'Creating account...' : 'Create account'}
              </button>
            </form>

            <div className="text-center">
              <p className="font-mono text-sm text-foreground/60">
                Already have an account?{' '}
                <Link href="/login" className="text-accent hover:underline">
                  Sign in
                </Link>
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="space-y-2">
              <h2 className="font-mono text-3xl">Verify email</h2>
              <p className="font-mono text-sm text-foreground/60">
                We sent a 6-digit code to{' '}
                <span className="text-foreground">{email}</span>
              </p>
            </div>

            <form onSubmit={handleVerify} className="space-y-6">
              <div className="space-y-2">
                <label htmlFor="otp" className="block font-mono text-sm">
                  Verification code
                </label>
                <input
                  id="otp"
                  name="otp"
                  type="text"
                  required
                  maxLength={6}
                  placeholder="000000"
                  className="w-full border-2 border-foreground/20 bg-background px-4 py-3 text-center font-mono text-2xl tracking-widest text-foreground transition-colors placeholder:text-foreground/40 focus:border-accent focus:outline-none"
                />
              </div>

              {error && (
                <div className="border-2 border-red-500 bg-red-500/10 p-3">
                  <p className="font-mono text-sm text-red-500">{error}</p>
                </div>
              )}

              {resendMsg && (
                <div className="border-2 border-accent bg-accent/10 p-3">
                  <p className="font-mono text-sm text-accent">{resendMsg}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full border-2 border-transparent bg-accent px-8 py-4 font-mono text-lg font-semibold text-black transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? 'Verifying...' : 'Verify email'}
              </button>
            </form>

            <div className="space-y-3 text-center">
              <p className="font-mono text-sm text-foreground/60">
                Didn&apos;t receive the code?{' '}
                <button
                  onClick={handleResend}
                  className="font-mono text-sm text-accent hover:underline"
                >
                  Resend
                </button>
              </p>
              <p className="font-mono text-sm text-foreground/60">
                Wrong email?{' '}
                <button
                  onClick={() => {
                    setStep('register')
                    setError('')
                  }}
                  className="font-mono text-sm text-accent hover:underline"
                >
                  Go back
                </button>
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
