import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Where to redirect if not authenticated. Defaults to '/'. */
  redirectTo?: string
}

export default function ProtectedRoute({ children, redirectTo = '/' }: Props) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return null  // wait for session check before deciding

  if (!isAuthenticated) return <Navigate to={redirectTo} replace />

  return <>{children}</>
}
