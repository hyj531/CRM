<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ isNew ? '新建开票' : '开票详情' }}</h2>
        <div class="page-subtitle">开票登记与审批管理</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="saveInvoice">
          {{ saving ? '保存中...' : '保存开票' }}
        </button>
        <button
          v-if="showInvoiceSubmitApproval"
          class="button secondary"
          :disabled="submittingApproval"
          @click="submitApproval"
        >
          {{ submittingApproval ? '提交中...' : '提交审批' }}
        </button>
        <button class="button secondary" @click="goBack">返回列表</button>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="card">
      <div class="section-title">审批进度</div>
      <div v-if="approvalProgressLoading" style="color: #888;">审批进度加载中...</div>
      <div v-else-if="approvalProgressError" style="color: #c92a2a;">{{ approvalProgressError }}</div>
      <div v-else-if="!approvalProgress?.has_instance" style="color: #888;">暂无审批记录</div>
      <div v-else class="form-grid">
        <div>
          <label>流程状态</label>
          <input :value="approvalInstanceStatusLabel(approvalProgress.instance_status)" disabled />
        </div>
        <div>
          <label>当前步骤</label>
          <input :value="approvalProgress.current_step_name || '-'" disabled />
        </div>
        <div>
          <label>当前审批人</label>
          <input :value="approvalProgressApprovers || '-'" disabled />
        </div>
        <div>
          <label>最近动作</label>
          <input :value="approvalProgressLatestActionLabel" disabled />
        </div>
      </div>
      <div v-if="approvalProgress?.has_instance" style="margin-top: 10px;">
        <button class="button secondary" @click="openApprovalDetail">查看审批详情</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title">开票信息</div>
      <div class="invoice-subsection-title">业务信息</div>
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
          <label>关联客户</label>
          <input :value="selectedAccountLabel" disabled />
        </div>
        <div>
          <label>所属区域</label>
          <select v-model.number="form.region">
            <option :value="null">请选择所属区域</option>
            <option v-for="r in regions" :key="r.id" :value="r.id">
              {{ r.name || r.code || `ID ${r.id}` }}
            </option>
          </select>
        </div>
        <div>
          <label>负责人</label>
          <select v-model.number="form.owner">
            <option :value="null">请选择负责人</option>
            <option v-for="u in users" :key="u.id" :value="u.id">
              {{ u.username || u.email || `ID ${u.id}` }}
            </option>
          </select>
        </div>
        <div>
          <label>开票编号</label>
          <input v-model="form.invoice_no" />
        </div>
      </div>

      <div class="invoice-subsection-title">开票抬头信息</div>
      <div class="form-grid">
        <div>
          <label>名称</label>
          <input v-model="form.billing_name" placeholder="名称" />
        </div>
        <div>
          <label>纳税人识别号 *</label>
          <input v-model="form.taxpayer_no" placeholder="纳税人识别号" />
        </div>
        <div>
          <label>地址 *</label>
          <input v-model="form.billing_address" placeholder="地址" />
        </div>
        <div>
          <label>电话 *</label>
          <input v-model="form.billing_phone" placeholder="电话" />
        </div>
        <div>
          <label>开户银行 *</label>
          <input v-model="form.billing_bank_name" placeholder="开户银行" />
        </div>
        <div>
          <label>银行账号 *</label>
          <input v-model="form.billing_bank_account" placeholder="银行账号" />
        </div>
      </div>

      <div class="invoice-subsection-title">金额与状态</div>
      <div class="form-grid">
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
          <label>开票状态</label>
          <select v-model="form.status">
            <option value="draft">草稿</option>
            <option value="issued">已开票</option>
            <option value="paid">已回款</option>
            <option value="void">已作废</option>
          </select>
        </div>
        <div>
          <label>审批状态</label>
          <input
            v-if="invoiceApprovalEnabled"
            :value="approvalLabel(form.approval_status)"
            disabled
          />
          <select v-else v-model="form.approval_status">
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const contracts = ref([])
const accounts = ref([])
const regions = ref([])
const users = ref([])
const contractSearch = ref('')
const showContractDropdown = ref(false)
const error = ref('')
const success = ref('')
const saving = ref(false)
const submittingApproval = ref(false)
const approvalProgressLoading = ref(false)
const approvalProgressError = ref('')
const approvalProgress = ref(null)
const billingAutoFillAccountId = ref(null)

