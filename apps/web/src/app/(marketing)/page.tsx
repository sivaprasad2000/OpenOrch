import Link from 'next/link'

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero Section */}
      <section className="flex-1 flex items-center justify-center px-6 py-24">
        <div className="max-w-4xl w-full space-y-12">
          {/* Title */}
          <h1 className="font-mono text-[5rem] sm:text-[7rem] lg:text-[10rem] leading-none tracking-tight">
            OpenOrch
          </h1>

          {/* Tagline */}
          <div className="space-y-2">
            <p className="font-mono text-2xl sm:text-3xl text-foreground">
              Describe your UI. AI writes the tests.
            </p>
            <p className="font-mono text-2xl sm:text-3xl text-accent">
              Ship faster. Break nothing.
            </p>
          </div>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-4 items-start">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center px-8 py-4 border-2 border-transparent bg-accent text-black font-mono text-lg font-semibold hover:bg-accent/90 transition-colors"
            >
              Start free trial →
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center px-8 py-4 border border-foreground/40 text-foreground font-mono text-lg hover:bg-foreground/10 transition-colors"
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
              } ${index < 2 ? 'border-b lg:border-b-0 border-border' : ''}`}
            >
              <h3 className="font-mono text-base text-foreground mb-2">
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
