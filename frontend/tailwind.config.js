/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: 'var(--canvas)',
        card: 'var(--card)',
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        line: 'var(--line)',
        navy: {
          950: '#06101C',
          900: '#0B1F3A',
          800: '#143154',
          700: '#1E4A7A',
        },
        gold: {
          500: '#C4A35A',
          300: '#E1CB8E',
          100: '#F8F1DE',
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'Segoe UI', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: 'none',
      },
    },
  },
  plugins: [],
}
