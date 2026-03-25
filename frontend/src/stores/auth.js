import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('accessToken') || '',
    refreshToken: localStorage.getItem('refreshToken') || '',
    user: null
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
    },
    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
    }
  }
})
