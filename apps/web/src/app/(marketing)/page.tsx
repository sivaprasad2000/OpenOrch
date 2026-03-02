import Link from 'next/link'

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Hero Section */}
      <section className="flex flex-1 items-center justify-center px-6 py-24">
        <div className="w-full max-w-4xl space-y-12">
          {/* Title */}
          <h1 className="font-mono text-[5rem] leading-none tracking-tight sm:text-[7rem] lg:text-[10rem]">
            OpenOrch
          </h1>

          {/* Tagline */}
          <div className="space-y-2">
            <p className="font-mono text-2xl text-foreground sm:text-3xl">
              Describe your UI. AI writes the tests.
            </p>
            <p className="font-mono text-2xl text-accent sm:text-3xl">
              Ship faster. Break nothing.
            </p>
          </div>

          {/* CTAs */}
          <div className="flex flex-col items-start gap-4 sm:flex-row">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center border-2 border-transparent bg-accent px-8 py-4 font-mono text-lg font-semibold text-black transition-colors hover:bg-accent/90"
            >
              Start free trial →
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center border border-foreground/40 px-8 py-4 font-mono text-lg text-foreground transition-colors hover:bg-foreground/10"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* Feature Bar */}
      <section className="border-t border-border">
        <div className="grid grid-cols-2 lg:grid-cols-4">
          {features.map((feature, index) => (
            <div
              key={feature.title}
              className={`p-8 ${
                index < features.length - 1 ? 'border-r border-border' : ''
              } ${index < 2 ? 'border-b border-border lg:border-b-0' : ''}`}
            >
              <h3 className="mb-2 font-mono text-base text-foreground">
                {feature.title}
              </h3>
              <p className="font-mono text-sm text-foreground/60">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

const features = [
  {
    title: 'AI test generation',
    description: 'Plain English in, test code out',
  },
  {
    title: 'Auto-healing selectors',
    description: 'Adapts when your UI changes',
  },
  {
    title: 'Visual regression',
    description: 'AI-powered pixel-level diffs',
  },
  {
    title: 'CI/CD native',
    description: 'GitHub Actions, GitLab, Jenkins',
  },
]
