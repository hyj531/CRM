<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">回款</h2>
        <div class="page-subtitle">回款登记与期次管理</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="savePayment">
          {{ saving ? '保存中...' : (editingId ? '保存修改' : '保存回款') }}
        </button>
        <button v-if="editingId" class="button secondary" @click="cancelEdit">取消编辑</button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

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
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">{{ editingId ? '编辑回款' : '新建回款' }}</div>
        <div class="form-grid">
          <div>
            <label>关联合同</label>
            <div class="filter-autocomplete">
              <input
                v-model="contractSearch"
                placeholder="输入合同/甲方关键词进行搜索"
                @focus="showContractDropdown = true"
                @input="showContractDropdown = true"
                @blur="hideContractDropdown"
              />
              <div v-if="showContractDropdown && contractSearch" class="filter-suggestions">
                <div
                  v-for="ct in filteredContracts"
                  :key="ct.id"
                  class="filter-suggestion"
                  @mousedown.prevent="selectContract(ct)"
                >
                  {{ contractLabel(ct) }}
                </div>
                <div v-if="!filteredContracts.length" class="filter-empty">无匹配合同</div>
              </div>
            </div>
          </div>
          <div>
            <label>回款金额</label>
            <input v-model.number="form.amount" type="number" />
          </div>
          <div>
            <label>回款状态</label>
            <select v-model="form.status">
              <option value="planned">未回款</option>
              <option value="partial">部分回款</option>
              <option value="paid">已回款</option>
            </select>
          </div>
          <div>
            <label>回款日期</label>
            <input v-model="form.paid_at" type="date" />
          </div>
          <div>
            <label>回款编号/备注</label>
            <input v-model="form.reference" />
          </div>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 条回款</div>
          <div>期次与状态追踪</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
          <div class="filter-left">
            <input v-model="search" placeholder="搜索回款备注/编号" @keyup.enter="applyFilters" />
            <select v-model="statusFilter">
              <option value="">全部状态</option>
              <option value="planned">未回款</option>
              <option value="partial">部分回款</option>
              <option value="paid">已回款</option>
            </select>
            <button class="button" @click="applyFilters">搜索</button>
            <button class="button secondary" @click="resetFilters">清除</button>
          </div>
          <div class="filter-right">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-paid_at">回款日期最新</option>
              <option value="-amount">回款金额高→低</option>
              <option value="amount">回款金额低→高</option>
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
                <th>合同名称</th>
                <th>合同金额</th>
                <th>合同甲方</th>
                <th>实收</th>
              <th>状态</th>
              <th>回款日期</th>
              <th>备注</th>
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
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || item.region || '-' }}</td>
              <td>
                <button v-if="canEdit" class="button secondary" @click="startEdit(item)">编辑</button>
                <button v-if="canDelete" class="button secondary" @click="deletePayment(item.id)">删除</button>
              </td>
            </tr>
              <tr v-if="!pagedPayments.length">
                <td colspan="10" style="color: #888;">暂无数据</td>
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

const payments = ref([])
const total = ref(0)
const contracts = ref([])
const accounts = ref([])
const contractSearch = ref('')
const showContractDropdown = ref(false)
const error = ref('')
const success = ref('')
const saving = ref(false)
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.payment?.delete))
const canEdit = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.payment?.update))
const search = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-paid_at')
const editingId = ref(null)

const statusLabel = (value) => {
  const map = {
    planned: '未回款',
    partial: '部分回款',
    paid: '已回款'
  }
  return map[value] || value || '-'
}

const form = ref({
  contract: null,
  amount: null,
  status: 'planned',
  paid_at: '',
  reference: ''
})

const totalCount = computed(() => total.value)
const totalAmount = computed(() => {
  const sum = payments.value.reduce((total, item) => total + (Number(item.amount) || 0), 0)
  return sum ? sum.toFixed(2) : '0.00'
})
const paidCount = computed(() => payments.value.filter((item) => item.status === 'paid').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedPayments = computed(() => payments.value)

const resetForm = () => {
  form.value = {
    contract: null,
    amount: null,
    status: 'planned',
    paid_at: '',
    reference: ''
  }
  contractSearch.value = ''
}

const contractLabel = (contract) => {
  if (!contract) return ''
  const name = contract.name || contract.contract_no || `合同${contract.id}`
  const accountId = contract.account
  const acc = accounts.value.find((item) => item.id === accountId)
  const accountName = acc ? (acc.full_name || acc.short_name || `甲方${acc.id}`) : (accountId ? `甲方${accountId}` : '')
  return accountName ? `${name}（${accountName}）` : name
}

const filteredContracts = computed(() => {
  const keyword = contractSearch.value.trim().toLowerCase()
  if (!keyword) return contracts.value
  return contracts.value.filter((ct) => {
    const name = (ct.name || ct.contract_no || '').toLowerCase()
    const accountId = ct.account
    const acc = accounts.value.find((item) => item.id === accountId)
    const accountName = acc ? `${acc.full_name || ''} ${acc.short_name || ''}`.toLowerCase() : ''
    return name.includes(keyword) || accountName.includes(keyword)
  })
})

const selectContract = (ct) => {
  form.value.contract = ct.id
  contractSearch.value = contractLabel(ct)
  showContractDropdown.value = false
}

const hideContractDropdown = () => {
  setTimeout(() => {
    showContractDropdown.value = false
  }, 120)
}


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
  return params
}

const fetchData = async () => {
  const res = await api.get('/payments/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    payments.value = res.data.results
    total.value = res.data.count
  } else {
    payments.value = res.data
    total.value = res.data.length || 0
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

const savePayment = async () => {
  if (!form.value.contract) {
    error.value = '请选择关联合同'
    return
  }
  if (!form.value.amount) {
    error.value = '回款金额不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      contract: Number(form.value.contract),
      amount: Number(form.value.amount),
      paid_at: form.value.paid_at || null
    }
    if (editingId.value) {
      await api.patch(`/payments/${editingId.value}/`, payload)
      success.value = '回款已更新'
      editingId.value = null
    } else {
      await api.post('/payments/', payload)
      success.value = '回款已保存'
    }
    resetForm()
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

const startEdit = (item) => {
  editingId.value = item.id
  error.value = ''
  success.value = ''
  form.value = {
    contract: item.contract != null ? Number(item.contract) : null,
    amount: item.amount != null ? Number(item.amount) : null,
    status: item.status || 'planned',
    paid_at: item.paid_at || '',
    reference: item.reference || ''
  }
  const ct = contracts.value.find((c) => c.id === item.contract)
  contractSearch.value = ct ? contractLabel(ct) : ''
}

const cancelEdit = () => {
  editingId.value = null
  resetForm()
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
  await fetchAccounts()
  await fetchContracts()
  await fetchData()
})

watch([statusFilter, ordering], () => {
  applyFilters()
})

watch(contractSearch, (val) => {
  if (!val) {
    form.value.contract = null
  }
})
</script>

<style scoped>
.filter-autocomplete {
  position: relative;
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
