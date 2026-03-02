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
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-24 bg-background">
      <div className="max-w-md w-full space-y-12">
        <Link href="/" className="block hover:text-accent transition-colors">
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
            {loading ? 'Creating...' : 'Create organization →'}
          </button>
        </form>
      </div>
    </div>
  )
}
