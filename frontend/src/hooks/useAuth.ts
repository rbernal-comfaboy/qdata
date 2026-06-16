import { create } from 'zustand'
import api from '../api/client'

interface User {
  id: string
  email: string
  name: string
  role: string
  created_at?: string
}

interface AuthState {
  token: string | null
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  loadUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('qdata_token'),
  user: null,
  loading: false,

  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('qdata_token', data.access_token)
    set({ token: data.access_token })
    await useAuthStore.getState().loadUser()
  },

  register: async (email, password, name) => {
    const { data } = await api.post('/auth/register', { email, password, name })
    localStorage.setItem('qdata_token', data.access_token)
    set({ token: data.access_token })
    await useAuthStore.getState().loadUser()
  },

  logout: () => {
    localStorage.removeItem('qdata_token')
    set({ token: null, user: null })
  },

  loadUser: async () => {
    try {
      const { data } = await api.get('/auth/me')
      set({ user: data })
    } catch {
      set({ user: null })
    }
  },
}))
