<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">任务</h2>
        <div class="page-subtitle">待办任务与截止时间管理</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="createTask">
          {{ saving ? '保存中...' : '保存任务' }}
        </button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">任务总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">进行中</div>
        <div class="stat-value">{{ openCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已完成</div>
        <div class="stat-value">{{ doneCount }}</div>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">新建任务</div>
        <div class="form-grid">
          <div>
            <label>标题</label>
            <input v-model="form.subject" />
          </div>
          <div>
            <label>截止时间</label>
            <input v-model="form.due_at" type="datetime-local" />
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
            <label>状态</label>
            <select v-model="form.status">
              <option value="open">进行中</option>
              <option value="done">完成</option>
              <option value="canceled">取消</option>
            </select>
          </div>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 条任务</div>
          <div>跟进节奏管理</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
          <div class="filter-left">
            <input v-model="search" placeholder="搜索任务标题" @keyup.enter="applyFilters" />
            <select v-model="statusFilter">
              <option value="">全部状态</option>
              <option value="open">进行中</option>
              <option value="done">完成</option>
              <option value="canceled">取消</option>
            </select>
            <button class="button" @click="applyFilters">搜索</button>
            <button class="button secondary" @click="resetFilters">清除</button>
          </div>
          <div class="filter-right">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="due_at">截止时间最早</option>
              <option value="-due_at">截止时间最新</option>
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
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>标题</th>
                <th>状态</th>
                <th>商机</th>
                <th>截止时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pagedTasks" :key="item.id">
                <td>{{ item.subject }}</td>
                <td>{{ item.status }}</td>
                <td>{{ opportunityName(item.opportunity) }}</td>
                <td>{{ item.due_at || '-' }}</td>
                <td>
                  <button v-if="canDelete" class="button secondary" @click="deleteTask(item.id)">删除</button>
                </td>
              </tr>
              <tr v-if="!pagedTasks.length">
                <td colspan="5" style="color: #888;">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>
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

const tasks = ref([])
const total = ref(0)
const opportunities = ref([])
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.task?.delete))
const error = ref('')
const success = ref('')
const saving = ref(false)
const search = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('due_at')

const form = ref({
  subject: '',
  status: 'open',
  opportunity: null,
  due_at: ''
})

const totalCount = computed(() => total.value)
const openCount = computed(() => tasks.value.filter((item) => item.status === 'open').length)
const doneCount = computed(() => tasks.value.filter((item) => item.status === 'done').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedTasks = computed(() => tasks.value)

const opportunityName = (oppId) => {
  const opp = opportunities.value.find((item) => item.id === oppId)
  return opp ? opp.opportunity_name : (oppId || '-')
}

const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
  if (search.value) params.search = search.value
  if (statusFilter.value) params.status = statusFilter.value
  return params
}

const fetchData = async () => {
  const res = await api.get('/tasks/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    tasks.value = res.data.results
    total.value = res.data.count
  } else {
    tasks.value = res.data
    total.value = res.data.length || 0
  }
}

const fetchOpportunities = async () => {
  const res = await api.get('/opportunities/', { params: { page: 1, page_size: 1000 } })
  opportunities.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const createTask = async () => {
  if (!form.value.subject) {
    error.value = '标题不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      opportunity: form.value.opportunity ? Number(form.value.opportunity) : null,
      due_at: form.value.due_at || null
    }
    await api.post('/tasks/', payload)
    success.value = '任务已保存'
    form.value = { subject: '', status: 'open', opportunity: null, due_at: '' }
    await fetchData()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      error.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      error.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    saving.value = false
  }
}

const exportCsv = () => {
  const params = buildParams()
  delete params.page
  delete params.page_size
  api.get('/tasks/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'tasks.csv'
      link.click()
      URL.revokeObjectURL(url)
    })
}

const applyFilters = () => {
  currentPage.value = 1
  fetchData()
}

const resetFilters = () => {
  search.value = ''
  statusFilter.value = ''
  applyFilters()
}

const changePage = (page) => {
  currentPage.value = page
  fetchData()
}

const deleteTask = async (id) => {
  if (!confirm('确认删除该任务？')) return
  try {
    await api.delete(`/tasks/${id}/`)
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

watch([statusFilter, ordering], () => {
  applyFilters()
})
</script>
