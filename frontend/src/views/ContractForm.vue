<template>
  <div class="opportunity-detail contract-detail">
    <div class="detail-header">
      <div class="detail-title-wrap">
        <button class="back-button" type="button" @click="goBack" aria-label="返回">←</button>
        <div>
          <div class="detail-title">{{ headerTitle }}</div>
          <div class="detail-meta">
            <span>状态：{{ statusLabel(form.status) }}</span>
            <span>审批：{{ approvalLabel(form.approval_status) }}</span>
            <span>甲方：{{ selectedAccountLabel || '-' }}</span>
            <span>金额：{{ formatMoney(form.amount) }}</span>
            <span>当前产值：{{ formatMoney(form.current_output) }}</span>
            <span>应收款：{{ receivableAmount || '-' }}</span>
            <span>签署日期：{{ form.signed_at || '-' }}</span>
          </div>
        </div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : (isEdit ? '保存修改' : '保存合同') }}
        </button>
        <button class="button secondary" @click="cancel">取消</button>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="card">
      <div class="section-title">合同信息</div>
      <div class="form-grid">
        <div>
          <label>合同编号</label>
          <input v-model="form.contract_no" placeholder="合同编号" />
        </div>
        <div>
          <label>合同名称</label>
          <input v-model="form.name" placeholder="合同名称" />
        </div>
        <div>
          <label>关联甲方</label>
          <div class="account-picker">
            <div class="account-search">
              <input
                v-model="accountQuery"
                placeholder="输入甲方全称/简称，自动搜索"
              />
              <button class="button secondary" type="button" @click="triggerSearch">搜索</button>
              <button v-if="form.account" class="button secondary" type="button" @click="clearAccount">
                清除
              </button>
            </div>
            <div v-if="searchHint" class="account-hint">{{ searchHint }}</div>
            <div v-if="!accountQuery" class="account-hint">最近甲方</div>
            <div v-if="selectedAccountLabel" class="account-selected">
              已选择：{{ selectedAccountLabel }}
            </div>
            <div class="account-results">
              <div v-if="accountLoading" style="color: #888;">加载中...</div>
              <div v-else-if="!accountOptions.length" style="color: #888;">暂无匹配客户</div>
              <button
                v-for="acc in accountOptions"
                :key="acc.id"
                class="account-option"
                type="button"
                @click="selectAccount(acc)"
              >
                {{ acc.full_name }}{{ acc.short_name ? `（${acc.short_name}）` : '' }}
              </button>
            </div>
            <div v-if="showQuickCreate" class="account-create">
              <div class="section-title">新增甲方</div>
              <div class="form-grid">
                <div>
                  <label>甲方全称</label>
                  <input v-model="accountCreate.full_name" placeholder="甲方全称" />
                </div>
                <div>
                  <label>甲方简称</label>
                  <input v-model="accountCreate.short_name" placeholder="甲方简称" />
                </div>
              </div>
              <div style="margin-top: 10px;">
                <button class="button" type="button" :disabled="accountCreateSaving" @click="createAccount">
                  {{ accountCreateSaving ? '保存中...' : '保存甲方' }}
                </button>
                <span v-if="accountCreateError" style="margin-left: 10px; color: #c92a2a;">
                  {{ accountCreateError }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div>
          <label>乙方公司</label>
          <select v-model.number="form.vendor_company">
            <option :value="null">请选择乙方公司</option>
            <option v-for="opt in lookupOptions.vendor_company" :key="opt.id" :value="opt.id">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div>
          <label>关联商机</label>
          <select v-model.number="form.opportunity">
            <option :value="null">未关联</option>
            <option v-for="opp in opportunities" :key="opp.id" :value="opp.id">
              {{ opp.opportunity_name }}
            </option>
          </select>
        </div>
        <div>
          <label>所属区域</label>
          <select v-model.number="form.region">
            <option :value="null">默认所属区域</option>
            <option v-for="region in regions" :key="region.id" :value="region.id">
              {{ region.name || region.code || `ID ${region.id}` }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-title">金额与状态</div>
      <div class="form-grid">
        <div>
          <label>合同金额</label>
          <input v-model.number="form.amount" type="number" />
        </div>
        <div>
          <label>当前产值</label>
          <input v-model.number="form.current_output" type="number" />
        </div>
        <div>
          <label>应收款</label>
          <input :value="receivableAmount" type="number" disabled />
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

    <div class="card">
      <div class="section-title">附件</div>
      <div v-if="!isEdit" style="color: #888;">保存合同后可上传附件</div>
      <div v-else>
        <div class="form-grid">
          <div>
            <label>选择附件</label>
            <input type="file" @change="onFileChange" />
          </div>
          <div>
            <label>附件备注</label>
            <input v-model="attachmentForm.description" placeholder="可选" />
          </div>
        </div>
        <div style="margin-top: 10px;">
          <button class="button" :disabled="uploading || !attachmentForm.file" @click="uploadAttachment">
            {{ uploading ? '上传中...' : '上传附件' }}
          </button>
          <span v-if="uploadError" style="margin-left: 10px; color: #c92a2a;">{{ uploadError }}</span>
        </div>
        <div style="margin-top: 12px;">
          <table class="table" v-if="attachments.length">
            <thead>
              <tr>
                <th>文件</th>
                <th>备注</th>
                <th>上传人</th>
                <th>时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="file in attachments" :key="file.id">
                <td>
                  <a
                    v-if="isTextAttachment(file)"
                    class="link-button"
                    :href="fileUrl(file)"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ fileName(file) }}
                  </a>
                  <span v-else>{{ fileName(file) }}</span>
                </td>
                <td>{{ file.description || '-' }}</td>
                <td>{{ file.owner_name || file.owner || '-' }}</td>
                <td>{{ file.created_at || '-' }}</td>
                <td>
                  <a class="link-button" :href="file.file_url || file.file" target="_blank" rel="noopener">下载</a>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else style="color: #888;">暂无附件</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-title">回款明细</div>
      <div v-if="!isEdit" style="color: #888;">保存合同后可录入回款明细</div>
      <div v-else>
        <div class="form-grid">
          <div>
            <label>回款金额</label>
            <input v-model.number="paymentForm.amount" type="number" />
          </div>
          <div>
            <label>回款时间</label>
            <input v-model="paymentForm.paid_at" type="date" />
          </div>
        </div>
        <div style="margin-top: 10px;">
          <button class="button" :disabled="paymentSaving || !paymentForm.amount" @click="savePayment">
            {{ paymentSaving ? '保存中...' : (editingPaymentId ? '保存修改' : '保存回款') }}
          </button>
          <button
            v-if="editingPaymentId"
            class="button secondary"
            style="margin-left: 8px;"
            @click="cancelEditPayment"
          >
            取消编辑
          </button>
          <span v-if="paymentError" style="margin-left: 10px; color: #c92a2a;">{{ paymentError }}</span>
          <span v-if="paymentSuccess" style="margin-left: 10px; color: #2b8a3e;">{{ paymentSuccess }}</span>
        </div>
        <div style="margin-top: 12px;">
          <table class="table" v-if="payments.length">
            <thead>
              <tr>
                <th>回款金额</th>
                <th>回款时间</th>
                <th>状态</th>
                <th>上传人</th>
                <th>时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in payments" :key="item.id">
                <td>{{ item.amount }}</td>
                <td>{{ item.paid_at || '-' }}</td>
                <td>{{ paymentStatusLabel(item.status) }}</td>
                <td>{{ item.owner_name || item.owner || '-' }}</td>
                <td>{{ item.created_at || '-' }}</td>
                <td>
                  <button class="button secondary" @click="startEditPayment(item)">编辑</button>
                  <button class="button secondary" @click="deletePayment(item.id)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else style="color: #888;">暂无回款记录</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()
