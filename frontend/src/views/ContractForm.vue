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
            <span>创建人：{{ form.created_by_name || '-' }}</span>
            <span>创建日期：{{ formatDate(form.created_at) }}</span>
            <span>更新人：{{ form.updated_by_name || '-' }}</span>
            <span>更新日期：{{ formatDate(form.updated_at) }}</span>
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
                @focus="handleAccountFocus"
                @blur="handleAccountBlur"
              />
              <button class="button secondary" type="button" @click="triggerSearch">搜索</button>
              <button v-if="form.account" class="button secondary" type="button" @click="clearAccount">
                清除
              </button>
            </div>
            <div v-if="showAccountDropdown && searchHint" class="account-hint">{{ searchHint }}</div>
            <div v-if="selectedAccountLabel" class="account-selected">
              已选择：{{ selectedAccountLabel }}
            </div>
            <div v-if="showAccountDropdown" class="account-results">
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
        <div>
          <label>负责人</label>
          <select v-model.number="form.owner">
            <option :value="null">默认负责人</option>
            <option v-for="u in users" :key="u.id" :value="u.id">
              {{ u.username || u.email || `ID ${u.id}` }}
            </option>
          </select>
        </div>
        <div>
          <label>是否为框架合同</label>
          <select v-model="form.is_framework">
            <option :value="false">否</option>
            <option :value="true">是</option>
          </select>
        </div>
        <div>
          <label>所属框架合同</label>
          <select v-model.number="form.framework_contract" :disabled="form.is_framework">
            <option :value="null">不选择</option>
            <option v-for="item in frameworkContracts" :key="item.id" :value="item.id">
              {{ frameworkLabel(item) }}
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
        <div style="grid-column: 1 / -1;">
          <label>备注</label>
          <textarea v-model="form.remark" rows="3"></textarea>
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
          <div style="grid-column: 1 / -1;">
            <label>回款说明</label>
            <textarea v-model="paymentForm.note" rows="3"></textarea>
          </div>
          <div>
            <label>所属区域</label>
            <select v-model.number="paymentForm.region">
              <option :value="null">请选择所属区域</option>
              <option v-for="r in regions" :key="r.id" :value="r.id">
                {{ r.name || r.code || `ID ${r.id}` }}
              </option>
            </select>
          </div>
          <div>
            <label>负责人</label>
            <select v-model.number="paymentForm.owner">
              <option :value="null">请选择负责人</option>
              <option v-for="u in users" :key="u.id" :value="u.id">
                {{ u.username || u.email || `ID ${u.id}` }}
              </option>
            </select>
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
              <th>所属区域</th>
              <th>负责人</th>
              <th>录入人</th>
              <th>回款说明</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
              <tr v-for="item in payments" :key="item.id">
                <td>{{ item.amount }}</td>
                <td>{{ item.paid_at || '-' }}</td>
                <td>{{ paymentStatusLabel(item.status) }}</td>
                <td>{{ item.region_name || item.region || '-' }}</td>
                <td>{{ item.owner_name || item.owner || '-' }}</td>
                <td>{{ item.created_by_name || item.created_by || '-' }}</td>
                <td>{{ item.note || '-' }}</td>
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

    <div v-if="isEdit && form.is_framework" class="card">
      <div class="section-title">合同明细</div>
      <div v-if="childContractsError" style="color: #c92a2a; margin-bottom: 8px;">
        {{ childContractsError }}
      </div>
      <div class="table-wrap contract-table-wrap">
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
            <tr v-for="item in childContracts" :key="item.id">
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
              <td>{{ item.account_name || item.account || '-' }}</td>
              <td>{{ vendorName(item.vendor_company) }}</td>
              <td>{{ formatMoney(item.amount) }}</td>
              <td>{{ formatMoney(item.paid_total) }}</td>
              <td>{{ item.current_output ?? '-' }}</td>
              <td>{{ receivableAmountFor(item) }}</td>
              <td>{{ item.signed_at || '-' }}</td>
              <td>{{ item.region_name || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">详情</router-link>
              </td>
            </tr>
            <tr v-if="!childContracts.length">
              <td colspan="13" style="color: #888;">暂无合同明细</td>
            </tr>
          </tbody>
        </table>
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
const saving = ref(false)
const submittingApproval = ref(false)
const error = ref('')
const success = ref('')
const opportunities = ref([])
const regions = ref([])
const users = ref([])
const frameworkContracts = ref([])
const childContracts = ref([])
const childContractsError = ref('')
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
  paid_at: '',
  note: '',
  region: null,
  owner: null
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
const accountFocused = ref(false)
let accountBlurTimer = null
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
  owner: null,
  amount: null,
  current_output: null,
  final_settlement_amount: null,
  status: 'draft',
  approval_status: 'pending',
  is_framework: false,
  framework_contract: null,
  remark: '',
  created_by_name: '',
  created_at: '',
  updated_by_name: '',
  updated_at: '',
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

const vendorName = (vendorId) => {
  const item = lookupOptions.value.vendor_company.find((opt) => String(opt.id) === String(vendorId))
  return item ? item.name : (vendorId || '-')
}

const frameworkLabel = (item) => {
  if (!item) return '-'
  return item.name || item.contract_no || `合同${item.id}`
}

const formatMoney = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
}

const formatDate = (value) => {
  if (!value) return '-'
  if (typeof value === 'string') return value.slice(0, 10)
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toISOString().slice(0, 10)
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

const fetchUsers = async () => {
  const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
  users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchFrameworkContracts = async () => {
  try {
    const res = await api.get('/contracts/', { params: { is_framework: 1, page: 1, page_size: 1000 } })
    frameworkContracts.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    frameworkContracts.value = []
  }
}

const fetchChildContracts = async () => {
  if (!isEdit.value || !form.value.is_framework) {
    childContracts.value = []
    return
  }
  childContractsError.value = ''
  try {
    const res = await api.get('/contracts/', {
      params: { framework_contract: route.params.id, page: 1, page_size: 1000, ordering: '-created_at' }
    })
    childContracts.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    childContracts.value = []
    childContractsError.value = '加载合同明细失败'
  }
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
  accountFocused.value = false
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
const showAccountDropdown = computed(() => accountFocused.value && accountQuery.value.trim().length > 0)
const applyDefaultOwnerRegion = () => {
  if (isEdit.value) return
  if (form.value.region == null && auth.user?.region != null) {
    form.value.region = Number(auth.user.region)
  }
  if (form.value.owner == null && auth.user?.id != null) {
    form.value.owner = Number(auth.user.id)
  }
}

const applyPaymentDefaults = () => {
  if (paymentForm.value.region == null && form.value.region != null) {
    paymentForm.value.region = Number(form.value.region)
  }
  if (paymentForm.value.owner == null && form.value.owner != null) {
    paymentForm.value.owner = Number(form.value.owner)
  }
}

const resetPaymentForm = () => {
  paymentForm.value = {
    amount: null,
    paid_at: '',
    note: '',
    region: form.value.region != null ? Number(form.value.region) : null,
    owner: form.value.owner != null ? Number(form.value.owner) : null
  }
}

const showQuickCreate = computed(() => {
  const query = accountQuery.value.trim()
  return query && query.length >= 2 && !accountOptions.value.length
})

const receivableAmount = computed(() => {
  const base = form.value.current_output != null ? Number(form.value.current_output) : Number(form.value.amount)
  if (Number.isNaN(base)) return ''
  const total = Number(paidTotal.value) || 0
  const value = base - total
  return Number.isFinite(value) ? value.toFixed(2) : ''
})

const receivableAmountFor = (item) => {
  if (!item) return '-'
  const paidTotal = Number(item.paid_total || 0)
  const base = item.current_output != null ? Number(item.current_output) : Number(item.amount)
  if (Number.isNaN(base)) return '-'
  const value = base - paidTotal
  return Number.isFinite(value) ? value.toFixed(2) : '-'
}

const handleAccountFocus = () => {
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
    accountBlurTimer = null
  }
  accountFocused.value = true
}

const handleAccountBlur = () => {
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
  }
  accountBlurTimer = setTimeout(() => {
    accountFocused.value = false
  }, 150)
}

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
      owner: data.owner != null ? Number(data.owner) : null,
      amount: data.amount != null ? Number(data.amount) : null,
      current_output: data.current_output != null ? Number(data.current_output) : null,
      final_settlement_amount: data.final_settlement_amount != null ? Number(data.final_settlement_amount) : null,
      status: data.status || 'draft',
      approval_status: data.approval_status || 'pending',
      is_framework: Boolean(data.is_framework),
      framework_contract: data.framework_contract != null ? Number(data.framework_contract) : null,
      remark: data.remark || '',
      created_by_name: data.created_by_name || '',
      created_at: data.created_at || '',
      updated_by_name: data.updated_by_name || '',
      updated_at: data.updated_at || '',
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
    if (!editingPaymentId.value) {
      applyPaymentDefaults()
    }
    await fetchChildContracts()
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
    paid_at: item.paid_at || '',
    note: item.note || '',
    region: item.region != null ? Number(item.region) : (form.value.region != null ? Number(form.value.region) : null),
    owner: item.owner != null ? Number(item.owner) : (form.value.owner != null ? Number(form.value.owner) : null)
  }
  paymentError.value = ''
  paymentSuccess.value = ''
}

