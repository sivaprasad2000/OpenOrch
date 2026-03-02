import Link from 'next/link'
import { Container } from '@/components/ui/container'
import { Button } from '@/components/ui/button'

export function Header() {
  return (
    <header className="border-b border-border py-4">
      <Container>
        <nav className="flex items-center justify-between">
          <Link href="/" className="font-mono text-xl font-bold">
            OpenOrch
          </Link>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm text-muted transition-colors hover:text-foreground"
            >
              Login
            </Link>
            <Button size="sm" asChild>
              <Link href="/signup">Sign Up</Link>
            </Button>
          </div>
        </nav>
      </Container>
    </header>
  )
}
