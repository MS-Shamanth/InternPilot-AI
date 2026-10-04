import type { Config } from 'tailwindcss';
import defaultTheme from 'tailwindcss/defaultTheme';

/**
 * InternPilot design tokens (design.md §15.2).
 *
 * Contrast (WCAG AA, 4.5:1 for body text) on white / ink-50:
 * - ink-600 and darker, pilot-700 and darker, signal-700 and darker,
 *   success-700, warning-700, danger-700 are safe for text.
 * - 500/600 shades of pilot/signal/semantic colors are for fills, borders and icons only.
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        pilot: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
          950: '#042f2e',
          DEFAULT: '#0f766e',
        },
        signal: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
          DEFAULT: '#b45309',
        },
        success: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          700: '#15803d',
          800: '#166534',
          DEFAULT: '#15803d',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          500: '#f59e0b',
          700: '#b45309',
          800: '#92400e',
          DEFAULT: '#b45309',
        },
        danger: {
          50: '#fef2f2',
          100: '#fee2e2',
          500: '#ef4444',
          700: '#b91c1c',
          800: '#991b1b',
          DEFAULT: '#b91c1c',
        },
      },
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
      },
      ringColor: {
        DEFAULT: '#0f766e',
      },
      outlineColor: {
        focus: '#0f766e',
      },
    },
  },
  plugins: [],
};

export default config;