const cancelEditPayment = () => {
  editingPaymentId.value = null
  resetPaymentForm()
  paymentError.value = ''
  paymentSuccess.value = ''
}

const savePayment = async () => {
  if (!paymentForm.value.amount) {
    paymentError.value = '回款金额不能为空'
    return
  }
  if (!paymentForm.value.region) {
    paymentError.value = '请选择所属区域'
    return
  }
  if (!paymentForm.value.owner) {
    paymentError.value = '请选择负责人'
    return
  }
  paymentError.value = ''
  paymentSuccess.value = ''
  paymentSaving.value = true
  try {
    if (editingPaymentId.value) {
      const payload = {
        amount: Number(paymentForm.value.amount),
        paid_at: paymentForm.value.paid_at || null,
        note: paymentForm.value.note || '',
        region: Number(paymentForm.value.region),
        owner: Number(paymentForm.value.owner)
      }
      await api.patch(`/payments/${editingPaymentId.value}/`, payload)
      paymentSuccess.value = '回款已更新'
      editingPaymentId.value = null
      resetPaymentForm()
    } else {
      const payload = {
        contract: Number(route.params.id),
        amount: Number(paymentForm.value.amount),
        paid_at: paymentForm.value.paid_at || null,
        note: paymentForm.value.note || '',
        region: Number(paymentForm.value.region),
        owner: Number(paymentForm.value.owner),
        status: 'paid'
      }
      await api.post('/payments/', payload)
      resetPaymentForm()
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
  ...(form.value.region ? { region: Number(form.value.region) } : {}),
  ...(form.value.owner ? { owner: Number(form.value.owner) } : {}),
  is_framework: Boolean(form.value.is_framework),
  framework_contract: form.value.is_framework
    ? null
    : (form.value.framework_contract ? Number(form.value.framework_contract) : null),
  remark: form.value.remark || '',
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
  if (!form.value.region) {
    error.value = '请选择所属区域'
    return
  }
  if (!form.value.owner) {
    error.value = '请选择负责人'
    return
  }
  const amount = Number(form.value.amount)
  const isFramework = Boolean(form.value.is_framework)
  if (form.value.amount === '' || form.value.amount === null || form.value.amount === undefined) {
    error.value = '合同金额不能为空'
    return
  }
  if (!isFramework && (!Number.isFinite(amount) || amount <= 0)) {
    error.value = '合同金额必须大于0'
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

const submitApproval = async () => {
  if (!isEdit.value) return
  error.value = ''
  success.value = ''
  submittingApproval.value = true
  try {
    await api.post(`/contracts/${route.params.id}/submit_approval/`)
    success.value = '已提交审批'
    await loadContract()
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

const cancel = () => {
  router.push('/contracts')
}

const goBack = () => {
  router.back()
}

onMounted(async () => {
  if (!auth.user) {
    await auth.fetchMe()
  }
  await fetchLookups()
  await fetchOpportunities()
  await fetchRegions()
  await fetchUsers()
  await fetchFrameworkContracts()
  await loadContract()
  await fetchAttachments()
  await fetchPayments()
  applyDefaultOwnerRegion()
  applyPaymentDefaults()
  if (route.query.saved) {
    success.value = '合同已保存'
  }
})

watch(accountQuery, (value) => {
  const query = value.trim()
  if (!query) {
    accountCreate.value.full_name = ''
    if (searchTimer) clearTimeout(searchTimer)
    accountOptions.value = []
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

watch(
  () => form.value.is_framework,
  (value) => {
    if (value) {
      form.value.framework_contract = null
      if (isEdit.value) {
        fetchChildContracts()
      }
    } else {
      childContracts.value = []
    }
  }
)
</script>

<style scoped>
.contract-detail {
  font-size: 13px;
}
</style>
