import { createContext, useContext, useEffect, useMemo, useState } from 'react'

interface ThemeState {
  theme: 'light' | 'dark'
  toggle: () => void
}

const ThemeContext = createContext<ThemeState | null>(null)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    localStorage.getItem('bi-theme') === 'dark' ? 'dark' : 'light',
  )

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('bi-theme', theme)
  }, [theme])

  const value = useMemo(() => ({ theme, toggle: () => setTheme((item) => (item === 'dark' ? 'light' : 'dark')) }), [theme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('ThemeProvider belum terpasang')
  return value
}
