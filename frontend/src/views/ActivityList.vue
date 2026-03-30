<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">商机跟进</h2>
        <div class="page-subtitle">记录每一次跟进，保持销售节奏</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="createActivity">
          {{ saving ? '保存中...' : '记录跟进' }}
        </button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">跟进总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日跟进</div>
        <div class="stat-value">{{ todayCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">近7天跟进</div>
        <div class="stat-value">{{ weekCount }}</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: !filters.type }" @click="setType('')">全部</button>
      <button
        v-for="t in types"
        :key="t.value"
        class="tab"
        :class="{ active: filters.type === t.value }"
        @click="setType(t.value)"
      >
        {{ t.label }}
      </button>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">快速记录</div>
        <div class="form-grid">
          <div>
            <label>跟进目标</label>
            <input v-model="form.subject" placeholder="例如：需求确认/方案沟通" />
          </div>
          <div>
            <label>关联商机</label>
            <select v-model.number="form.opportunity">
              <option :value="null">未关联</option>
              <option v-for="opp in opportunities" :key="opp.id" :value="opp.id">
                {{ opp.opportunity_name }}
              </option>
            </select>
          </div>
          <div>
            <label>跟进时间</label>
            <input v-model="form.due_at" type="datetime-local" />
          </div>
        </div>
        <div style="margin-top: 10px;">
          <label>跟进内容</label>
          <textarea v-model="form.description" rows="4"></textarea>
        </div>
        <div style="margin-top: 10px;">
          <button class="button" :disabled="saving" @click="createActivity">
            {{ saving ? '保存中...' : '保存跟进' }}
          </button>
          <span v-if="success" style="margin-left: 10px; color: #2b8a3e;">{{ success }}</span>
          <span v-if="error" style="margin-left: 10px; color: #c92a2a;">{{ error }}</span>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 条跟进</div>
          <div>按商机与方式过滤</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
          <div class="filter-left">
            <input v-model="search" placeholder="搜索跟进目标/内容" @keyup.enter="applyFilters" />
            <button class="button" @click="applyFilters">搜索</button>
            <button class="button secondary" @click="resetFilters">清除</button>
          </div>
          <div class="filter-right">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-due_at">跟进时间最新</option>
              <option value="due_at">跟进时间最早</option>
              <option value="-created_at">创建时间最新</option>
            </select>
            <button
            class="button secondary small icon-only"
            @click="exportCsv"
            title="导出CSV"
            aria-label="导出CSV"
          >
            <span class="icon">⬇</span>
          </button>
          </div>
        </div>
        <div v-for="item in pagedActivities" :key="item.id" class="list-row">
          <div>
            <div class="list-title">{{ item.subject }}</div>
            <div class="list-meta">
              <span class="badge blue">{{ typeLabel(item.activity_type) }}</span>
              <span>商机ID：{{ item.opportunity || '-' }}</span>
              <span>时间：{{ item.due_at || '-' }}</span>
              <span>内容：{{ item.description || '-' }}</span>
            </div>
          </div>
          <div class="list-actions">
            <button v-if="canDelete" class="button secondary" @click="deleteActivity(item.id)">删除</button>
          </div>
        </div>
        <div v-if="!pagedActivities.length" style="padding: 16px; color: #888;">暂无跟进记录</div>
        <div class="pager" style="padding: 0 16px 16px;">
          <button :disabled="currentPage === 1" @click="changePage(currentPage - 1)">上一页</button>
          <span>第 {{ currentPage }} / {{ pageCount }} 页</span>
          <button :disabled="currentPage === pageCount" @click="changePage(currentPage + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const activities = ref([])
const total = ref(0)
const opportunities = ref([])
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.activity?.delete))
const error = ref('')
const success = ref('')
const saving = ref(false)
const filters = ref({
  type: ''
})
const search = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-due_at')
const toLocalDateTime = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - offset).toISOString().slice(0, 16)
}

const form = ref({
  activity_type: 'internal',
  subject: '',
  description: '',
  opportunity: null,
  due_at: toLocalDateTime()
})

const types = [
  { value: 'call', label: '电话' },
  { value: 'meeting', label: '会议' },
  { value: 'email', label: '邮件' },
  { value: 'visit', label: '拜访' },
  { value: 'internal', label: '内部穿透' }
]

const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
  if (filters.value.type) params.activity_type = filters.value.type
  if (search.value) params.search = search.value
  return params
}

const fetchData = async () => {
  const res = await api.get('/activities/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    activities.value = res.data.results
    total.value = res.data.count
  } else {
    activities.value = res.data
    total.value = res.data.length || 0
  }
}

const fetchOpportunities = async () => {
  const res = await api.get('/opportunities/', { params: { page: 1, page_size: 1000 } })
  opportunities.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const typeLabel = (value) => {
  const match = types.find((t) => t.value === value)
  return match ? match.label : value
}

const createActivity = async () => {
  if (!form.value.subject) {
    error.value = '跟进目标不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      activity_type: form.value.activity_type,
      subject: form.value.subject,
      description: form.value.description,
      opportunity: form.value.opportunity ? Number(form.value.opportunity) : null,
      due_at: form.value.due_at || null
    }
    await api.post('/activities/', payload)
    form.value = { activity_type: 'internal', subject: '', description: '', opportunity: null, due_at: toLocalDateTime() }
    success.value = '跟进已保存'
    await fetchData()
  } catch (err) {
    const status = err.response?.status
    if (status === 401) {
      error.value = '登录已过期，请重新登录'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        error.value = messages || '保存失败，请检查必填项或后端服务'
      } else {
        error.value = '保存失败，请检查必填项或后端服务'
      }
    }
  } finally {
    saving.value = false
  }
}

const setType = (value) => {
  filters.value.type = value
  applyFilters()
}

const pagedActivities = computed(() => activities.value)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const totalCount = computed(() => total.value)
const todayCount = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return activities.value.filter((item) => (item.due_at || '').slice(0, 10) === today).length
})
const weekCount = computed(() => {
  const now = new Date()
  const start = new Date(now)
  start.setDate(now.getDate() - 6)
  return activities.value.filter((item) => {
    if (!item.due_at) return false
    const date = new Date(item.due_at)
    return date >= start && date <= now
  }).length
})

const applyFilters = () => {
  currentPage.value = 1
  fetchData()
}

const resetFilters = () => {
  search.value = ''
  filters.value.type = ''
  applyFilters()
}

const changePage = (page) => {
  currentPage.value = page
  fetchData()
}

const exportCsv = () => {
  const params = buildParams()
  delete params.page
  delete params.page_size
  api.get('/activities/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'followups.csv'
      link.click()
      URL.revokeObjectURL(url)
    })
}

const deleteActivity = async (id) => {
  if (!confirm('确认删除该跟进记录？')) return
  try {
    await api.delete(`/activities/${id}/`)
    await fetchData()
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      error.value = '无删除权限'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        error.value = detail.detail || '删除失败，请检查权限或后端服务'
      } else {
        error.value = '删除失败，请检查权限或后端服务'
      }
    }
  }
}

onMounted(async () => {
  await fetchOpportunities()
  await fetchData()
})

watch([ordering, () => filters.value.type], () => {
  applyFilters()
})
</script>
