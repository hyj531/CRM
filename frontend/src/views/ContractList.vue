<template>
  <div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">合同总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">合同金额合计</div>
        <div class="stat-value">{{ contractTotal }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">回款合计</div>
        <div class="stat-value">{{ paidTotal }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">应收款合计</div>
        <div class="stat-value">{{ receivableTotal }}</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: activeTab === 'all' }" @click="setTab('all')">全部合同</button>
      <button class="tab" :class="{ active: activeTab === 'receivable' }" @click="setTab('receivable')">应收款</button>
      <button class="tab" :class="{ active: activeTab === 'framework' }" @click="setTab('framework')">框架合同</button>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="filter-bar contract-filters">
      <div class="filter-left">
        <input v-model="search" placeholder="搜索合同编号/名称" @keyup.enter="applyFilters" />
        <select v-model="filters.status">
          <option value="">合同状态</option>
          <option value="draft">草稿</option>
          <option value="signed">已签署</option>
          <option value="active">履行中</option>
          <option value="closed">已关闭</option>
        </select>
        <select v-model="filters.approval_status">
          <option value="">审批状态</option>
          <option value="pending">待审批</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
        </select>
        <div class="filter-range">
          <input v-model="filters.signed_at_start" type="date" />
          <span class="range-split">至</span>
          <input v-model="filters.signed_at_end" type="date" />
        </div>
        <div class="filter-autocomplete">
          <input
            v-model="accountSearch"
            placeholder="输入甲方名称/简称"
            @focus="showAccountDropdown = true"
            @input="showAccountDropdown = true"
            @blur="hideAccountDropdown"
          />
          <div v-if="showAccountDropdown && accountSearch" class="filter-suggestions">
            <div
              v-for="acc in filteredAccounts"
              :key="acc.id"
              class="filter-suggestion"
              @mousedown.prevent="selectFilterAccount(acc)"
            >
              {{ accountLabel(acc) }}
            </div>
            <div v-if="!filteredAccounts.length" class="filter-empty">无匹配客户</div>
          </div>
        </div>
        <select v-model="filters.vendor_company">
          <option value="">乙方公司</option>
          <option v-for="opt in lookupOptions.vendor_company" :key="opt.id" :value="String(opt.id)">
            {{ opt.name }}
          </option>
        </select>
        <select v-model="filters.region">
          <option value="">区域</option>
          <option v-for="region in regions" :key="region.id" :value="String(region.id)">
            {{ region.name || region.code || `ID ${region.id}` }}
          </option>
        </select>
        <select v-if="isReceivableTab" v-model="receivableUrgentFilter">
          <option value="">是否重点催收</option>
          <option value="1">仅重点</option>
          <option value="0">仅非重点</option>
        </select>
        <button class="button" @click="applyFilters">搜索</button>
        <button class="button secondary" @click="resetFilters">清除</button>
      </div>
    </div>

    <div class="card list-card">
      <div class="list-head">
        <div class="list-head-info">
          <div>{{ listTitle }}</div>
        </div>
        <div class="list-head-actions">
          <button class="button" @click="goCreate">新建合同</button>
          <div class="toolbar-left">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-created_at">最新创建</option>
              <option value="-signed_at">最新签署</option>
              <option value="-amount">合同金额高→低</option>
              <option value="amount">合同金额低→高</option>
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
      <div v-if="!isReceivableTab" class="table-wrap contract-table-wrap">
        <table class="table contract-table">
          <thead>
            <tr>
              <th>合同名称</th>
              <th>合同状态</th>
              <th>审批状态</th>
              <th>甲方</th>
              <th>乙方</th>
              <th>合同金额</th>
              <th>回款</th>
              <th>当前产值</th>
              <th>应收款</th>
              <th>签署日期</th>
              <th>区域</th>
              <th>负责人</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedContracts" :key="item.id">
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">
                  {{ item.name || item.contract_no || `合同${item.id}` }}
                </router-link>
              </td>
              <td>
                <span :class="['badge', statusBadgeClass(item.status)]">{{ statusLabel(item.status) }}</span>
              </td>
              <td>
                <span :class="['badge', approvalBadgeClass(item.approval_status)]">
                  {{ approvalLabel(item.approval_status) }}
                </span>
              </td>
              <td>{{ accountName(item.account) }}</td>
              <td>{{ vendorName(item.vendor_company) }}</td>
              <td>{{ formatMoney(item.amount) }}</td>
              <td>{{ formatMoney(item.paid_total) }}</td>
              <td>{{ item.current_output ?? '-' }}</td>
              <td>{{ receivableAmount(item) }}</td>
              <td>{{ item.signed_at || '-' }}</td>
              <td>{{ item.region_name || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">详情</router-link>
                <button v-if="canDelete" class="button secondary" @click="deleteContract(item.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!pagedContracts.length">
              <td colspan="13" style="color: #888;">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="table-wrap contract-table-wrap">
        <table class="table contract-receivable-table">
          <thead>
            <tr>
              <th>合同名称</th>
              <th>客户</th>
              <th>合同金额</th>
              <th>已回款</th>
              <th>应收款</th>
              <th>负责人</th>
              <th>区域</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedContracts" :key="item.id" :class="{ 'row-urgent': item.receivable_urgent }">
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">
                  {{ item.name || item.contract_no || `合同${item.id}` }}
                </router-link>
                <span v-if="item.receivable_urgent" class="badge orange urgent-badge">重点催收</span>
              </td>
              <td>{{ accountName(item.account) }}</td>
              <td>{{ formatMoney(item.amount) }}</td>
              <td>{{ formatMoney(item.paid_total) }}</td>
              <td>{{ receivableAmount(item) }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || '-' }}</td>
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">详情</router-link>
                <button class="button secondary small" @click="toggleUrgent(item)">
                  {{ item.receivable_urgent ? '取消催收' : '标记催收' }}
                </button>
                <button v-if="canDelete" class="button secondary" @click="deleteContract(item.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!pagedContracts.length">
              <td colspan="8" style="color: #888;">暂无数据</td>
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

const contracts = ref([])
const total = ref(0)
const error = ref('')
const search = ref('')
const summary = ref({
  contract_total: 0,
  paid_total: 0,
  receivable_total: 0
})
const filters = ref({
  status: '',
  approval_status: '',
  account: '',
  vendor_company: '',
  region: '',
  signed_at_start: '',
  signed_at_end: ''
})
const lookupOptions = ref({
  vendor_company: []
})
const regions = ref([])
const accounts = ref([])
const accountSearch = ref('')
const showAccountDropdown = ref(false)
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-signed_at')
const activeTab = ref('all')
const receivableUrgentFilter = ref('')
const router = useRouter()
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contract?.delete))
const isReceivableTab = computed(() => activeTab.value === 'receivable')
const isFrameworkTab = computed(() => activeTab.value === 'framework')

