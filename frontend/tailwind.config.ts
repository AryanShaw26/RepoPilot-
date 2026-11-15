/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: 'rgb(var(--surface-rgb) / <alpha-value>)',
        'surface-raised': 'rgb(var(--surface-raised-rgb) / <alpha-value>)',
        'surface-inset': 'rgb(var(--surface-inset-rgb) / <alpha-value>)',
        ink: 'rgb(var(--ink-rgb) / <alpha-value>)',
        'ink-muted': 'rgb(var(--ink-muted-rgb) / <alpha-value>)',
        'ink-faint': 'rgb(var(--ink-faint-rgb) / <alpha-value>)',
        edge: 'rgb(var(--edge-rgb) / <alpha-value>)',
        accent: 'rgb(var(--brand-rgb) / <alpha-value>)',
        'accent-strong': 'rgb(var(--brand-deep-rgb) / <alpha-value>)',
        'accent-ink': 'rgb(var(--accent-ink-rgb) / <alpha-value>)',
        focus: 'rgb(var(--focus-rgb) / <alpha-value>)',
        led: {
          green: 'rgb(var(--led-green-rgb) / <alpha-value>)',
          amber: 'rgb(var(--led-amber-rgb) / <alpha-value>)',
          red: 'rgb(var(--led-red-rgb) / <alpha-value>)',
          blue: 'rgb(var(--led-blue-rgb) / <alpha-value>)',
        },
        glass: 'rgb(var(--glass-rgb) / <alpha-value>)',
        'glass-ink': 'rgb(var(--glass-ink-rgb) / <alpha-value>)',
        metal: {
          hi: 'rgb(var(--metal-hi-rgb) / <alpha-value>)',
          lo: 'rgb(var(--metal-lo-rgb) / <alpha-value>)',
        },
      },
      boxShadow: {
        e1: 'var(--elev-1)',
        e2: 'var(--elev-2)',
        e3: 'var(--elev-3)',
        i1: 'var(--inset-1)',
        i2: 'var(--inset-2)',
        inset: 'var(--inset-1)',
      },
      borderRadius: {
        sm: '8px',
        md: '14px',
        lg: '22px',
        pill: '999px',
      },
      fontFamily: {
        display: ['"Barlow Semi Condensed"', '"Arial Narrow"', 'sans-serif'],
        sans: ['Figtree', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
