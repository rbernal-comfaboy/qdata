import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useAuthStore } from '../../hooks/useAuth'

export default function Layout() {
  const loadUser = useAuthStore((s) => s.loadUser)
  const token = useAuthStore((s) => s.token)

  useEffect(() => {
    if (token) loadUser()
  }, [token, loadUser])

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