const form = ref({
  invoice_no: '',
  contract: null,
  account: null,
  billing_name: '',
  taxpayer_no: '',
  billing_address: '',
  billing_phone: '',
  billing_bank_name: '',
  billing_bank_account: '',
  region: null,
  owner: null,
  amount: null,
  tax_rate: null,
  invoice_type: 'normal',
  status: 'draft',
  approval_status: 'pending',
  issued_at: ''
})

const invoiceId = computed(() => {
  const raw = route.params.id
  if (!raw) return null
  const id = Number(raw)
  return Number.isFinite(id) ? id : null
})

const isNew = computed(() => !invoiceId.value)
const invoiceApprovalEnabled = computed(() => auth.user?.approval_switches?.invoice !== false)
const showInvoiceSubmitApproval = computed(() => (
  !isNew.value && invoiceApprovalEnabled.value
))
const approvalProgressApprovers = computed(() => {
  const items = Array.isArray(approvalProgress.value?.pending_approvers) ? approvalProgress.value.pending_approvers : []
  if (!items.length) return ''
  return items.map((item) => item.username).filter(Boolean).join('、')
})
const approvalProgressLatestActionLabel = computed(() => {
  const action = approvalProgress.value?.latest_action
  if (!action) return '-'
  const actor = action.actor_name || '-'
  const when = formatDateTime(action.created_at)
  return `${approvalActionLabel(action.action)} · ${actor} · ${when}`
})

const approvalLabel = (value) => {
  const map = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回'
  }
  return map[value] || value || '-'
}

const approvalInstanceStatusLabel = (value) => {
  const map = {
    pending: '审批中',
    approved: '已通过',
    rejected: '已驳回',
    withdrawn: '已撤回'
  }
  return map[value] || '-'
}

const approvalActionLabel = (value) => {
  const map = {
    submitted: '发起审批',
    task_activated: '任务激活',
    approved: '审批通过',
    rejected: '审批驳回',
    withdrawn: '审批撤回',
    completed: '流程完成',
    todo_create: '待办创建',
    todo_complete: '待办关闭',
    todo_failed: '待办失败'
  }
  return map[value] || value || '-'
}