const saving = ref(false)
const error = ref('')
const success = ref('')
const opportunities = ref([])
const regions = ref([])
const attachments = ref([])
const attachmentForm = ref({
  file: null,
  description: ''
})
const uploading = ref(false)
const uploadError = ref('')
const payments = ref([])
const paymentForm = ref({
  amount: null,
  paid_at: ''
})
const editingPaymentId = ref(null)
const paymentSaving = ref(false)
const paymentError = ref('')
const paymentSuccess = ref('')
const paidTotal = ref(0)
const lookupOptions = ref({
  vendor_company: []
})
const accountOptions = ref([])
const accountQuery = ref('')
const accountLoading = ref(false)
const selectedAccount = ref(null)
const accountCreate = ref({
  full_name: '',
  short_name: ''
})
const accountCreateSaving = ref(false)
const accountCreateError = ref('')

const form = ref({
  contract_no: '',
  name: '',
  account: null,
  vendor_company: null,
  opportunity: null,
  region: null,
  amount: null,
  current_output: null,
  final_settlement_amount: null,
  status: 'draft',
  approval_status: 'pending',
  signed_at: '',
  start_date: '',
  end_date: ''
})

const isEdit = computed(() => Boolean(route.params.id))
const headerTitle = computed(() => {
  if (!isEdit.value) return '新建合同'
  return form.value.name || form.value.contract_no || '合同详情'
})

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

