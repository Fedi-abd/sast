/** @type {import('tailwindcss').Config} */

/*
 * "Analyst console" palette.
 *
 * Dark mode is the signature: a deep navy near-black with cyan-blue
 * accents and a hint of warmth on raised surfaces. Light mode is the
 * same identity in a daylight register — same elevation rules, same
 * typography, brighter base.
 *
 * Surface tokens express elevation, not "light vs. dark." Components
 * pick `surface.base`, `surface.raised`, `surface.elevated`, etc.,
 * and the values shift via `dark:` variants.
 *
 * Border tokens carry their own contract: `line` for quiet
 * separators, `line.strong` when a border has to read as an edge.
 */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Geist',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'sans-serif',
        ],
        mono: ['"Geist Mono"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
        display: ['Geist', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Brand — a cool blue that pops on both day and night surfaces.
        brand: {
          50: '#EBF2FF',
          100: '#D6E4FF',
          200: '#ADC8FF',
          300: '#84ABFF',
          400: '#5B8DEF',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#172554',
          DEFAULT: '#3B82F6',
        },
        // Accent — cyan, used sparingly: focus rings, active rollup borders,
        // the subtle radial glow in dark mode. Never as primary CTA.
        accent: {
          400: '#22D3EE',
          500: '#06B6D4',
          DEFAULT: '#06B6D4',
        },
        // Surface elevation tokens. The naming is "where am I on the
        // elevation scale" — `sunken` is below the body, `base` is the
        // body itself, `raised` and `elevated` are above it. Components
        // pick a level instead of hard-coding slate-X.
        surface: {
          // Light register
          sunken: '#F4F6FA',
          base: '#FAFBFC',
          raised: '#FFFFFF',
          elevated: '#FFFFFF',
          // Dark register — the signature.
          'dark-sunken': '#040711',
          'dark-base': '#070B14',
          'dark-raised': '#0F1726',
          'dark-elevated': '#152034',
          // Highlight — used for the 1px inset top edge on dark cards,
          // and for the active-nav fill in light mode.
          'dark-highlight': '#1F2D45',
        },
        line: {
          DEFAULT: '#E5E8EE',          // light borders, quiet
          strong: '#D0D5DD',           // light borders, intentional edge
          dark: '#1B2436',             // dark borders, quiet
          'dark-strong': '#293449',    // dark borders, intentional edge
        },
        // Severity colors — semantic, always the same hue across modes.
        // Each gets a foreground for the badge text + a softened
        // background-tint variant for use on dark cards.
        severity: {
          'high-fg': '#FCA5A5',
          'high-bg': '#7F1D1D',
          'med-fg': '#FCD34D',
          'med-bg': '#78350F',
          'low-fg': '#7DD3FC',
          'low-bg': '#0C4A6E',
        },
      },
      boxShadow: {
        // Two-stop card shadow — close + ambient. Tuned for light
        // surfaces; dark uses a 1px inset highlight instead (see
        // .card-glass in style.css).
        card: '0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)',
        'card-hover':
          '0 2px 4px rgba(15, 23, 42, 0.06), 0 8px 16px -4px rgba(15, 23, 42, 0.10)',
        // Soft inner glow on focused inputs.
        'focus-ring': '0 0 0 3px rgba(59, 130, 246, 0.28)',
      },
      backgroundImage: {
        // Atmospheric radial glow for the dark body — feels like an
        // analyst console rather than a void.
        'dark-atmosphere':
          'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(34, 211, 238, 0.10), transparent 70%)',
      },
      keyframes: {
        'rise-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'rise-in': 'rise-in 320ms cubic-bezier(0.16, 1, 0.3, 1) both',
      },
    },
  },
  plugins: [],
}
