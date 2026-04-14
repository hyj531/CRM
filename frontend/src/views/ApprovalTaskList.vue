<template>
  <div class="approval-workbench">
    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="success" class="alert success">{{ success }}</div>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">待我审批</div>
        <div class="metric-value">{{ stats.pending_count }}</div>
      </div>
      <div class="metric-card danger">
        <div class="metric-label">已超时</div>
        <div class="metric-value">{{ stats.overdue_count }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">今日已处理</div>
        <div class="metric-value">{{ stats.processed_today_count }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">我发起进行中</div>
        <div class="metric-value">{{ stats.started_running_count }}</div>
      </div>
    </div>

    <div class="card list-card">
      <div class="list-head">
        <div class="list-head-info">
          <div class="section-title">审批中心</div>
          <div class="list-subtitle">共 {{ items.length }} 条</div>
        </div>
        <div class="list-head-actions">
          <button class="button secondary" @click="fetchAll">刷新</button>
        </div>
      </div>

      <div class="tabs">
        <button class="tab" :class="{ active: tab === 'pending' }" @click="setTab('pending')">
          待审批
        </button>
        <button class="tab" :class="{ active: tab === 'processed' }" @click="setTab('processed')">
          已处理
        </button>
        <button class="tab" :class="{ active: tab === 'started' }" @click="setTab('started')">
          我的发起
        </button>
      </div>

      <div class="filter-bar">
        <select v-model="filters.target_type">
          <option value="">全部业务类型</option>
          <option value="contract">合同</option>
          <option value="invoice">开票</option>
          <option value="quote">报价</option>
        </select>
        <select v-model="filters.region">
          <option value="">全部区域</option>
          <option v-for="region in regions" :key="region.id" :value="String(region.id)">
            {{ region.name || region.code || `ID ${region.id}` }}
          </option>
        </select>
        <select v-model="filters.instance_status">
          <option value="">全部流程状态</option>
          <option value="pending">审批中</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
          <option value="withdrawn">已撤回</option>
        </select>
        <select v-model="filters.started_by">
          <option value="">全部发起人</option>
          <option v-for="u in users" :key="u.id" :value="String(u.id)">
            {{ u.username || `ID ${u.id}` }}
          </option>
        </select>
        <input v-model="filters.created_from" type="date" />
        <input v-model="filters.created_to" type="date" />
        <input
          v-model.trim="filters.keyword"
          class="keyword-input"
          placeholder="搜索标题/编号"
          @keyup.enter="fetchInstances"
        />
        <button class="button" @click="fetchInstances">筛选</button>
        <button class="button secondary" @click="resetFilters">重置</button>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>业务类型</th>
              <th>标题</th>
              <th>当前步骤</th>
              <th>流程状态</th>
              <th>当前审批人</th>
              <th>SLA倒计时</th>
              <th>发起人</th>
              <th>发起时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in items"
              :key="item.instance_id"
              :class="{
                'row-overdue': tab === 'pending' && item.sla_level === 'overdue',
                'row-warning': tab === 'pending' && item.sla_level === 'warning'
              }"
            >
              <td>{{ targetLabel(item.target_type) }}</td>
              <td>
                <router-link class="link-button" :to="detailRoute(item)">
                  {{ item.target_title || '-' }}
                </router-link>
              </td>
              <td>{{ item.current_step_name || '-' }}</td>
              <td>
                <span :class="['badge', instanceStatusBadge(item.instance_status)]">
                  {{ instanceStatusLabel(item.instance_status) }}
                </span>
              </td>
              <td>{{ approverNames(item) }}</td>
              <td>
                <span :class="slaClass(item)">{{ slaText(item) }}</span>
              </td>
              <td>{{ item.started_by_name || '-' }}</td>
              <td>{{ formatDate(item.created_at) }}</td>
              <td>
                <div class="row-actions">
                  <template v-if="canQuickDecision(item)">
                    <button
                      class="button mini"
                      :disabled="decisionLoadingByInstance[item.instance_id]"
                      @click="quickDecision(item, true)"
                    >
                      同意
                    </button>
                    <button
                      class="button secondary mini"
                      :disabled="decisionLoadingByInstance[item.instance_id]"
                      @click="quickDecision(item, false)"
                    >
                      驳回
                    </button>
                  </template>
                  <router-link class="link-button" :to="detailRoute(item)">查看</router-link>
                </div>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="9" style="text-align: center; color: #8a94a6;">暂无审批记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api'

const error = ref('')
const success = ref('')
const tab = ref('pending')
const items = ref([])
const regions = ref([])
const users = ref([])
const decisionLoadingByInstance = ref({})
const stats = ref({
  pending_count: 0,
  overdue_count: 0,
  processed_today_count: 0,
  started_running_count: 0
})
const filters = ref({
  target_type: '',
  region: '',
  instance_status: '',
  started_by: '',
  created_from: '',
  created_to: '',
  keyword: ''
})

const fetchStats = async () => {
  try {
    const resp = await api.get('/approval-instances/mine/stats/')
    stats.value = {
      pending_count: Number(resp.data?.pending_count || 0),
      overdue_count: Number(resp.data?.overdue_count || 0),
      processed_today_count: Number(resp.data?.processed_today_count || 0),
      started_running_count: Number(resp.data?.started_running_count || 0)
    }
  } catch (err) {
    stats.value = {
      pending_count: 0,
      overdue_count: 0,
      processed_today_count: 0,
      started_running_count: 0
    }
  }
}

const fetchInstances = async () => {
  error.value = ''
  try {
    const params = {
      tab: tab.value,
      page: 1,
      page_size: 200,
      target_type: filters.value.target_type || undefined,
      region: filters.value.region || undefined,
      instance_status: filters.value.instance_status || undefined,
      started_by: filters.value.started_by || undefined,
      created_from: filters.value.created_from || undefined,
      created_to: filters.value.created_to || undefined,
      keyword: filters.value.keyword || undefined
    }
    const resp = await api.get('/approval-instances/mine/', { params })
    const data = resp.data?.results || resp.data || []
    items.value = Array.isArray(data) ? data : []
  } catch (err) {
    error.value = err.response?.data?.detail || '加载审批列表失败'
  }
}

const fetchRegions = async () => {
  try {
    const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
    regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    regions.value = []
  }
}

const fetchUsers = async () => {
  try {
    const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
    users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    users.value = []
  }
}

const fetchAll = async () => {
  await Promise.all([fetchInstances(), fetchStats()])
}

const setTab = async (value) => {
  tab.value = value
  await fetchAll()
}

const resetFilters = async () => {
  filters.value = {
    target_type: '',
    region: '',
    instance_status: '',
    started_by: '',
    created_from: '',
    created_to: '',
    keyword: ''
  }
  await fetchInstances()
}

const targetLabel = (value) => {
  const map = { contract: '合同', invoice: '开票', quote: '报价' }
  return map[value] || '审批'
}

const instanceStatusLabel = (value) => {
  const map = {
    pending: '审批中',
    approved: '已通过',
    rejected: '已驳回',
    withdrawn: '已撤回'
  }
  return map[value] || '-'
}

const instanceStatusBadge = (value) => {
  if (value === 'approved') return 'green'
  if (value === 'rejected') return 'orange'
  if (value === 'pending') return 'blue'
  return ''
}

const formatDate = (value) => {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

const approverNames = (item) => {
  const names = Array.isArray(item.current_approver_names) ? item.current_approver_names : []
  return names.length ? names.join('、') : '-'
}

const slaText = (item) => {
  if (tab.value !== 'pending') return '-'
  const seconds = Number(item.sla_remaining_seconds)
  if (!Number.isFinite(seconds)) return '-'
  if (seconds <= 0) return `已超时 ${formatDuration(Math.abs(seconds))}`
  return formatDuration(seconds)
}

const slaClass = (item) => {
  if (tab.value !== 'pending') return ''
  if (item.sla_level === 'overdue') return 'sla overdue'
  if (item.sla_level === 'warning') return 'sla warning'
  return 'sla normal'
}

const formatDuration = (seconds) => {
  const total = Math.max(0, Math.floor(seconds))
  const day = Math.floor(total / 86400)
  const hour = Math.floor((total % 86400) / 3600)
  const minute = Math.floor((total % 3600) / 60)
  if (day > 0) return `${day}天${hour}小时`
  if (hour > 0) return `${hour}小时${minute}分`
  return `${minute}分`
}

const canQuickDecision = (item) => {
  return tab.value === 'pending' && Number(item.my_pending_task_count || 0) === 1
}

const quickDecision = async (item, approved) => {
  const taskIds = Array.isArray(item.my_pending_task_ids) ? item.my_pending_task_ids : []
  if (taskIds.length !== 1) return
  const taskId = taskIds[0]
  decisionLoadingByInstance.value = {
    ...decisionLoadingByInstance.value,
    [item.instance_id]: true
  }
  error.value = ''
  success.value = ''
  try {
    await api.post(`/approval-tasks/${taskId}/decision/`, { approved, comment: '' })
    success.value = approved ? '审批已同意' : '审批已驳回'
    await fetchAll()
  } catch (err) {
    error.value = err.response?.data?.detail || '审批提交失败'
  } finally {
    decisionLoadingByInstance.value = {
      ...decisionLoadingByInstance.value,
      [item.instance_id]: false
    }
  }
}

const detailRoute = (item) => {
  const query = { from: 'approvals' }
  if (Array.isArray(item.my_pending_task_ids) && item.my_pending_task_ids.length) {
    query.task_id = String(item.my_pending_task_ids[0])
  }
  return {
    name: 'approval-instance',
    params: { id: item.instance_id },
    query
  }
}

onMounted(async () => {
  await Promise.all([fetchRegions(), fetchUsers()])
  await fetchAll()
})
</script>

<style scoped>
.approval-workbench {
  display: grid;
  gap: 12px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  background: #f8fbff;
  border: 1px solid #dbe7f6;
  border-radius: 12px;
  padding: 12px;
}

.metric-card.danger {
  background: #fff5f5;
  border-color: #ffd6d6;
}

.metric-label {
  font-size: 12px;
  color: #6b7280;
}

.metric-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.filter-bar {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0;
}

.filter-bar select,
.filter-bar input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 8px;
  font-size: 12px;
}

.keyword-input {
  grid-column: span 2;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.button.mini {
  padding: 4px 8px;
  font-size: 12px;
  min-height: auto;
}

.sla {
  font-size: 12px;
  font-weight: 600;
}

.sla.overdue {
  color: #c92a2a;
}

.sla.warning {
  color: #d97904;
}

.sla.normal {
  color: #0f766e;
}

.row-overdue {
  background: #fff6f6;
}

.row-warning {
  background: #fffaf2;
}

.alert {
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
}

.alert.error {
  background: #fff2f0;
  color: #c92a2a;
}

.alert.success {
  background: #eef9f0;
  color: #2b8a3e;
}

@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .keyword-input {
    grid-column: span 2;
  }
}
</style>
