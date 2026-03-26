<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">合同</h2>
        <div class="page-subtitle">合同创建、审批与回款衔接</div>
      </div>
      <div class="page-actions">
        <button class="button" @click="goCreate">新建合同</button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

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

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">筛选</div>
        <div class="field">
          <label>关键词</label>
          <input v-model="search" placeholder="搜索合同编号/名称" @keyup.enter="applyFilters" />
        </div>
        <div class="field">
          <label>合同状态</label>
          <select v-model="filters.status">
            <option value="">全部</option>
            <option value="draft">草稿</option>
            <option value="signed">已签署</option>
            <option value="active">履行中</option>
            <option value="closed">已关闭</option>
          </select>
        </div>
        <div class="field">
          <label>审批状态</label>
          <select v-model="filters.approval_status">
            <option value="">全部</option>
            <option value="pending">待审批</option>
            <option value="approved">已通过</option>
            <option value="rejected">已驳回</option>
          </select>
        </div>
        <div class="field">
          <label>签约日期</label>
          <div class="filter-range">
            <input v-model="filters.signed_at_start" type="date" />
            <span class="range-split">至</span>
            <input v-model="filters.signed_at_end" type="date" />
          </div>
        </div>
        <div class="field">
          <label>甲方</label>
          <div class="filter-autocomplete">
            <input
              v-model="accountSearch"
              placeholder="输入甲方名称/简称进行模糊搜索"
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
        </div>
        <div class="field">
          <label>乙方公司</label>
          <select v-model="filters.vendor_company">
            <option value="">全部</option>
            <option v-for="opt in lookupOptions.vendor_company" :key="opt.id" :value="String(opt.id)">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>区域</label>
          <select v-model="filters.region">
            <option value="">全部</option>
            <option v-for="region in regions" :key="region.id" :value="String(region.id)">
              {{ region.name || region.code || `ID ${region.id}` }}
            </option>
          </select>
        </div>
        <div class="filter-actions">
          <button class="button" @click="applyFilters">搜索</button>
          <button class="button secondary" @click="resetFilters">清除</button>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 份合同</div>
          <div>审批与金额状态</div>
        </div>
        <div class="list-toolbar">
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
        <div v-for="item in pagedContracts" :key="item.id" class="list-row">
          <div>
            <router-link class="list-title link-button" :to="`/contracts/${item.id}`">
              {{ item.name || item.contract_no || `合同${item.id}` }}
            </router-link>
            <div class="list-meta">
              <span :class="['badge', statusBadgeClass(item.status)]">{{ statusLabel(item.status) }}</span>
              <span :class="['badge', approvalBadgeClass(item.approval_status)]">
                {{ approvalLabel(item.approval_status) }}
              </span>
              <span>甲方：{{ accountName(item.account) }}</span>
              <span>乙方：{{ vendorName(item.vendor_company) }}</span>
              <span>金额：{{ formatMoney(item.amount) }}</span>
              <span>回款：{{ formatMoney(item.paid_total) }}</span>
              <span>当前产值：{{ item.current_output ?? '-' }}</span>
              <span>应收款：{{ receivableAmount(item) }}</span>
              <span>签署：{{ item.signed_at || '-' }}</span>
              <span>区域：{{ item.region_name || '-' }}</span>
              <span>负责人：{{ item.owner_name || item.owner || '-' }}</span>
            </div>
          </div>
          <div class="list-actions">
            <router-link class="link-button" :to="`/contracts/${item.id}`">详情</router-link>
            <button v-if="canDelete" class="button secondary" @click="deleteContract(item.id)">删除</button>
          </div>
        </div>
        <div v-if="!pagedContracts.length" style="padding: 16px; color: #888;">暂无数据</div>
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
const router = useRouter()
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contract?.delete))

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

const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
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

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedContracts = computed(() => contracts.value)

const goCreate = () => {
  router.push('/contracts/new')
}

const resetFilters = () => {
  search.value = ''
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
</style>
