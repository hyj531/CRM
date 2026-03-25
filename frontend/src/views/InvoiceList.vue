<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">开票申请</h2>
        <div class="page-subtitle">开票申请与审批状态跟踪</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="saveInvoice">
          {{ saving ? '保存中...' : (editingId ? '保存修改' : '保存开票') }}
        </button>
        <button v-if="editingId" class="button secondary" @click="cancelEdit">取消编辑</button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">申请总数</div>
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
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">{{ editingId ? '编辑开票申请' : '新建开票申请' }}</div>
        <div class="form-grid">
          <div>
            <label>开票编号</label>
            <input v-model="form.invoice_no" />
          </div>
          <div>
            <label>关联合同</label>
            <select v-model.number="form.contract">
              <option :value="null">请选择合同</option>
              <option v-for="ct in contracts" :key="ct.id" :value="ct.id">
                {{ contractLabel(ct) }}
              </option>
            </select>
          </div>
          <div>
            <label>关联客户</label>
            <select v-model.number="form.account">
              <option :value="null">未关联</option>
              <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                {{ acc.full_name }}{{ acc.short_name ? `（${acc.short_name}）` : '' }}
              </option>
            </select>
          </div>
          <div>
            <label>开票金额</label>
            <input v-model.number="form.amount" type="number" />
          </div>
          <div>
            <label>税率</label>
            <input v-model.number="form.tax_rate" type="number" step="0.01" />
          </div>
          <div>
            <label>开票类型</label>
            <select v-model="form.invoice_type">
              <option value="normal">普票</option>
              <option value="special">专票</option>
            </select>
          </div>
          <div>
            <label>申请状态</label>
            <select v-model="form.status">
              <option value="draft">草稿</option>
              <option value="issued">已开票</option>
              <option value="paid">已回款</option>
              <option value="void">已作废</option>
            </select>
          </div>
          <div>
            <label>审批状态</label>
            <select v-model="form.approval_status">
              <option value="pending">待审批</option>
              <option value="approved">已通过</option>
              <option value="rejected">已驳回</option>
            </select>
          </div>
          <div>
            <label>开票日期</label>
            <input v-model="form.issued_at" type="date" />
          </div>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 条开票申请</div>
          <div>审批与开票状态</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
          <div class="filter-left">
            <input v-model="search" placeholder="搜索开票编号" @keyup.enter="applyFilters" />
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
            <button class="button" @click="applyFilters">搜索</button>
            <button class="button secondary" @click="resetFilters">清除</button>
          </div>
          <div class="filter-right">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-issued_at">开票日期最新</option>
              <option value="-amount">开票金额高→低</option>
              <option value="amount">开票金额低→高</option>
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
                <td>{{ contractName(item.contract) }}</td>
                <td>{{ accountName(item.account) }}</td>
                <td>{{ item.amount }}</td>
                <td>{{ item.tax_rate || '-' }}</td>
                <td>{{ invoiceTypeLabel(item.invoice_type) }}</td>
                <td>{{ statusLabel(item.status) }}</td>
              <td>{{ approvalLabel(item.approval_status) }}</td>
              <td>{{ item.issued_at || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || item.region || '-' }}</td>
              <td>
                <button v-if="canEdit" class="button secondary" @click="startEdit(item)">编辑</button>
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const invoices = ref([])
const total = ref(0)
const contracts = ref([])
const accounts = ref([])
const error = ref('')
const success = ref('')
const saving = ref(false)
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.invoice?.delete))
const canEdit = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.invoice?.update))
const search = ref('')
const statusFilter = ref('')
const approvalFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-issued_at')
const editingId = ref(null)

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

const form = ref({
  invoice_no: '',
  contract: null,
  account: null,
  amount: null,
  tax_rate: null,
  invoice_type: 'normal',
  status: 'draft',
  approval_status: 'pending',
  issued_at: ''
})

const totalCount = computed(() => total.value)
const totalAmount = computed(() => {
  const sum = invoices.value.reduce((total, item) => total + (Number(item.amount) || 0), 0)
  return sum ? sum.toFixed(2) : '0.00'
})
const approvedCount = computed(() => invoices.value.filter((item) => item.approval_status === 'approved').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedInvoices = computed(() => invoices.value)

const resetForm = () => {
  form.value = {
    invoice_no: '',
    contract: null,
    account: null,
    amount: null,
    tax_rate: null,
    invoice_type: 'normal',
    status: 'draft',
    approval_status: 'pending',
    issued_at: ''
  }
}

const contractLabel = (contract) => {
  if (!contract) return ''
  return contract.contract_no || contract.name || `合同${contract.id}`
}

const contractName = (contractId) => {
  const ct = contracts.value.find((item) => item.id === contractId)
  return ct ? contractLabel(ct) : (contractId || '-')
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
  return params
}

const fetchData = async () => {
  const res = await api.get('/invoices/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    invoices.value = res.data.results
    total.value = res.data.count
  } else {
    invoices.value = res.data
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

const saveInvoice = async () => {
  if (!form.value.contract) {
    error.value = '请选择关联合同'
    return
  }
  if (!form.value.amount) {
    error.value = '开票金额不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      contract: Number(form.value.contract),
      account: form.value.account ? Number(form.value.account) : null,
      amount: Number(form.value.amount),
      tax_rate: form.value.tax_rate === '' ? null : form.value.tax_rate,
      issued_at: form.value.issued_at || null
    }
    if (editingId.value) {
      await api.patch(`/invoices/${editingId.value}/`, payload)
      success.value = '开票申请已更新'
      editingId.value = null
    } else {
      await api.post('/invoices/', payload)
      success.value = '开票申请已保存'
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
    invoice_no: item.invoice_no || '',
    contract: item.contract != null ? Number(item.contract) : null,
    account: item.account != null ? Number(item.account) : null,
    amount: item.amount != null ? Number(item.amount) : null,
    tax_rate: item.tax_rate != null ? Number(item.tax_rate) : null,
    invoice_type: item.invoice_type || 'normal',
    status: item.status || 'draft',
    approval_status: item.approval_status || 'pending',
    issued_at: item.issued_at || ''
  }
}

const cancelEdit = () => {
  editingId.value = null
  resetForm()
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
  await fetchContracts()
  await fetchAccounts()
  await fetchData()
})

watch([statusFilter, approvalFilter, ordering], () => {
  applyFilters()
})
</script>
