import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Middleware for route protection
 * Phase 1: Structure only
 * Phase 2+: Integrate with auth provider
 */

export function middleware(_request: NextRequest) {
  // TODO: Phase 2 - Implement actual auth checks
  // For now, allow all routes (Phase 1)
  // In Phase 2+, implement route protection logic:
  /*
  const PUBLIC_ROUTES = ['/', '/login', '/signup']
  const AUTH_ROUTES = ['/login', '/signup']
  const PROTECTED_ROUTES = ['/app']

  const { pathname } = request.nextUrl
  const isAuthenticated = await checkAuth(request)

  const isPublicRoute = PUBLIC_ROUTES.some((route) =>
    pathname === route ? true : pathname.startsWith(route + '/')
  )

  const isAuthRoute = AUTH_ROUTES.some((route) =>
    pathname === route ? true : pathname.startsWith(route + '/')
  )

  const isProtectedRoute = PROTECTED_ROUTES.some((route) =>
    pathname.startsWith(route)
  )

  if (isProtectedRoute && !isAuthenticated) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL('/app/dashboard', request.url))
  }
  */

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
