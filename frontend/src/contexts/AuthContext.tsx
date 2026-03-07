import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { clearToken, getMe, loginWithGoogle, logout as apiLogout, setToken, type User } from '../api'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  signIn: () => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount: capture ?token= from OAuth redirect or load existing session
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const authError = params.get('auth_error')

    if (token) {
      setToken(token)
      window.history.replaceState({}, '', window.location.pathname)
    }

    if (authError) {
      console.warn('OAuth error:', authError)
      window.history.replaceState({}, '', window.location.pathname)
    }

    getMe()
      .then(setUser)
      .finally(() => setIsLoading(false))
  }, [])

  const signIn = useCallback(() => loginWithGoogle(), [])

  const signOut = useCallback(async () => {
    await apiLogout()
    clearToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: user !== null, isLoading, signIn, signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