const statusLabel = (value) => {
  const map = {
    draft: '草稿',
    signed: '已签署',
    active: '履行中',
    closed: '已关闭'
  }
  return map[value] || value || '-'
}

const approvalLabel = (value) => {
  const map = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回'
  }
  return map[value] || value || '-'
}

const statusBadgeClass = (value) => {
  if (value === 'active') return 'green'
  if (value === 'closed') return 'gray'
  return 'orange'
}

const approvalBadgeClass = (value) => {
  if (value === 'approved') return 'green'
  if (value === 'rejected') return 'gray'
  return 'orange'
}

const accountLabel = (acc) => acc.full_name || acc.short_name || acc.name || `ID ${acc.id}`

const filteredAccounts = computed(() => {
  const keyword = accountSearch.value.trim().toLowerCase()
  if (!keyword) return accounts.value
  return accounts.value.filter((acc) => {
    const fullName = (acc.full_name || '').toLowerCase()
    const shortName = (acc.short_name || '').toLowerCase()
    return fullName.includes(keyword) || shortName.includes(keyword)
  })
})

const selectFilterAccount = (acc) => {
  filters.value.account = String(acc.id)
  accountSearch.value = accountLabel(acc)
  showAccountDropdown.value = false
  applyFilters()
}

const hideAccountDropdown = () => {
  setTimeout(() => {
    showAccountDropdown.value = false
  }, 120)
}

const accountName = (accountId) => {
  const acc = accounts.value.find((item) => item.id === accountId)
  if (!acc) return accountId || '-'
  return acc.full_name || acc.short_name || accountId || '-'
}

const vendorName = (vendorId) => {
  const item = lookupOptions.value.vendor_company.find((opt) => String(opt.id) === String(vendorId))
  return item ? item.name : (vendorId || '-')
}

const formatMoney = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
}

const receivableAmount = (item) => {
  if (!item) return '-'
  const paidTotal = Number(item.paid_total || 0)
  const base = item.current_output != null ? Number(item.current_output) : Number(item.amount)
  if (Number.isNaN(base)) return '-'
  const value = base - paidTotal
  return Number.isFinite(value) ? value.toFixed(2) : '-'
}

const setTab = (tab) => {
  if (activeTab.value === tab) return
  activeTab.value = tab
  receivableUrgentFilter.value = ''
  currentPage.value = 1
  fetchData()
}

