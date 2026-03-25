import axios from 'axios'

const api = axios.create({
  baseURL: '/api'
})

const refreshClient = axios.create({
  baseURL: '/api'
})

let isRefreshing = false
let pending = []

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {}
    if (error.response && error.response.status === 401 && !original._retry) {
      const refreshToken = localStorage.getItem('refreshToken')
      if (!refreshToken) {
        localStorage.removeItem('accessToken')
        localStorage.removeItem('refreshToken')
        window.location.href = '/app/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pending.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }

      isRefreshing = true
      original._retry = true

      try {
        const resp = await refreshClient.post('/auth/jwt/refresh/', { refresh: refreshToken })
        const newAccess = resp.data.access
        localStorage.setItem('accessToken', newAccess)
        pending.forEach((p) => p.resolve(newAccess))
        pending = []
        original.headers.Authorization = `Bearer ${newAccess}`
        return api(original)
      } catch (refreshError) {
        pending.forEach((p) => p.reject(refreshError))
        pending = []
        localStorage.removeItem('accessToken')
        localStorage.removeItem('refreshToken')
        window.location.href = '/app/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export default api