const formatMoney = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
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

const fetchOpportunities = async () => {
  const res = await api.get('/opportunities/', { params: { page: 1, page_size: 1000 } })
  opportunities.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

let searchTimer = null

const loadAccounts = async (query) => {
  accountLoading.value = true
  try {
    const res = await api.get('/accounts/', {
      params: {
        page: 1,
        page_size: 20,
        ordering: '-created_at',
        search: query || ''
      }
    })
    accountOptions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } finally {
    accountLoading.value = false
  }
}

const fetchAccountById = async (id) => {
  try {
    const res = await api.get(`/accounts/${id}/`)
    return res.data
  } catch (err) {
    return null
  }
}

const triggerSearch = () => {
  const query = accountQuery.value.trim()
  if (!query) {
    loadAccounts('')
    return
  }
  if (query.length < 2) {
    return
  }
  loadAccounts(query)
}

const searchHint = computed(() => {
  const query = accountQuery.value.trim()
  if (!query) return ''
  if (query.length < 2) return '请输入至少 2 个字'
  return ''
})

const selectAccount = (acc) => {
  form.value.account = acc.id
  selectedAccount.value = acc
  accountQuery.value = acc.full_name || acc.short_name || ''
}

const clearAccount = () => {
  form.value.account = null
  selectedAccount.value = null
  accountQuery.value = ''
}

const selectedAccountLabel = computed(() => {
  if (!form.value.account) return ''
  const acc = selectedAccount.value || accountOptions.value.find((item) => item.id === form.value.account)
  if (!acc) return `ID ${form.value.account}`
  return `${acc.full_name}${acc.short_name ? `（${acc.short_name}）` : ''}`
})

const showQuickCreate = computed(() => {
  const query = accountQuery.value.trim()
  return query && query.length >= 2 && !accountOptions.value.length
})

const paymentStatusLabel = (value) => {
  const map = {
    planned: '计划中',
    partial: '部分回款',
    paid: '已回款'
  }
  return map[value] || value || '-'
}

const fileName = (file) => file.original_name || file.file || '-'

const fileUrl = (file) => file.file_url || file.file || '#'

const isTextAttachment = (file) => {
  const name = fileName(file).toLowerCase()
  const ext = name.includes('.') ? name.split('.').pop() : ''
  return [
    'txt', 'md', 'log', 'csv', 'json', 'xml', 'yaml', 'yml', 'html', 'htm',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'
  ].includes(ext)
}

const createAccount = async () => {
  if (!accountCreate.value.full_name) {
    accountCreateError.value = '甲方全称不能为空'
    return
  }
  accountCreateError.value = ''
  accountCreateSaving.value = true
  try {
    const payload = {
      full_name: accountCreate.value.full_name,
      short_name: accountCreate.value.short_name || ''
    }
    const res = await api.post('/accounts/', payload)
    const created = res.data
    selectedAccount.value = created
    form.value.account = created.id
    accountOptions.value = [created, ...accountOptions.value]
    accountQuery.value = created.full_name
    accountCreate.value = { full_name: '', short_name: '' }
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      accountCreateError.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      accountCreateError.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    accountCreateSaving.value = false
  }
}

const loadContract = async () => {
  if (!isEdit.value) return
  try {
    const res = await api.get(`/contracts/${route.params.id}/`)
    const data = res.data
    form.value = {
      contract_no: data.contract_no || '',
      name: data.name || '',
      account: data.account != null ? Number(data.account) : null,
      vendor_company: data.vendor_company != null ? Number(data.vendor_company) : null,
      opportunity: data.opportunity != null ? Number(data.opportunity) : null,
      region: data.region != null ? Number(data.region) : null,
      amount: data.amount != null ? Number(data.amount) : null,
      current_output: data.current_output != null ? Number(data.current_output) : null,
      final_settlement_amount: data.final_settlement_amount != null ? Number(data.final_settlement_amount) : null,
      status: data.status || 'draft',
      approval_status: data.approval_status || 'pending',
      signed_at: data.signed_at || '',
      start_date: data.start_date || '',
      end_date: data.end_date || ''
    }
    paidTotal.value = Number(data.paid_total || 0)
    if (form.value.account) {
      const acc = await fetchAccountById(form.value.account)
      if (acc) {
        selectedAccount.value = acc
        accountQuery.value = acc.full_name
        accountOptions.value = [acc, ...accountOptions.value.filter((item) => item.id !== acc.id)]
      }
    }
  } catch (err) {
    error.value = '加载合同失败，请确认该合同存在且有权限访问'
  }
}

const fetchAttachments = async () => {
  if (!isEdit.value) return
  const res = await api.get('/contract-attachments/', {
    params: { contract: route.params.id, ordering: '-created_at', page: 1, page_size: 50 }
  })
  attachments.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const onFileChange = (event) => {
  const file = event.target.files && event.target.files[0]
  attachmentForm.value.file = file || null
  uploadError.value = ''
}

const uploadAttachment = async () => {
  if (!attachmentForm.value.file || !isEdit.value) return
  uploading.value = true
  uploadError.value = ''
  try {
    const formData = new FormData()
    formData.append('contract', String(route.params.id))
    formData.append('file', attachmentForm.value.file)
    if (attachmentForm.value.description) {
      formData.append('description', attachmentForm.value.description)
    }
    await api.post('/contract-attachments/', formData)
    attachmentForm.value = { file: null, description: '' }
    await fetchAttachments()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      uploadError.value = messages || '上传失败，请检查后端服务'
    } else {
      uploadError.value = '上传失败，请检查后端服务'
    }
  } finally {
    uploading.value = false
  }
}

const fetchPayments = async () => {
  if (!isEdit.value) return
  const res = await api.get('/payments/', {
    params: { contract: route.params.id, ordering: '-paid_at', page: 1, page_size: 50 }
  })
  payments.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  paidTotal.value = payments.value.reduce((sum, item) => sum + (Number(item.amount) || 0), 0)
}

const startEditPayment = (item) => {
  editingPaymentId.value = item.id
  paymentForm.value = {
    amount: item.amount != null ? Number(item.amount) : null,
    paid_at: item.paid_at || ''
  }
  paymentError.value = ''
  paymentSuccess.value = ''
}

const cancelEditPayment = () => {
  editingPaymentId.value = null
  paymentForm.value = { amount: null, paid_at: '' }
  paymentError.value = ''
  paymentSuccess.value = ''
}

const savePayment = async () => {
  if (!paymentForm.value.amount) {
    paymentError.value = '回款金额不能为空'
    return
  }
  paymentError.value = ''
  paymentSuccess.value = ''
  paymentSaving.value = true
  try {
    if (editingPaymentId.value) {
      const payload = {
        amount: Number(paymentForm.value.amount),
        paid_at: paymentForm.value.paid_at || null
      }
      await api.patch(`/payments/${editingPaymentId.value}/`, payload)
      paymentSuccess.value = '回款已更新'
      editingPaymentId.value = null
      paymentForm.value = { amount: null, paid_at: '' }
    } else {
      const payload = {
        contract: Number(route.params.id),
        amount: Number(paymentForm.value.amount),
        paid_at: paymentForm.value.paid_at || null,
        status: 'paid'
      }
      await api.post('/payments/', payload)
      paymentForm.value = { amount: null, paid_at: '' }
      paymentSuccess.value = '回款已保存'
    }
    await fetchPayments()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      paymentError.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      paymentError.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    paymentSaving.value = false
  }
}

const deletePayment = async (id) => {
  if (!confirm('确认删除该回款记录？')) return
  paymentError.value = ''
  paymentSuccess.value = ''
  try {
    await api.delete(`/payments/${id}/`)
    paymentSuccess.value = '回款已删除'
    if (editingPaymentId.value === id) {
      cancelEditPayment()
    }
    await fetchPayments()
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      paymentError.value = '无删除权限'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        paymentError.value = detail.detail || '删除失败，请检查权限或后端服务'
      } else {
        paymentError.value = '删除失败，请检查权限或后端服务'
      }
    }
  }
}

