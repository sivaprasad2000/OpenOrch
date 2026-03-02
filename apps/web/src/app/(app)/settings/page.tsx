'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { LogOut, CheckCircle, Circle } from 'lucide-react'
import { userService } from '@/features/users/services/user.service'
import type { UserMeResponse } from '@/features/users/types'
import { tokenStorage } from '@/lib/token'
import { Spinner } from '@/components/ui/spinner'

const INPUT_CLS =
  'w-full px-3 py-2.5 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/30 font-mono text-sm focus:outline-none focus:border-accent transition-colors'
const SEC_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 border-2 border-foreground/30 text-foreground font-mono text-sm hover:bg-foreground/10 transition-colors'

export default function SettingsPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserMeResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // New org
  const [newOrgName, setNewOrgName] = useState('')
  const [creatingOrg, setCreatingOrg] = useState(false)
  const [orgError, setOrgError] = useState('')
  const [orgSuccess, setOrgSuccess] = useState('')

  function loadUser() {
    userService
      .getMe()
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadUser()
  }, [])

  async function handleSwitchOrg(orgId: string) {
    try {
      await userService.setActiveOrganization(orgId)
      loadUser()
    } catch {
      /* ignore */
    }
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault()
    if (!newOrgName.trim()) return
    setCreatingOrg(true)
    setOrgError('')
    setOrgSuccess('')
    try {
      const org = await userService.createOrganization({
        name: newOrgName.trim(),
      })
      await userService.setActiveOrganization(org.id)
      setNewOrgName('')
      setOrgSuccess(`Organization "${org.name}" created and set as active.`)
      loadUser()
    } catch (err) {
      setOrgError(
        err instanceof Error ? err.message : 'Failed to create organization'
      )
    } finally {
      setCreatingOrg(false)
    }
  }

  function handleLogout() {
    tokenStorage.remove()
    router.push('/login')
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="font-mono text-3xl font-bold tracking-tight">
          Settings
        </h1>
        <p className="mt-1 font-mono text-sm text-foreground/40">
          Manage your account and workspace
        </p>
      </div>

      {/* Profile */}
      <section className="space-y-5 border border-foreground/20 p-6">
        <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
          Profile
        </p>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Name
            </label>
            <input
              value={user?.name ?? ''}
              readOnly
              className={INPUT_CLS + ' cursor-not-allowed opacity-60'}
            />
          </div>
          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Email
            </label>
            <div className="flex items-center gap-3">
              <input
                value={user?.email ?? ''}
                readOnly
                className={INPUT_CLS + ' flex-1 cursor-not-allowed opacity-60'}
              />
              <div className="flex flex-shrink-0 items-center gap-1.5">
                {user?.is_verified ? (
                  <>
                    <CheckCircle
                      size={14}
                      strokeWidth={1.5}
                      className="text-green-500"
                    />
                    <span className="font-mono text-xs text-green-500">
                      verified
                    </span>
                  </>
                ) : (
                  <>
                    <Circle
                      size={14}
                      strokeWidth={1.5}
                      className="text-foreground/30"
                    />
                    <span className="font-mono text-xs text-foreground/40">
                      unverified
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Organization */}
      <section className="space-y-5 border border-foreground/20 p-6">
        <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
          Organization
        </p>

        {user?.organizations && user.organizations.length > 1 && (
          <div className="space-y-2">
            <p className="font-mono text-sm text-foreground/60">
              Switch organization
            </p>
            <div className="space-y-2">
              {user.organizations.map((org) => {
                const isActive = org.id === user.active_organization?.id
                return (
                  <button
                    key={org.id}
                    onClick={() => !isActive && handleSwitchOrg(org.id)}
                    disabled={isActive}
                    className={`flex w-full items-center justify-between border-2 px-4 py-3 text-left font-mono text-sm transition-colors ${
                      isActive
                        ? 'cursor-default border-accent text-foreground'
                        : 'border-foreground/20 text-foreground/60 hover:border-foreground/40 hover:text-foreground'
                    }`}
                  >
                    <span>{org.name}</span>
                    {isActive && (
                      <span className="text-xs text-accent">active</span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {!user?.organizations ||
          (user.organizations.length <= 1 && (
            <div className="space-y-1">
              <p className="font-mono text-sm text-foreground/60">
                Current organization
              </p>
              <p className="font-mono text-foreground">
                {user?.active_organization?.name ?? '—'}
              </p>
            </div>
          ))}

        <div className="space-y-3 border-t border-border pt-5">
          <p className="font-mono text-sm text-foreground/60">
            Create new organization
          </p>
          <form onSubmit={handleCreateOrg} className="flex gap-3">
            <input
              placeholder="Organization name"
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              className={INPUT_CLS + ' flex-1'}
            />
            <button
              type="submit"
              disabled={creatingOrg || !newOrgName.trim()}
              className={SEC_BTN}
            >
              {creatingOrg ? 'Creating...' : 'Create'}
            </button>
          </form>
          {orgError && (
            <div className="border-2 border-red-500 bg-red-500/10 p-3">
              <p className="font-mono text-sm text-red-500">{orgError}</p>
            </div>
          )}
          {orgSuccess && (
            <div className="border-2 border-accent bg-accent/10 p-3">
              <p className="font-mono text-sm text-accent">{orgSuccess}</p>
            </div>
          )}
        </div>
      </section>

      {/* Sign out */}
      <section className="space-y-4 border border-foreground/20 p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-sm">Sign out</p>
            <p className="mt-0.5 font-mono text-xs text-foreground/40">
              You will be redirected to the login page.
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="inline-flex items-center gap-2 border-2 border-red-500/50 px-5 py-2.5 font-mono text-sm text-red-400 transition-colors hover:bg-red-500/10"
          >
            <LogOut size={14} strokeWidth={1.5} />
            Sign out
          </button>
        </div>
      </section>
    </div>
  )
}
