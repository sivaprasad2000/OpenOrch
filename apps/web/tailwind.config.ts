import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    './src/features/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        accent: '#A7C7FF',
        background: '#0a0a0a',
        foreground: '#fafafa',
        muted: '#404040',
        border: '#262626',
      },
      fontFamily: {
        sans: ['var(--font-quicksand)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-quicksand)', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        none: '0',
        sm: '2px',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '26': '6.5rem',
        '30': '7.5rem',
      },
    },
  },
  plugins: [],
}

export default config