const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
  if (isReceivableTab.value) params.receivable_only = 1
  if (isReceivableTab.value && receivableUrgentFilter.value) {
    params.receivable_urgent = receivableUrgentFilter.value
  }
  if (isFrameworkTab.value) params.is_framework = 1
  if (search.value) params.search = search.value
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.approval_status) params.approval_status = filters.value.approval_status
  if (filters.value.account) params.account = filters.value.account
  if (filters.value.vendor_company) params.vendor_company = filters.value.vendor_company
  if (filters.value.region) params.region = filters.value.region
  if (filters.value.signed_at_start) params.signed_at_start = filters.value.signed_at_start
  if (filters.value.signed_at_end) params.signed_at_end = filters.value.signed_at_end
  return params
}

const fetchData = async () => {
  error.value = ''
  const params = buildParams()
  try {
    const summaryRes = await api.get('/contracts/summary/', { params })
    summary.value = summaryRes.data || { contract_total: 0, paid_total: 0, receivable_total: 0 }
  } catch (err) {
    summary.value = { contract_total: 0, paid_total: 0, receivable_total: 0 }
  }
  try {
    const res = await api.get('/contracts/', { params })
    if (res.data && Array.isArray(res.data.results)) {
      contracts.value = res.data.results
      total.value = res.data.count
    } else {
      contracts.value = res.data
      total.value = res.data.length || 0
    }
  } catch (err) {
    contracts.value = []
    total.value = 0
    const status = err.response?.status
    if (status === 401) {
      error.value = '登录已过期，请重新登录'
    } else {
      error.value = '加载失败，请确认已登录且后端服务可用'
    }
  }
}

const fetchLookups = async () => {
  const res = await api.get('/lookups/')
  const categories = Array.isArray(res.data?.results) ? res.data.results : res.data
  const pick = (code) => {
    const cat = categories.find((c) => c.code === code)
    return cat ? cat.options : []
  }
  lookupOptions.value = {
    vendor_company: pick('vendor_company')
  }
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchAccounts = async () => {
  const res = await api.get('/accounts/', { params: { page: 1, page_size: 1000 } })
  accounts.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const totalCount = computed(() => total.value)
const contractTotal = computed(() => Number(summary.value.contract_total || 0).toFixed(2))
const paidTotal = computed(() => Number(summary.value.paid_total || 0).toFixed(2))
const receivableTotal = computed(() => Number(summary.value.receivable_total || 0).toFixed(2))
const listTitle = computed(() => {
  if (isReceivableTab.value) return `共 ${totalCount.value} 份应收合同`
  if (isFrameworkTab.value) return `共 ${totalCount.value} 份框架合同`
  return `共 ${totalCount.value} 份合同`
})

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedContracts = computed(() => contracts.value)

const goCreate = () => {
  router.push('/contracts/new')
}

const resetFilters = () => {
  search.value = ''
  receivableUrgentFilter.value = ''
  filters.value = {
    status: '',
    approval_status: '',
    account: '',
    vendor_company: '',
    region: '',
    signed_at_start: '',
    signed_at_end: ''
  }
  applyFilters()
}

const applyFilters = () => {
  currentPage.value = 1
  fetchData()
}

const changePage = (page) => {
  currentPage.value = page
  fetchData()
}

const exportCsv = () => {
  const params = buildParams()
  delete params.page
  delete params.page_size
  api.get('/contracts/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'contracts.csv'
      link.click()
      URL.revokeObjectURL(url)
    })
}

const toggleUrgent = async (item) => {
  if (!item) return
  const nextValue = !item.receivable_urgent
  try {
    await api.patch(`/contracts/${item.id}/`, { receivable_urgent: nextValue })
    item.receivable_urgent = nextValue
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      error.value = '无修改权限'
    } else {
      error.value = '标记失败，请稍后重试'
    }
  }
}

const deleteContract = async (id) => {
  if (!confirm('确认删除该合同？')) return
  try {
    await api.delete(`/contracts/${id}/`)
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
  await fetchLookups()
  await fetchRegions()
  await fetchAccounts()
  await fetchData()
})

watch(ordering, () => {
  applyFilters()
})

watch(accountSearch, (val) => {
  if (!val) {
    filters.value.account = ''
  }
})
</script>

<style scoped>
.filter-autocomplete {
  position: relative;
}

.filter-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-split {
  color: #94a3b8;
}

.filter-suggestions {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
  max-height: 220px;
  overflow: auto;
  z-index: 20;
}

.filter-suggestion {
  padding: 8px 10px;
  cursor: pointer;
}

.filter-suggestion:hover {
  background: #f1f5f9;
}

.filter-empty {
  padding: 8px 10px;
  color: #94a3b8;
}

.row-urgent td {
  background: #ffe8cc;
}

.urgent-badge {
  margin-left: 6px;
}
</style>
