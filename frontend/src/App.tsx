import { useEffect, useState } from 'react'

import { login, logout, me } from './api'
import { LoginForm } from './components/LoginForm'
import { ReviewDashboard } from './components/ReviewDashboard'
import type { UserInfo } from './types'

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const userInfo = await me()
        setUser(userInfo)
      } catch {
        setUser(null)
      } finally {
        setLoading(false)
      }
    }

    void bootstrap()
  }, [])

  const handleLogin = async (username: string, password: string) => {
    const info = await login(username, password)
    setUser(info)
  }

  const handleLogout = async () => {
    if (!user) {
      return
    }
    await logout(user.csrf_token)
    setUser(null)
  }

  if (loading) {
    return <main className="loading-screen">Loading...</main>
  }

  if (!user) {
    return <LoginForm onSubmit={handleLogin} />
  }

  return (
    <ReviewDashboard
      username={user.username}
      role={user.role}
      csrfToken={user.csrf_token}
      onLogout={handleLogout}
    />
  )
}
