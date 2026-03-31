<template>
  <div class="card" style="max-width: 420px; margin: 80px auto;">
    <div class="login-title">
      <img class="login-logo" src="/logo.png" alt="徐师傅 CRM" />
      <h2>徐师傅CRM登录</h2>
    </div>
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

<style scoped>
.login-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 6px;
}

.login-title h2 {
  margin: 0;
  line-height: 1;
}

.login-logo {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  object-fit: cover;
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.15);
}
</style>

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
