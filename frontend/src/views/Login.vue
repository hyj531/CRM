<template>
  <div class="card" style="max-width: 420px; margin: 80px auto;">
    <h2>登录</h2>
    <div class="form-grid">
      <div>
        <label>用户名</label>
        <input v-model="username" placeholder="用户名" />
      </div>
      <div>
        <label>密码</label>
        <input v-model="password" type="password" placeholder="密码" />
      </div>
    </div>
    <div style="margin-top: 12px; display: flex; gap: 10px;">
      <button class="button" @click="handleLogin">登录</button>
      <span v-if="error" style="color: #c92a2a;">{{ error }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
const error = ref('')
const auth = useAuthStore()
const router = useRouter()

const handleLogin = async () => {
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/opportunities')
  } catch (err) {
    error.value = '登录失败，请检查账号密码'
  }
}
</script>