const formatDateTime = (value) => {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

const contractLabel = (contract) => {
  if (!contract) return ''
  const name = contract.name || contract.contract_no || `合同${contract.id}`
  const accountId = contract.account
  const acc = accounts.value.find((item) => item.id === accountId)
  const accountName = acc ? `${acc.full_name || ''}${acc.short_name ? `（${acc.short_name}）` : ''}` : ''
  return accountName ? `${name}（${accountName}）` : name
}

const selectedAccountLabel = computed(() => {
  if (!form.value.account) return '-'
  const acc = accounts.value.find((item) => item.id === form.value.account)
  if (!acc) return `ID ${form.value.account}`
  return `${acc.full_name || ''}${acc.short_name ? `（${acc.short_name}）` : ''}`
})

const filteredContracts = computed(() => {
  const keyword = contractSearch.value.trim().toLowerCase()
  if (!keyword) return contracts.value
  return contracts.value.filter((ct) => {
    const contractText = `${ct.name || ''} ${ct.contract_no || ''}`.toLowerCase()
    const acc = accounts.value.find((item) => item.id === ct.account)
    const accountText = acc ? `${acc.full_name || ''} ${acc.short_name || ''}`.toLowerCase() : ''
    return contractText.includes(keyword) || accountText.includes(keyword)
  })
})

const applyDefaults = () => {
  if (form.value.region == null && auth.user?.region != null) {
    form.value.region = Number(auth.user.region)
  }
  if (form.value.owner == null && auth.user?.id != null) {
    form.value.owner = Number(auth.user.id)
  }
}

const fillBillingInfoFromAccount = (accountId, force = false) => {
  if (!accountId) return
  const acc = accounts.value.find((item) => item.id === Number(accountId))
  if (!acc) return
  if (force || !form.value.billing_name) form.value.billing_name = acc.full_name || ''
  if (force || !form.value.taxpayer_no) form.value.taxpayer_no = acc.credit_code || ''
  if (force || !form.value.billing_address) form.value.billing_address = acc.address || ''
  if (force || !form.value.billing_phone) form.value.billing_phone = acc.phone || ''
}

const fillBillingInfoFromLastInvoice = async (accountId) => {
  if (!isNew.value || !accountId) return
  const accountNum = Number(accountId)
  const force = billingAutoFillAccountId.value !== accountNum

  try {
    const res = await api.get('/invoices/', {
      params: {
        account: accountNum,
        page: 1,
        page_size: 1,
        ordering: '-created_at'
      }
    })
    const list = Array.isArray(res.data?.results) ? res.data.results : (Array.isArray(res.data) ? res.data : [])
    const latest = list[0]
    if (latest) {
      if (force || !form.value.billing_name) form.value.billing_name = latest.billing_name || ''
      if (force || !form.value.taxpayer_no) form.value.taxpayer_no = latest.taxpayer_no || ''
      if (force || !form.value.billing_address) form.value.billing_address = latest.billing_address || ''
      if (force || !form.value.billing_phone) form.value.billing_phone = latest.billing_phone || ''
      if (force || !form.value.billing_bank_name) form.value.billing_bank_name = latest.billing_bank_name || ''
      if (force || !form.value.billing_bank_account) form.value.billing_bank_account = latest.billing_bank_account || ''
      const hasHistory = Boolean(
        latest.billing_name || latest.taxpayer_no || latest.billing_address
        || latest.billing_phone || latest.billing_bank_name || latest.billing_bank_account
      )
      if (hasHistory) {
        billingAutoFillAccountId.value = accountNum
        return
      }
    }
  } catch (err) {
    // ignore autofill errors to avoid blocking invoice creation
  }

  fillBillingInfoFromAccount(accountNum, force)
  billingAutoFillAccountId.value = accountNum
}

const selectContract = async (ct) => {
  form.value.contract = ct.id
  form.value.account = ct.account != null ? Number(ct.account) : null
  form.value.region = ct.region != null ? Number(ct.region) : form.value.region
  form.value.owner = ct.owner != null ? Number(ct.owner) : form.value.owner
  await fillBillingInfoFromLastInvoice(form.value.account)
  contractSearch.value = contractLabel(ct)
  showContractDropdown.value = false
}

const hideContractDropdown = () => {
  setTimeout(() => {
    showContractDropdown.value = false
  }, 120)
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

const fetchInvoice = async () => {
  if (!invoiceId.value) return
  const res = await api.get(`/invoices/${invoiceId.value}/`)
  const data = res.data || {}
  form.value = {
    invoice_no: data.invoice_no || '',
    contract: data.contract != null ? Number(data.contract) : null,
    account: data.account != null ? Number(data.account) : null,
    billing_name: data.billing_name || '',
    taxpayer_no: data.taxpayer_no || '',
    billing_address: data.billing_address || '',
    billing_phone: data.billing_phone || '',
    billing_bank_name: data.billing_bank_name || '',
    billing_bank_account: data.billing_bank_account || '',
    region: data.region != null ? Number(data.region) : null,
    owner: data.owner != null ? Number(data.owner) : null,
    amount: data.amount != null ? Number(data.amount) : null,
    tax_rate: data.tax_rate != null ? Number(data.tax_rate) : null,
    invoice_type: data.invoice_type || 'normal',
    status: data.status || 'draft',
    approval_status: data.approval_status || 'pending',
    issued_at: data.issued_at || ''
  }
  const ct = contracts.value.find((item) => item.id === form.value.contract)
  contractSearch.value = ct ? contractLabel(ct) : ''
  if (!form.value.account && ct?.account != null) {
    form.value.account = Number(ct.account)
  }
  applyDefaults()
}

const fetchApprovalProgress = async () => {
  if (!invoiceId.value) {
    approvalProgress.value = null
    approvalProgressError.value = ''
    return
  }
  approvalProgressLoading.value = true
  approvalProgressError.value = ''
  try {
    const res = await api.get(`/invoices/${invoiceId.value}/approval_progress/`)
    approvalProgress.value = res.data || null
  } catch (err) {
    approvalProgress.value = null
    approvalProgressError.value = '审批进度加载失败'
  } finally {
    approvalProgressLoading.value = false
  }
}

const openApprovalDetail = () => {
  if (!approvalProgress.value?.has_instance || !approvalProgress.value?.instance_id) return
  router.push({
    name: 'approval-instance',
    params: { id: String(approvalProgress.value.instance_id) },
    query: { from: `invoice:${invoiceId.value}` }
  })
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
  if (!form.value.region) {
    error.value = '请选择所属区域'
    return
  }
  if (!form.value.owner) {
    error.value = '请选择负责人'
    return
  }
  if (!form.value.taxpayer_no?.trim()) {
    error.value = '纳税人识别号不能为空'
    return
  }
  if (!form.value.billing_address?.trim()) {
    error.value = '地址不能为空'
    return
  }
  if (!form.value.billing_phone?.trim()) {
    error.value = '电话不能为空'
    return
  }
  if (!form.value.billing_bank_name?.trim()) {
    error.value = '开户银行不能为空'
    return
  }
  if (!form.value.billing_bank_account?.trim()) {
    error.value = '银行账号不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      invoice_no: form.value.invoice_no || '',
      contract: Number(form.value.contract),
      account: form.value.account ? Number(form.value.account) : null,
      billing_name: form.value.billing_name || '',
      taxpayer_no: form.value.taxpayer_no || '',
      billing_address: form.value.billing_address || '',
      billing_phone: form.value.billing_phone || '',
      billing_bank_name: form.value.billing_bank_name || '',
      billing_bank_account: form.value.billing_bank_account || '',
      amount: Number(form.value.amount),
      tax_rate: form.value.tax_rate === '' ? null : form.value.tax_rate,
      invoice_type: form.value.invoice_type,
      status: form.value.status || 'draft',
      region: Number(form.value.region),
      owner: Number(form.value.owner),
      ...(invoiceApprovalEnabled.value ? {} : { approval_status: form.value.approval_status }),
      issued_at: form.value.issued_at || null
    }
    if (isNew.value) {
      await api.post('/invoices/', payload)
      success.value = '开票已保存'
      router.push('/invoices')
    } else {
      await api.patch(`/invoices/${invoiceId.value}/`, payload)
      success.value = '开票已更新'
    }
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

const submitApproval = async () => {
  if (!showInvoiceSubmitApproval.value || !invoiceId.value) return
  error.value = ''
  success.value = ''
  submittingApproval.value = true
  try {
    await api.post(`/invoices/${invoiceId.value}/submit_approval/`)
    success.value = '已提交审批'
    await fetchInvoice()
    await fetchApprovalProgress()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || '提交审批失败，请检查权限或流程配置'
    } else {
      error.value = '提交审批失败，请检查权限或流程配置'
    }
  } finally {
    submittingApproval.value = false
  }
}

const goBack = () => {
  router.push('/invoices')
}

onMounted(async () => {
  await auth.ensureMeFresh(60000)
  await fetchAccounts()
  await fetchContracts()
  await fetchRegions()
  await fetchUsers()
  if (!isNew.value) {
    await fetchInvoice()
    await fetchApprovalProgress()
  } else {
    applyDefaults()
  }
})

watch(contractSearch, (val) => {
  if (!val) {
    form.value.contract = null
    form.value.account = null
    form.value.region = null
    form.value.owner = null
    billingAutoFillAccountId.value = null
    applyDefaults()
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

.invoice-subsection-title {
  margin: 14px 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
</style>
