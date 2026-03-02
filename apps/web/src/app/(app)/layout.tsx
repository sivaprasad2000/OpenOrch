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
          ? 'text-accent border-l-2 border-accent pl-[10px]'
          : 'text-foreground/50 hover:text-foreground border-l-2 border-transparent pl-[10px]'
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
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex bg-background">
      {/* Sidebar */}
      <aside className="w-60 border-r border-border flex flex-col flex-shrink-0">
        <div className="p-6 border-b border-border">
          <Link
            href="/dashboard"
            className="font-mono text-xl font-bold tracking-tight hover:text-accent transition-colors"
          >
            OpenOrch
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
        </nav>

        <div className="p-4 border-t border-border space-y-3">
          {user && (
            <div className="space-y-0.5">
              <p className="text-xs font-mono uppercase tracking-wider text-foreground/30">
                {user.active_organization?.name ?? 'No org'}
              </p>
              <p className="text-xs font-mono text-foreground/50 truncate">
                {user.email}
              </p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-xs font-mono text-foreground/40 hover:text-red-400 transition-colors"
          >
            <LogOut size={12} strokeWidth={1.5} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="border-b border-border h-14 flex items-center px-6 flex-shrink-0">
          <div className="flex-1" />
          <button
            onClick={() => router.push('/settings')}
            className="font-mono text-sm text-foreground/50 hover:text-foreground transition-colors"
          >
            {user?.name ?? 'Profile'}
          </button>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-8 overflow-auto">
          <Container size="full">{children}</Container>
        </main>
      </div>
    </div>
  )
}
