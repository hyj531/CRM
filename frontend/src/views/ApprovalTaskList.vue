<template>
  <div>
    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="card list-card">
      <div class="list-head">
        <div class="list-head-info">
          <div class="section-title">我的审批</div>
          <div class="list-subtitle">共 {{ filteredItems.length }} 条</div>
        </div>
        <div class="list-head-actions">
          <button class="button secondary" @click="fetchTasks">刷新</button>
        </div>
      </div>

      <div class="tabs">
        <button class="tab" :class="{ active: statusFilter === 'pending' }" @click="setStatus('pending')">
          待审批
        </button>
        <button class="tab" :class="{ active: statusFilter === 'processed' }" @click="setStatus('processed')">
          已处理
        </button>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>业务类型</th>
              <th>标题</th>
              <th>步骤</th>
              <th>状态</th>
              <th>发起人</th>
              <th>发起时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredItems" :key="item.id">
              <td>{{ targetLabel(item.target_type) }}</td>
              <td>{{ item.target_title || '-' }}</td>
              <td>{{ item.step_name || '-' }}</td>
              <td>
                <span :class="['badge', statusBadge(item.status)]">{{ statusLabel(item.status) }}</span>
              </td>
              <td>{{ item.started_by_name || '-' }}</td>
              <td>{{ formatDate(item.created_at) }}</td>
              <td>
                <router-link class="text-link" :to="`/approvals/tasks/${item.id}`">处理</router-link>
              </td>
            </tr>
            <tr v-if="!filteredItems.length">
              <td colspan="7" style="text-align: center; color: #8a94a6;">暂无审批任务</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const error = ref('')
const tasks = ref([])
const statusFilter = ref('pending')

const fetchTasks = async () => {
  error.value = ''
  try {
    const params = {
      page: 1,
      page_size: 200,
      ordering: '-created_at'
    }
    if (statusFilter.value === 'pending') {
      params.status = 'pending'
    }
    const resp = await api.get('/approval-tasks/', { params })
    const data = resp.data?.results || resp.data || []
    tasks.value = Array.isArray(data) ? data : []
  } catch (err) {
    error.value = err.response?.data?.detail || '加载审批任务失败'
  }
}

const filteredItems = computed(() => {
  if (statusFilter.value === 'pending') return tasks.value
  return tasks.value.filter((item) => item.status && item.status !== 'pending')
})

const setStatus = (value) => {
  statusFilter.value = value
  fetchTasks()
}

const targetLabel = (value) => {
  const map = { contract: '合同', invoice: '开票', quote: '报价' }
  return map[value] || '审批'
}

const statusLabel = (value) => {
  const map = { pending: '待审批', approved: '已同意', rejected: '已驳回', blocked: '未轮到' }
  return map[value] || '-'
}

const statusBadge = (value) => {
  if (value === 'approved') return 'green'
  if (value === 'rejected') return 'orange'
  if (value === 'pending') return 'blue'
  return ''
}

const formatDate = (value) => {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

onMounted(fetchTasks)
</script>
