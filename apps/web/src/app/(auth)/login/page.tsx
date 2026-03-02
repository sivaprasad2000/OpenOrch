'use client'

import { useState, FormEvent } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authService } from '@/features/auth/services/auth.service'
import { tokenStorage } from '@/lib/token'

export default function LoginPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const form = e.currentTarget
    const email = (form.elements.namedItem('email') as HTMLInputElement).value
    const password = (form.elements.namedItem('password') as HTMLInputElement).value

    try {
      const data = await authService.signin({ email, password })
      tokenStorage.set(data.access_token)
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24">
      <div className="max-w-md w-full space-y-12">
        {/* Back Link */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 font-mono text-sm text-foreground/60 hover:text-accent transition-colors"
        >
          ← Back to home
        </Link>

        {/* Logo/Brand */}
        <Link href="/" className="block hover:text-accent transition-colors">
          <h1 className="font-mono text-6xl tracking-tight">OpenOrch</h1>
        </Link>

        {/* Title */}
        <div className="space-y-2">
          <h2 className="font-mono text-3xl">Sign in</h2>
          <p className="font-mono text-sm text-foreground/60">
            Continue to your dashboard
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
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
              className="w-full px-4 py-3 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/40 font-mono focus:outline-none focus:border-accent transition-colors"
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
              placeholder="••••••••"
              className="w-full px-4 py-3 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/40 font-mono focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          {error && (
            <div className="p-3 border-2 border-red-500 bg-red-500/10">
              <p className="font-mono text-sm text-red-500">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full px-8 py-4 border-2 border-transparent bg-accent text-black font-mono text-lg font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        {/* Sign up link */}
        <div className="text-center">
          <p className="font-mono text-sm text-foreground/60">
            Don&apos;t have an account?{' '}
            <Link href="/signup" className="text-accent hover:underline">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
