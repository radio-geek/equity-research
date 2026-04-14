import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { trackEvent } from '../analytics'

export default function Header() {
  const { user, isAuthenticated, signIn, signOut } = useAuth()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [pictureError, setPictureError] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    setPictureError(false)
  }, [user?.id, user?.picture])

  const handleSignOut = async () => {
    setDropdownOpen(false)
    trackEvent('Sign Out', {})
    await signOut()
  }

  const isLanding = location.pathname === '/' || location.pathname === ''

  return (
    <header className={`se-header${isLanding ? '' : ' se-header--light'}`}>
      <div className="se-header__inner">
        <button className="se-header__logo" onClick={() => navigate('/')}>
          <span className="logo-valyu">valyu</span>
          <span className="logo-tagline">EQUITY RESEARCH</span>
        </button>

        <div className="se-header__actions">
          {isAuthenticated && user ? (
            <div className="user-menu" ref={dropdownRef}>
              <button
                className="user-avatar-btn"
                onClick={() => setDropdownOpen((o) => !o)}
                aria-label="User menu"
                aria-expanded={dropdownOpen}
              >
                {user.picture && !pictureError ? (
                  <img
                    src={user.picture}
                    alt={user.name ?? user.email}
                    className="user-avatar"
                    referrerPolicy="no-referrer"
                    onError={() => setPictureError(true)}
                  />
                ) : (
                  <span className="user-avatar-fallback">
                    {(user.name ?? user.email).charAt(0).toUpperCase()}
                  </span>
                )}
              </button>

              {dropdownOpen && (
                <div className="user-dropdown" role="menu">
                  <div className="user-dropdown-info">
                    {user.picture && !pictureError ? (
                      <img
                        src={user.picture}
                        alt={user.name ?? user.email}
                        className="user-dropdown-avatar"
                        referrerPolicy="no-referrer"
                        onError={() => setPictureError(true)}
                      />
                    ) : (
                      <span className="user-dropdown-avatar user-avatar-fallback">
                        {(user.name ?? user.email).charAt(0).toUpperCase()}
                      </span>
                    )}
                    <div>
                      <div className="user-dropdown-name">{user.name}</div>
                      <div className="user-dropdown-email">{user.email}</div>
                    </div>
                  </div>
                  <hr className="user-dropdown-divider" />
                  <button className="user-dropdown-item signout-item" onClick={handleSignOut} role="menuitem">
                    Sign out
                  </button>
                </div>
              )}

              {dropdownOpen && (
                <div
                  className="dropdown-backdrop"
                  onClick={() => setDropdownOpen(false)}
                  aria-hidden
                />
              )}
            </div>
          ) : (
            <button
              className="google-signin-btn"
              onClick={() => {
                trackEvent('Sign In Click', {})
                signIn()
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Sign in with Google
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