const normalizePayload = () => ({
  contract_no: form.value.contract_no || '',
  name: form.value.name || '',
  account: form.value.account ? Number(form.value.account) : null,
  vendor_company: form.value.vendor_company ? Number(form.value.vendor_company) : null,
  opportunity: form.value.opportunity ? Number(form.value.opportunity) : null,
  region: form.value.region ? Number(form.value.region) : null,
  amount: form.value.amount === '' ? null : form.value.amount,
  current_output: form.value.current_output === '' ? null : form.value.current_output,
  final_settlement_amount: form.value.final_settlement_amount === '' ? null : form.value.final_settlement_amount,
  status: form.value.status,
  approval_status: form.value.approval_status,
  signed_at: form.value.signed_at || null,
  start_date: form.value.start_date || null,
  end_date: form.value.end_date || null
})

const save = async () => {
  if (!form.value.account) {
    error.value = '请选择关联甲方'
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
    const payload = normalizePayload()
    if (isEdit.value) {
      await api.patch(`/contracts/${route.params.id}/`, payload)
      success.value = '合同已更新'
    } else {
      const res = await api.post('/contracts/', payload)
      router.push({ path: `/contracts/${res.data.id}`, query: { saved: '1' } })
    }
  } catch (err) {
    const status = err.response?.status
    if (status === 401) {
      error.value = '登录已过期，请重新登录'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        error.value = messages || '保存失败，请检查必填项或后端服务'
      } else {
        error.value = '保存失败，请检查必填项或后端服务'
      }
    }
  } finally {
    saving.value = false
  }
}

const cancel = () => {
  router.push('/contracts')
}

const goBack = () => {
  router.back()
}

onMounted(async () => {
  await fetchLookups()
  await fetchOpportunities()
  await fetchRegions()
  await loadAccounts('')
  await loadContract()
  await fetchAttachments()
  await fetchPayments()
  if (route.query.saved) {
    success.value = '合同已保存'
  }
})

watch(accountQuery, (value) => {
  const query = value.trim()
  if (!query) {
    accountCreate.value.full_name = ''
    if (searchTimer) clearTimeout(searchTimer)
    loadAccounts('')
    return
  }
  if (!accountCreate.value.full_name) {
    accountCreate.value.full_name = value
  }
  if (query.length < 2) {
    return
  }
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadAccounts(query)
  }, 300)
})
</script>

<style scoped>
.contract-detail {
  font-size: 13px;
}
</style>
const receivableAmount = computed(() => {
  const base = form.value.current_output != null ? Number(form.value.current_output) : Number(form.value.amount)
  if (Number.isNaN(base)) return ''
  const total = Number(paidTotal.value) || 0
  const value = base - total
  return Number.isFinite(value) ? value.toFixed(2) : ''
})
