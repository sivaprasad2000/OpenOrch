'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { userService } from '@/features/users/services/user.service'
import { Spinner } from '@/components/ui/spinner'

export default function OnboardingPage() {
  const router = useRouter()
  const [checking, setChecking] = useState(true)
  const [orgName, setOrgName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    userService
      .getMe()
      .then((me) => {
        if (me.active_organization !== null) {
          router.push('/dashboard')
        }
      })
      .catch(() => router.push('/login'))
      .finally(() => setChecking(false))
  }, [router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!orgName.trim()) return
    setLoading(true)
    setError('')
    try {
      const org = await userService.createOrganization({ name: orgName.trim() })
      await userService.setActiveOrganization(org.id)
      router.push('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6 py-24">
      <div className="w-full max-w-md space-y-12">
        <Link href="/" className="block transition-colors hover:text-accent">
          <h1 className="font-mono text-5xl tracking-tight">OpenOrch</h1>
        </Link>

        <div className="space-y-2">
          <h2 className="font-mono text-3xl">Create organization</h2>
          <p className="font-mono text-sm text-foreground/60">
            Set up your workspace to start testing.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label htmlFor="org-name" className="block font-mono text-sm">
              Organization name
            </label>
            <input
              id="org-name"
              type="text"
              required
              placeholder="Acme Corp"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              autoFocus
              className="w-full border-2 border-foreground/20 bg-background px-4 py-3 font-mono text-foreground transition-colors placeholder:text-foreground/40 focus:border-accent focus:outline-none"
            />
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
            {loading ? 'Creating...' : 'Create organization →'}
          </button>
        </form>
      </div>
    </div>
  )
}
