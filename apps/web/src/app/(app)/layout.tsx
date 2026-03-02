'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import {
  LayoutDashboard,
  FlaskConical,
  Bot,
  Settings,
  LogOut,
} from 'lucide-react'
import { tokenStorage } from '@/lib/token'
import { userService } from '@/features/users/services/user.service'
import type { UserMeResponse } from '@/features/users/types'
import { Spinner } from '@/components/ui/spinner'
import { Container } from '@/components/ui/container'

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { href: '/test-groups', label: 'Test Groups', Icon: FlaskConical },
  { href: '/llms', label: 'LLMs', Icon: Bot },
  { href: '/settings', label: 'Settings', Icon: Settings },
]

function NavLink({
  href,
  label,
  Icon,
}: {
  href: string
  label: string
  Icon: React.ElementType
}) {
  const pathname = usePathname()
  const isActive =
    pathname === href ||
    (href !== '/dashboard' && pathname.startsWith(href + '/'))

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2.5 font-mono text-sm transition-colors ${
        isActive
          ? 'border-l-2 border-accent pl-[10px] text-accent'
          : 'border-l-2 border-transparent pl-[10px] text-foreground/50 hover:text-foreground'
      }`}
    >
      <Icon size={15} strokeWidth={1.5} />
      <span>{label}</span>
    </Link>
  )
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [checking, setChecking] = useState(true)
  const [user, setUser] = useState<UserMeResponse | null>(null)

  useEffect(() => {
    const token = tokenStorage.get()
    if (!token) {
      router.push('/login')
      return
    }

    userService
      .getMe()
      .then((me) => {
        setUser(me)
        if (me.active_organization === null) {
          router.push('/onboarding')
        }
      })
      .catch(() => {
        tokenStorage.remove()
        router.push('/login')
      })
      .finally(() => setChecking(false))
  }, [router])

  function handleLogout() {
    tokenStorage.remove()
    router.push('/login')
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="flex w-60 flex-shrink-0 flex-col border-r border-border">
        <div className="border-b border-border p-6">
          <Link
            href="/dashboard"
            className="font-mono text-xl font-bold tracking-tight transition-colors hover:text-accent"
          >
            OpenOrch
          </Link>
        </div>

        <nav className="flex-1 space-y-0.5 p-4">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
        </nav>

        <div className="space-y-3 border-t border-border p-4">
          {user && (
            <div className="space-y-0.5">
              <p className="font-mono text-xs uppercase tracking-wider text-foreground/30">
                {user.active_organization?.name ?? 'No org'}
              </p>
              <p className="truncate font-mono text-xs text-foreground/50">
                {user.email}
              </p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 font-mono text-xs text-foreground/40 transition-colors hover:text-red-400"
          >
            <LogOut size={12} strokeWidth={1.5} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Bar */}
        <header className="flex h-14 flex-shrink-0 items-center border-b border-border px-6">
          <div className="flex-1" />
          <button
            onClick={() => router.push('/settings')}
            className="font-mono text-sm text-foreground/50 transition-colors hover:text-foreground"
          >
            {user?.name ?? 'Profile'}
          </button>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-8">
          <Container size="full">{children}</Container>
        </main>
      </div>
    </div>
  )
}
