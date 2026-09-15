import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 120_000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('qdata_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (status === 401 || (status === 403 && detail === 'Not authenticated')) {
      localStorage.removeItem('qdata_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default api
