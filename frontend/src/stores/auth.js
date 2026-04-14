import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('accessToken') || '',
    refreshToken: localStorage.getItem('refreshToken') || '',
    user: null,
    userFetchedAt: 0
  }),
  actions: {
    async login(username, password) {
      const response = await api.post('/auth/jwt/', { username, password })
      this.accessToken = response.data.access
      this.refreshToken = response.data.refresh
      localStorage.setItem('accessToken', this.accessToken)
      localStorage.setItem('refreshToken', this.refreshToken)
      await this.fetchMe()
    },
    async fetchMe() {
      const response = await api.get('/auth/me/')
      this.user = response.data
      this.userFetchedAt = Date.now()
    },
    async ensureMeFresh(maxAgeMs = 60000) {
      if (!this.accessToken) return
      const now = Date.now()
      const isExpired = !this.userFetchedAt || now - this.userFetchedAt > maxAgeMs
      if (!this.user || isExpired) {
        await this.fetchMe()
      }
    },
    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      this.userFetchedAt = 0
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
    }
  }
})
