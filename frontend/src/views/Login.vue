<template>
  <div class="card" style="max-width: 420px; margin: 80px auto;">
    <div class="login-title">
      <img class="login-logo" src="/logo.png" alt="徐师傅 CRM" />
      <h2>徐师傅CRM登录</h2>
    </div>
    <div v-if="ssoLoading || ssoMessage" class="login-sso-hint">
      {{ ssoLoading ? '正在尝试钉钉免登录...' : ssoMessage }}
    </div>
    <div class="form-grid">
      <div>
        <label>用户名</label>
        <input v-model="username" placeholder="用户名" :disabled="ssoLoading" />
      </div>
      <div>
        <label>密码</label>
        <input v-model="password" type="password" placeholder="密码" :disabled="ssoLoading" />
      </div>
    </div>
    <div style="margin-top: 12px; display: flex; gap: 10px;">
      <button class="button" :disabled="ssoLoading" @click="handleLogin">登录</button>
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

.login-sso-hint {
  margin-bottom: 12px;
  color: #495057;
  font-size: 13px;
}
</style>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const username = ref('')
const password = ref('')
const error = ref('')
const ssoLoading = ref(false)
const ssoMessage = ref('')
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const DEFAULT_LOGIN_REDIRECT = '/opportunities'

const resolveRedirectPath = () => {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  if (!redirect || !redirect.startsWith('/') || redirect.startsWith('//')) {
    return ''
  }
  return redirect
}

const nextPath = computed(() => resolveRedirectPath() || DEFAULT_LOGIN_REDIRECT)

const shouldAttemptSso = computed(() => {
  const redirect = resolveRedirectPath()
  if (!redirect) return false
  try {
    const parsed = new URL(redirect, window.location.origin)
    return parsed.searchParams.get('sso') === '1'
  } catch {
    return redirect.includes('sso=1')
  }
})

const extractErrorMessage = (err) => {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  return ''
}

const requestDingTalkAuthCode = (corpId) => (
  new Promise((resolve, reject) => {
    const sdk = typeof window !== 'undefined' ? window.dd : null
    if (!sdk?.runtime?.permission?.requestAuthCode) {
      reject(new Error('当前环境不支持钉钉免登录'))
      return
    }
    sdk.runtime.permission.requestAuthCode({
      corpId,
      onSuccess: (result) => {
        const code = result?.code || result?.authCode
        if (code) {
          resolve(code)
          return
        }
        reject(new Error('钉钉授权码为空'))
      },
      onFail: (err) => {
        const msg = err?.errorMessage || err?.message || '获取钉钉授权码失败'
        reject(new Error(msg))
      },
    })
  })
)

const tryAutoDingTalkLogin = async () => {
  if (!shouldAttemptSso.value || ssoLoading.value) return
  ssoLoading.value = true
  error.value = ''
  try {
    const configResp = await api.get('/auth/dingtalk/config/')
    const config = configResp?.data || {}
    if (!config.enabled || !config.corp_id) {
      ssoMessage.value = '当前未启用钉钉免登录，请使用账号密码登录'
      return
    }

    const code = await requestDingTalkAuthCode(config.corp_id)
    await auth.loginWithDingTalkCode(code)
    await router.replace(nextPath.value)
  } catch (err) {
    const detail = extractErrorMessage(err)
    error.value = detail ? `钉钉免登录失败：${detail}` : '钉钉免登录失败，请使用账号密码登录'
  } finally {
    ssoLoading.value = false
  }
}

const handleLogin = async () => {
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push(nextPath.value)
  } catch (err) {
    error.value = '登录失败，请检查账号密码'
  }
}

onMounted(() => {
  if (!shouldAttemptSso.value) return
  ssoMessage.value = '检测到审批待办链接，正在尝试钉钉免登录。'
  void tryAutoDingTalkLogin()
})
</script>
