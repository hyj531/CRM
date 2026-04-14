<template>
  <div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">开票总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">开票金额合计</div>
        <div class="stat-value">{{ totalAmount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已审批</div>
        <div class="stat-value">{{ approvedCount }}</div>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="filter-bar payment-filters">
      <div class="filter-left">
        <input v-model="search" placeholder="搜索开票编号/合同/客户" @keyup.enter="applyFilters" />
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="issued">已开票</option>
          <option value="paid">已回款</option>
          <option value="void">已作废</option>
        </select>
        <select v-model="approvalFilter">
          <option value="">全部审批</option>
          <option value="pending">待审批</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
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
          <input v-model="issuedAtStart" type="date" />
          <span class="range-split">至</span>
          <input v-model="issuedAtEnd" type="date" />
        </div>
        <button class="button" @click="applyFilters">搜索</button>
        <button class="button secondary" @click="resetFilters">清除</button>
      </div>
    </div>

    <div class="card list-card">
      <div class="list-head">
        <div class="list-head-info">
          <div>共 {{ totalCount }} 条开票申请</div>
        </div>
        <div class="list-head-actions">
          <button class="button" @click="goCreate">新建开票</button>
          <div class="toolbar-left">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-issued_at">开票日期最新</option>
              <option value="-amount">开票金额高→低</option>
              <option value="amount">开票金额低→高</option>
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
              <th>开票编号</th>
              <th>合同</th>
              <th>客户</th>
              <th>金额</th>
              <th>税率</th>
              <th>类型</th>
              <th>状态</th>
              <th>审批</th>
              <th>开票日期</th>
              <th>负责人</th>
              <th>所属区域</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedInvoices" :key="item.id">
              <td>{{ item.invoice_no || '-' }}</td>
              <td>{{ contractDisplayName(item.contract) }}</td>
              <td>{{ accountName(item.account) }}</td>
              <td>{{ item.amount }}</td>
              <td>{{ item.tax_rate ?? '-' }}</td>
              <td>{{ invoiceTypeLabel(item.invoice_type) }}</td>
              <td>{{ statusLabel(item.status) }}</td>
              <td>{{ approvalLabel(item.approval_status) }}</td>
              <td>{{ item.issued_at || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || item.region || '-' }}</td>
              <td>
                <router-link class="link-button" :to="`/invoices/${item.id}`">详情</router-link>
                <button v-if="canDelete" class="button secondary" @click="deleteInvoice(item.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!pagedInvoices.length">
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

const invoices = ref([])
const total = ref(0)
const summary = ref({
  total_amount: 0,
  total_count: 0
})
const cardMoneyFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})
const regions = ref([])
const users = ref([])
const contracts = ref([])
const accounts = ref([])
const error = ref('')
const router = useRouter()
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.invoice?.delete))
const search = ref('')
const statusFilter = ref('')
const approvalFilter = ref('')
const regionFilter = ref('')
const ownerFilter = ref('')
const issuedAtStart = ref('')
const issuedAtEnd = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-issued_at')

const statusLabel = (value) => {
  const map = {
    draft: '草稿',
    issued: '已开票',
    paid: '已回款',
    void: '已作废'
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

const invoiceTypeLabel = (value) => {
  const map = {
    normal: '普票',
    special: '专票'
  }
  return map[value] || value || '-'
}

const totalCount = computed(() => total.value)
const totalAmount = computed(() => {
  const value = Number(summary.value.total_amount || 0)
  if (!Number.isFinite(value)) return '0.00'
  return cardMoneyFormatter.format(value)
})
const approvedCount = computed(() => invoices.value.filter((item) => item.approval_status === 'approved').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedInvoices = computed(() => invoices.value)

const contractDisplayName = (contractId) => {
  const ct = contracts.value.find((item) => item.id === contractId)
  if (!ct) return contractId || '-'
  return ct.name || ct.contract_no || `合同${ct.id}`
}

const accountName = (accountId) => {
  const acc = accounts.value.find((item) => item.id === accountId)
  if (!acc) return accountId || '-'
  return acc.full_name || acc.short_name || accountId || '-'
}

const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
  if (search.value) params.search = search.value
  if (statusFilter.value) params.status = statusFilter.value
  if (approvalFilter.value) params.approval_status = approvalFilter.value
  if (regionFilter.value) params.region = regionFilter.value
  if (ownerFilter.value) params.owner = ownerFilter.value
  if (issuedAtStart.value) params.issued_at_start = issuedAtStart.value
  if (issuedAtEnd.value) params.issued_at_end = issuedAtEnd.value
  return params
}

const fetchData = async () => {
  const res = await api.get('/invoices/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    invoices.value = res.data.results
    total.value = res.data.count
    if (res.data.total_amount != null) {
      summary.value = {
        total_amount: res.data.total_amount,
        total_count: res.data.count || 0
      }
    } else {
      const sum = invoices.value.reduce((acc, item) => acc + (Number(item.amount) || 0), 0)
      summary.value = {
        total_amount: sum || 0,
        total_count: total.value
      }
    }
  } else {
    invoices.value = res.data
    total.value = res.data.length || 0
    const sum = invoices.value.reduce((acc, item) => acc + (Number(item.amount) || 0), 0)
    summary.value = {
      total_amount: sum || 0,
      total_count: total.value
    }
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
  router.push('/invoices/new')
}

const exportCsv = () => {
  const params = buildParams()
  delete params.page
  delete params.page_size
  api.get('/invoices/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'invoices.csv'
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
  approvalFilter.value = ''
  regionFilter.value = ''
  ownerFilter.value = ''
  issuedAtStart.value = ''
  issuedAtEnd.value = ''
  applyFilters()
}

const changePage = (page) => {
  currentPage.value = page
  fetchData()
}

const deleteInvoice = async (id) => {
  if (!confirm('确认删除该开票申请？')) return
  try {
    await api.delete(`/invoices/${id}/`)
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
  await auth.ensureMeFresh(60000)
  await fetchRegions()
  await fetchUsers()
  await fetchAccounts()
  await fetchContracts()
  await fetchData()
})

watch([statusFilter, approvalFilter, ordering], () => {
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
