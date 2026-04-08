<template>
  <div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">回款总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">回款金额合计</div>
        <div class="stat-value">{{ totalAmount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已回款</div>
        <div class="stat-value">{{ paidCount }}</div>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="filter-bar payment-filters">
      <div class="filter-left">
        <input v-model="search" placeholder="搜索回款备注/编号" @keyup.enter="applyFilters" />
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option value="planned">未回款</option>
          <option value="partial">部分回款</option>
          <option value="paid">已回款</option>
        </select>
        <select v-model="regionFilter">
          <option value="">所属区域</option>
          <option v-for="region in regions" :key="region.id" :value="String(region.id)">
            {{ region.name || region.code || `ID ${region.id}` }}
          </option>
        </select>
        <select v-model="ownerFilter">
          <option value="">负责人</option>
          <option v-for="u in users" :key="u.id" :value="String(u.id)">
            {{ u.username || u.email || `ID ${u.id}` }}
          </option>
        </select>
        <div class="filter-range">
          <input v-model="paidAtStart" type="date" />
          <span class="range-split">至</span>
          <input v-model="paidAtEnd" type="date" />
        </div>
        <button class="button" @click="applyFilters">搜索</button>
        <button class="button secondary" @click="resetFilters">清除</button>
      </div>
    </div>

    <div class="card list-card">
      <div class="list-head">
        <div class="list-head-info">
          <div>共 {{ totalCount }} 条回款</div>
        </div>
        <div class="list-head-actions">
          <button class="button" @click="goCreate">新建回款</button>
          <div class="toolbar-left">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-paid_at">回款日期最新</option>
              <option value="-amount">回款金额高→低</option>
              <option value="amount">回款金额低→高</option>
            </select>
          </div>
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
          <table class="table payment-table">
            <thead>
              <tr>
                <th>合同名称</th>
                <th>合同金额</th>
                <th>合同甲方</th>
                <th>实收</th>
                <th>状态</th>
                <th>回款日期</th>
                <th>备注</th>
                <th>回款说明</th>
                <th>录入人</th>
                <th>负责人</th>
                <th>所属区域</th>
                <th>操作</th>
            </tr>
          </thead>
          <tbody>
              <tr v-for="item in pagedPayments" :key="item.id">
                <td>{{ contractDisplayName(item.contract) }}</td>
                <td>{{ contractAmount(item.contract) }}</td>
                <td>{{ contractAccountName(item.contract) }}</td>
                <td>{{ item.amount }}</td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ item.paid_at || '-' }}</td>
                <td>{{ item.reference || '-' }}</td>
                <td>{{ item.note || '-' }}</td>
                <td>{{ item.created_by_name || item.created_by || '-' }}</td>
                <td>{{ item.owner_name || item.owner || '-' }}</td>
                <td>{{ item.region_name || item.region || '-' }}</td>
                <td>
                  <router-link class="link-button" :to="`/payments/${item.id}`">详情</router-link>
                  <button v-if="canDelete" class="button secondary" @click="deletePayment(item.id)">删除</button>
                </td>
            </tr>
              <tr v-if="!pagedPayments.length">
                <td colspan="12" style="color: #888;">暂无数据</td>
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
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const payments = ref([])
const total = ref(0)
const summary = ref({
  total_amount: 0,
  total_count: 0
})
const regions = ref([])
const users = ref([])
const contracts = ref([])
const accounts = ref([])
const error = ref('')
const router = useRouter()
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.payment?.delete))
const search = ref('')
const statusFilter = ref('')
const regionFilter = ref('')
const ownerFilter = ref('')
const paidAtStart = ref('')
const paidAtEnd = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-paid_at')

const statusLabel = (value) => {
  const map = {
    planned: '未回款',
    partial: '部分回款',
    paid: '已回款'
  }
  return map[value] || value || '-'
}

const totalCount = computed(() => total.value)
const totalAmount = computed(() => Number(summary.value.total_amount || 0).toFixed(2))
const paidCount = computed(() => payments.value.filter((item) => item.status === 'paid').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedPayments = computed(() => payments.value)

const formatMoney = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
}

const contractDisplayName = (contractId) => {
  const ct = contracts.value.find((item) => item.id === contractId)
  if (!ct) return contractId || '-'
  return ct.name || ct.contract_no || `合同${ct.id}`
}

const contractAmount = (contractId) => {
  const ct = contracts.value.find((item) => item.id === contractId)
  return ct ? formatMoney(ct.amount) : '-'
}

const contractAccountName = (contractId) => {
  const ct = contracts.value.find((item) => item.id === contractId)
  if (!ct) return '-'
  const accountId = ct.account
  const acc = accounts.value.find((item) => item.id === accountId)
  return acc ? (acc.full_name || acc.short_name || `甲方${acc.id}`) : (accountId ? `甲方${accountId}` : '-')
}


const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
  if (search.value) params.search = search.value
  if (statusFilter.value) params.status = statusFilter.value
  if (regionFilter.value) params.region = regionFilter.value
  if (ownerFilter.value) params.owner = ownerFilter.value
  if (paidAtStart.value) params.paid_at_start = paidAtStart.value
  if (paidAtEnd.value) params.paid_at_end = paidAtEnd.value
  return params
}

const fetchData = async () => {
  const res = await api.get('/payments/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    payments.value = res.data.results
    total.value = res.data.count
    if (res.data.total_amount != null) {
      summary.value = {
        total_amount: res.data.total_amount,
        total_count: res.data.count || 0
      }
    } else {
      await fetchSummary()
    }
  } else {
    payments.value = res.data
    total.value = res.data.length || 0
    const sum = payments.value.reduce((total, item) => total + (Number(item.amount) || 0), 0)
    summary.value = {
      total_amount: sum || 0,
      total_count: total.value
    }
  }
}

const fetchSummary = async () => {
  try {
    const params = buildParams()
    delete params.page
    delete params.page_size
    const summaryRes = await api.get('/payments/summary/', { params })
    summary.value = summaryRes.data || { total_amount: 0, total_count: 0 }
  } catch (err) {
    summary.value = { total_amount: 0, total_count: 0 }
  }
}

const fetchContracts = async () => {
  const res = await api.get('/contracts/', { params: { page: 1, page_size: 1000 } })
  contracts.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const fetchAccounts = async () => {
  const res = await api.get('/accounts/', { params: { page: 1, page_size: 1000 } })
  accounts.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchUsers = async () => {
  const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
  users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}
const goCreate = () => {
  router.push('/payments/new')
}

const exportCsv = () => {
  const params = buildParams()
  delete params.page
  delete params.page_size
  api.get('/payments/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'payments.csv'
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
  regionFilter.value = ''
  ownerFilter.value = ''
  paidAtStart.value = ''
  paidAtEnd.value = ''
  applyFilters()
}

const changePage = (page) => {
  currentPage.value = page
  fetchData()
}

const deletePayment = async (id) => {
  if (!confirm('确认删除该回款记录？')) return
  try {
    await api.delete(`/payments/${id}/`)
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
  await fetchRegions()
  await fetchUsers()
  await fetchAccounts()
  await fetchContracts()
  await fetchData()
})

watch([statusFilter, ordering], () => {
  applyFilters()
})
</script>

<style scoped>
.filter-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-split {
  color: #94a3b8;
}
</style>
