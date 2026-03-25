<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">合同</h2>
        <div class="page-subtitle">合同创建、审批与回款衔接</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="saveContract">
          {{ saving ? '保存中...' : (editingId ? '保存修改' : '保存合同') }}
        </button>
        <button v-if="editingId" class="button secondary" @click="cancelEdit">取消编辑</button>
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
        <div class="section-title">{{ editingId ? '编辑合同' : '新建合同' }}</div>
        <div class="form-grid">
          <div>
            <label>合同编号</label>
            <input v-model="form.contract_no" />
          </div>
          <div>
            <label>合同名称</label>
            <input v-model="form.name" />
          </div>
          <div>
            <label>关联客户</label>
            <select v-model.number="form.account">
              <option :value="null">请选择客户</option>
              <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                {{ acc.full_name }}{{ acc.short_name ? `（${acc.short_name}）` : '' }}
              </option>
            </select>
          </div>
          <div>
            <label>关联商机</label>
            <select v-model.number="form.opportunity">
              <option :value="null">未关联</option>
              <option v-for="opp in opportunities" :key="opp.id" :value="opp.id">{{ opp.opportunity_name }}</option>
            </select>
          </div>
          <div>
            <label>合同金额</label>
            <input v-model.number="form.amount" type="number" />
          </div>
          <div>
            <label>最终结算金额</label>
            <input v-model.number="form.final_settlement_amount" type="number" />
          </div>
          <div>
            <label>合同状态</label>
            <select v-model="form.status">
              <option value="draft">草稿</option>
              <option value="signed">已签署</option>
              <option value="active">履行中</option>
              <option value="closed">已关闭</option>
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
            <label>签署日期</label>
            <input v-model="form.signed_at" type="date" />
          </div>
          <div>
            <label>生效日期</label>
            <input v-model="form.start_date" type="date" />
          </div>
          <div>
            <label>到期日期</label>
            <input v-model="form.end_date" type="date" />
          </div>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 份合同</div>
          <div>审批与金额状态</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
          <div class="filter-left">
            <input v-model="search" placeholder="搜索合同编号/名称" @keyup.enter="applyFilters" />
            <select v-model="statusFilter">
              <option value="">全部状态</option>
              <option value="draft">草稿</option>
              <option value="signed">已签署</option>
              <option value="active">履行中</option>
              <option value="closed">已关闭</option>
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
              <option value="-signed_at">签署日期最新</option>
              <option value="-amount">合同金额高→低</option>
              <option value="amount">合同金额低→高</option>
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
                <th>合同编号</th>
                <th>合同名称</th>
                <th>客户</th>
                <th>商机</th>
                <th>金额</th>
                <th>最终结算</th>
                <th>状态</th>
                <th>审批</th>
              <th>签署日期</th>
              <th>生效</th>
              <th>到期</th>
              <th>负责人</th>
              <th>所属区域</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
              <tr v-for="item in pagedContracts" :key="item.id">
                <td>{{ item.contract_no || '-' }}</td>
                <td>{{ item.name || '-' }}</td>
                <td>{{ accountName(item.account) }}</td>
                <td>{{ opportunityName(item.opportunity) }}</td>
                <td>{{ item.amount }}</td>
                <td>{{ item.final_settlement_amount || '-' }}</td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ approvalLabel(item.approval_status) }}</td>
              <td>{{ item.signed_at || '-' }}</td>
              <td>{{ item.start_date || '-' }}</td>
              <td>{{ item.end_date || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || item.region || '-' }}</td>
              <td>
                <button v-if="canEdit" class="button secondary" @click="startEdit(item)">编辑</button>
                <button v-if="canDelete" class="button secondary" @click="deleteContract(item.id)">删除</button>
              </td>
            </tr>
              <tr v-if="!pagedContracts.length">
                <td colspan="14" style="color: #888;">暂无数据</td>
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

const contracts = ref([])
const total = ref(0)
const accounts = ref([])
const opportunities = ref([])
const error = ref('')
const success = ref('')
const saving = ref(false)
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contract?.delete))
const canEdit = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contract?.update))
const search = ref('')
const statusFilter = ref('')
const approvalFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-signed_at')
const editingId = ref(null)

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

const form = ref({
  contract_no: '',
  name: '',
  account: null,
  opportunity: null,
  amount: null,
  final_settlement_amount: null,
  status: 'draft',
  approval_status: 'pending',
  signed_at: '',
  start_date: '',
  end_date: ''
})

const totalCount = computed(() => total.value)
const totalAmount = computed(() => {
  const sum = contracts.value.reduce((total, item) => total + (Number(item.amount) || 0), 0)
  return sum ? sum.toFixed(2) : '0.00'
})
const approvedCount = computed(() => contracts.value.filter((item) => item.approval_status === 'approved').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedContracts = computed(() => contracts.value)

const resetForm = () => {
  form.value = {
    contract_no: '',
    name: '',
    account: null,
    opportunity: null,
    amount: null,
    final_settlement_amount: null,
    status: 'draft',
    approval_status: 'pending',
    signed_at: '',
    start_date: '',
    end_date: ''
  }
}

const accountName = (accountId) => {
  const acc = accounts.value.find((item) => item.id === accountId)
  if (!acc) return accountId || '-'
  return acc.full_name || acc.short_name || accountId || '-'
}

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
  if (approvalFilter.value) params.approval_status = approvalFilter.value
  return params
}

const fetchData = async () => {
  const res = await api.get('/contracts/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    contracts.value = res.data.results
    total.value = res.data.count
  } else {
    contracts.value = res.data
    total.value = res.data.length || 0
  }
}

const fetchAccounts = async () => {
  const res = await api.get('/accounts/', { params: { page: 1, page_size: 1000 } })
  accounts.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const fetchOpportunities = async () => {
  const res = await api.get('/opportunities/', { params: { page: 1, page_size: 1000 } })
  opportunities.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const saveContract = async () => {
  if (!form.value.account) {
    error.value = '请选择关联客户'
    return
  }
  if (!form.value.amount) {
    error.value = '合同金额不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      account: Number(form.value.account),
      opportunity: form.value.opportunity ? Number(form.value.opportunity) : null,
      amount: Number(form.value.amount),
      final_settlement_amount: form.value.final_settlement_amount === '' ? null : form.value.final_settlement_amount,
      signed_at: form.value.signed_at || null,
      start_date: form.value.start_date || null,
      end_date: form.value.end_date || null
    }
    if (editingId.value) {
      await api.patch(`/contracts/${editingId.value}/`, payload)
      success.value = '合同已更新'
      editingId.value = null
    } else {
      await api.post('/contracts/', payload)
      success.value = '合同已保存'
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
    contract_no: item.contract_no || '',
    name: item.name || '',
    account: item.account != null ? Number(item.account) : null,
    opportunity: item.opportunity != null ? Number(item.opportunity) : null,
    amount: item.amount != null ? Number(item.amount) : null,
    final_settlement_amount: item.final_settlement_amount != null ? Number(item.final_settlement_amount) : null,
    status: item.status || 'draft',
    approval_status: item.approval_status || 'pending',
    signed_at: item.signed_at || '',
    start_date: item.start_date || '',
    end_date: item.end_date || ''
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
  await fetchAccounts()
  await fetchOpportunities()
  await fetchData()
})

watch([statusFilter, approvalFilter, ordering], () => {
  applyFilters()
})
</script>
