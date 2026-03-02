import type { Metadata } from 'next'
import { Quicksand } from 'next/font/google'
import './globals.css'
import { env } from '@/config/env'

const quicksand = Quicksand({
  subsets: ['latin'],
  variable: '--font-quicksand',
  display: 'swap',
  weight: ['300', '400', '500', '600', '700'],
})

export const metadata: Metadata = {
  title: 'OpenOrch - AI-Assisted UI Testing',
  description:
    'Describe your UI in plain English. OpenOrch AI writes and runs the tests. Auto-healing selectors, visual regression, and CI/CD integration out of the box.',
  metadataBase: new URL(env.NEXT_PUBLIC_APP_URL),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: env.NEXT_PUBLIC_APP_URL,
    title: 'OpenOrch - AI-Assisted UI Testing',
    description:
      'Describe your UI. AI writes the tests. Ship faster. Break nothing.',
    siteName: 'OpenOrch',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'OpenOrch - AI-Assisted UI Testing',
    description:
      'Describe your UI. AI writes the tests. Ship faster. Break nothing.',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${quicksand.variable} font-sans`}>{children}</body>
    </html>
  )
}
