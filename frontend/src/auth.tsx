import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { User } from './types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('bi-token')
    if (!token) {
      setLoading(false)
      return
    }
    api<User>('/api/auth/me')
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('bi-token')
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      async login(username, password) {
        const result = await api<{ token: string; user: User }>('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password }),
        })
        localStorage.setItem('bi-token', result.token)
        setUser(result.user)
      },
      logout() {
        localStorage.removeItem('bi-token')
        setUser(null)
      },
    }),
    [user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider belum terpasang')
  return value
}
