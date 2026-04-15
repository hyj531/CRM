<template>
  <div v-if="!auth.accessToken" class="main">
    <router-view />
  </div>
  <div v-else class="layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-main">
          <img class="brand-logo" src="/logo.png" alt="徐师傅 CRM" />
          <span class="brand-text">徐师傅 CRM</span>
        </div>
        <button
          class="sidebar-toggle"
          type="button"
          :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="toggleSidebar"
        >
          <span aria-hidden="true">{{ sidebarCollapsed ? '»' : '«' }}</span>
        </button>
      </div>
      <nav class="nav">
        <router-link to="/dashboard" title="销售看板"><span class="nav-icon">◈</span><span class="nav-label">销售看板</span></router-link>
        <router-link to="/opportunities" title="商机管理"><span class="nav-icon">◎</span><span class="nav-label">商机管理</span></router-link>
        <router-link to="/accounts" title="客户管理"><span class="nav-icon">◼</span><span class="nav-label">客户管理</span></router-link>
        <router-link to="/contracts" title="合同管理"><span class="nav-icon">▣</span><span class="nav-label">合同管理</span></router-link>
        <router-link to="/invoices" title="开票管理"><span class="nav-icon">◉</span><span class="nav-label">开票管理</span></router-link>
        <router-link to="/payments" title="回款管理"><span class="nav-icon">◆</span><span class="nav-label">回款管理</span></router-link>
        <router-link to="/approvals/tasks" title="审批中心">
          <span class="nav-icon">◬</span>
          <span class="nav-label">审批中心</span>
          <span v-if="showApprovalBadge" class="nav-badge">{{ approvalBadgeText }}</span>
        </router-link>
        <router-link v-if="canManageApprovalConfig" to="/approvals/config" title="审批配置"><span class="nav-icon">◍</span><span class="nav-label">审批配置</span></router-link>
        <router-link v-if="canAccessCommonDocs" to="/common-docs" title="常用文档"><span class="nav-icon">◧</span><span class="nav-label">常用文档</span></router-link>
      </nav>
      <div v-if="!sidebarCollapsed" class="sidebar-footer">
        <div class="sidebar-user">
          <div class="sidebar-user-head">
            <div>
              <div class="sidebar-user-label">当前用户</div>
              <div class="sidebar-user-name">{{ auth.user?.username || '-' }}</div>
            </div>
          </div>
          <div class="sidebar-user-actions">
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
      <router-view v-slot="{ Component, route }">
        <keep-alive>
          <component v-if="route.meta.keepAlive" :is="Component" />
        </keep-alive>
        <component v-if="!route.meta.keepAlive" :is="Component" />
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import api from './api'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const canAccessCommonDocs = computed(() => {
  if (auth.user?.is_staff || auth.user?.is_superuser) return true
  const mod = auth.user?.permissions?.common_doc
  return Boolean(mod && (mod.create || mod.update || mod.delete || mod.approve))
})
const canManageApprovalConfig = computed(() => (
  auth.user?.can_manage_approval_config || auth.user?.is_staff || auth.user?.is_superuser
))
const SIDEBAR_COLLAPSED_STORAGE_KEY = 'crm_sidebar_collapsed'

const readSidebarCollapsed = () => {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1'
  } catch (err) {
    return false
  }
}

const sidebarCollapsed = ref(readSidebarCollapsed())
const showPasswordForm = ref(false)
const passwordSaving = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})
const approvalPendingCount = ref(0)
const approvalBadgeLastFetchedAt = ref(0)
const approvalBadgeLoaded = ref(false)
const approvalBadgeFetching = ref(false)
const approvalBadgeTimerId = ref(null)
const APPROVAL_BADGE_SYNC_MS = 60000

const showApprovalBadge = computed(() => approvalPendingCount.value > 0)
const approvalBadgeText = computed(() => (
  approvalPendingCount.value > 99 ? '99+' : String(approvalPendingCount.value)
))

const togglePasswordForm = () => {
  showPasswordForm.value = !showPasswordForm.value
  passwordError.value = ''
  passwordSuccess.value = ''
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  if (sidebarCollapsed.value) {
    showPasswordForm.value = false
  }
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, sidebarCollapsed.value ? '1' : '0')
    } catch (err) {
      // Ignore storage write errors and keep UI usable.
    }
  }
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

const fetchApprovalBadgeCount = async ({ force = false } = {}) => {
  if (!auth.accessToken) return
  if (approvalBadgeFetching.value) return
  if (!force) {
    const ageMs = Date.now() - approvalBadgeLastFetchedAt.value
    if (approvalBadgeLoaded.value && ageMs < APPROVAL_BADGE_SYNC_MS) return
  }
  approvalBadgeFetching.value = true
  try {
    const resp = await api.get('/approval-instances/mine/stats/')
    const value = Number(resp.data?.pending_count)
    approvalPendingCount.value = Number.isFinite(value) && value > 0 ? Math.floor(value) : 0
    approvalBadgeLoaded.value = true
    approvalBadgeLastFetchedAt.value = Date.now()
  } catch (err) {
    if (!approvalBadgeLoaded.value) {
      approvalPendingCount.value = 0
    }
  } finally {
    approvalBadgeFetching.value = false
  }
}

const clearApprovalBadgeSync = () => {
  if (approvalBadgeTimerId.value && typeof window !== 'undefined') {
    window.clearInterval(approvalBadgeTimerId.value)
  }
  approvalBadgeTimerId.value = null
  if (typeof window !== 'undefined') {
    window.removeEventListener('focus', handleWindowFocus)
  }
}

const startApprovalBadgeSync = () => {
  if (!auth.accessToken) return
  clearApprovalBadgeSync()
  void fetchApprovalBadgeCount({ force: true })
  if (typeof window !== 'undefined') {
    approvalBadgeTimerId.value = window.setInterval(() => {
      void fetchApprovalBadgeCount({ force: true })
    }, APPROVAL_BADGE_SYNC_MS)
    window.addEventListener('focus', handleWindowFocus)
  }
}

const handleWindowFocus = () => {
  void fetchApprovalBadgeCount()
}

watch(
  () => route.fullPath,
  () => {
    void fetchApprovalBadgeCount()
  }
)

watch(
  () => auth.accessToken,
  (token) => {
    if (token) {
      startApprovalBadgeSync()
      return
    }
    clearApprovalBadgeSync()
    approvalPendingCount.value = 0
    approvalBadgeLastFetchedAt.value = 0
    approvalBadgeLoaded.value = false
    approvalBadgeFetching.value = false
  }
)

onMounted(async () => {
  if (auth.accessToken) {
    try {
      await auth.ensureMeFresh(60000)
      startApprovalBadgeSync()
    } catch (err) {
      auth.logout()
    }
  }
})

onBeforeUnmount(() => {
  clearApprovalBadgeSync()
})
</script>
