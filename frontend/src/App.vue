<template>
  <div v-if="!auth.accessToken" class="main">
    <router-view />
  </div>
  <div v-else class="layout">
    <aside class="sidebar">
      <div class="brand">
        <img class="brand-logo" src="/logo.png" alt="徐师傅 CRM" />
        <span class="brand-text">徐师傅 CRM</span>
      </div>
      <nav class="nav">
        <router-link to="/dashboard"><span class="nav-icon">◈</span>销售看板</router-link>
        <router-link to="/opportunities"><span class="nav-icon">◎</span>商机管理</router-link>
        <router-link to="/accounts"><span class="nav-icon">◼</span>客户管理</router-link>
        <router-link to="/contracts"><span class="nav-icon">▣</span>合同管理</router-link>
        <router-link to="/payments"><span class="nav-icon">◆</span>回款管理</router-link>
      </nav>
      <div class="sidebar-footer">
        <div class="sidebar-user">
          <div class="sidebar-user-head">
            <div>
              <div class="sidebar-user-label">当前用户</div>
              <div class="sidebar-user-name">{{ auth.user?.username || '-' }}</div>
            </div>
          </div>
          <div class="sidebar-user-actions">
            <a class="text-link small" href="#" @click.prevent="goApprovals">我的审批</a>
            <a class="text-link small" href="#" @click.prevent="togglePasswordForm">
              {{ showPasswordForm ? '收起修改密码' : '修改密码' }}
            </a>
            <a class="text-link small danger" href="#" @click.prevent="handleLogout">退出</a>
          </div>
        </div>
        <div v-if="showPasswordForm" class="sidebar-card">
          <label>当前密码</label>
          <input v-model="passwordForm.old_password" type="password" autocomplete="current-password" />
          <label>新密码</label>
          <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" />
          <label>确认新密码</label>
          <input v-model="passwordForm.confirm_password" type="password" autocomplete="new-password" />
          <div class="sidebar-actions">
            <button class="text-link small" :disabled="passwordSaving" @click="submitPassword">
              {{ passwordSaving ? '保存中...' : '保存' }}
            </button>
            <button class="text-link small" @click="cancelPassword">取消</button>
          </div>
          <div v-if="passwordError" class="sidebar-hint error">{{ passwordError }}</div>
          <div v-if="passwordSuccess" class="sidebar-hint success">{{ passwordSuccess }}</div>
        </div>
      </div>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import api from './api'

const auth = useAuthStore()
const router = useRouter()
const showPasswordForm = ref(false)
const passwordSaving = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const togglePasswordForm = () => {
  showPasswordForm.value = !showPasswordForm.value
  passwordError.value = ''
  passwordSuccess.value = ''
}

const cancelPassword = () => {
  showPasswordForm.value = false
  passwordError.value = ''
  passwordSuccess.value = ''
  passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
}

const submitPassword = async () => {
  passwordError.value = ''
  passwordSuccess.value = ''
  if (!passwordForm.value.new_password) {
    passwordError.value = '新密码不能为空'
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  passwordSaving.value = true
  try {
    await api.post('/auth/password/', { ...passwordForm.value })
    passwordSuccess.value = '密码已更新'
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      passwordError.value = detail.detail || '修改失败，请稍后重试'
    } else {
      passwordError.value = '修改失败，请稍后重试'
    }
  } finally {
    passwordSaving.value = false
  }
}

const handleLogout = () => {
  auth.logout()
  router.push({ name: 'login' })
}

const goApprovals = () => {
  router.push({ name: 'approval-task-list' })
}

onMounted(async () => {
  if (auth.accessToken && !auth.user) {
    try {
      await auth.fetchMe()
    } catch (err) {
      auth.logout()
    }
  }
})
</script>
