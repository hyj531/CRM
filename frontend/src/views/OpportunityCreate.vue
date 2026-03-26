<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">新建商机</h2>
        <div class="page-subtitle">创建后可进入详情继续补充</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : '保存商机' }}
        </button>
        <button class="button secondary" @click="cancel">取消</button>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="card">
      <div class="section-title">核心信息</div>
      <div class="form-grid">
        <div>
          <label>商机名称</label>
          <input v-model="form.opportunity_name" placeholder="请输入商机名称" />
        </div>
        <div>
          <label>阶段</label>
          <select v-model="form.stage">
            <option v-for="s in stages" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </div>
        <div v-if="canAssign">
          <label>负责人</label>
          <select v-model.number="form.owner">
            <option :value="null">默认本人</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
          </select>
          <div v-if="usersError" style="font-size: 12px; color: #c92a2a;">{{ usersError }}</div>
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
          <label>成交概率%</label>
          <input v-model.number="form.win_probability" type="number" min="0" max="100" />
        </div>
        <div>
          <label>预计金额</label>
          <input v-model.number="form.expected_amount" type="number" />
        </div>
        <div>
          <label>预计成交时间</label>
          <input v-model="form.expected_close_date" type="date" />
        </div>
        <div>
          <label>企业性质</label>
          <select v-model.number="form.enterprise_nature">
            <option :value="null">未设置</option>
            <option v-for="opt in lookupOptions.enterprise_nature" :key="opt.id" :value="opt.id">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div>
          <label>商机分类</label>
          <select v-model.number="form.opportunity_category">
            <option :value="null">未设置</option>
            <option v-for="opt in lookupOptions.opportunity_category" :key="opt.id" :value="opt.id">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div>
          <label>线索来源</label>
          <select v-model.number="form.lead_source">
            <option :value="null">未设置</option>
            <option v-for="opt in lookupOptions.lead_source" :key="opt.id" :value="opt.id">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div>
          <label>客户</label>
          <div class="account-picker">
            <div class="account-search">
              <input
                v-model="accountQuery"
                placeholder="输入客户全称/简称，自动搜索"
              />
              <button class="button secondary" type="button" @click="triggerSearch">搜索</button>
              <button v-if="form.account" class="button secondary" type="button" @click="clearAccount">
                清除
              </button>
            </div>
            <div v-if="searchHint" class="account-hint">{{ searchHint }}</div>
            <div v-if="!accountQuery" class="account-hint">最近客户</div>
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
              <div class="section-title">新增客户</div>
              <div class="form-grid">
                <div>
                  <label>客户全称</label>
                  <input v-model="accountCreate.full_name" placeholder="客户全称" />
                </div>
                <div>
                  <label>客户简称</label>
                  <input v-model="accountCreate.short_name" placeholder="客户简称" />
                </div>
              </div>
              <div style="margin-top: 10px;">
                <button class="button" type="button" :disabled="accountCreateSaving" @click="createAccount">
                  {{ accountCreateSaving ? '保存中...' : '保存客户' }}
                </button>
                <span v-if="accountCreateError" style="margin-left: 10px; color: #c92a2a;">
                  {{ accountCreateError }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div style="grid-column: 1 / -1;">
          <label>备注</label>
          <textarea v-model="form.remark" rows="3"></textarea>
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

const router = useRouter()
const saving = ref(false)
const error = ref('')
const auth = useAuthStore()
const canAssign = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.opportunity?.update))
const users = ref([])
const usersError = ref('')
const regions = ref([])
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
  opportunity_name: '',
  stage: 'lead',
  owner: null,
  win_probability: null,
  expected_amount: null,
  expected_close_date: '',
  remark: '',
  account: null,
  region: null,
  enterprise_nature: null,
  opportunity_category: null,
  lead_source: null,
})

const stages = [
  { value: 'lead', label: '线索阶段' },
  { value: 'opportunity', label: '商机阶段' },
  { value: 'demand', label: '需求引导' },
  { value: 'solution', label: '方案阶段' },
  { value: 'business', label: '商务谈判' },
  { value: 'contract', label: '合同审批' },
  { value: 'won', label: '成交关闭' },
  { value: 'framework', label: '框架合作' },
  { value: 'lost', label: '商机关闭' }
]

const lookupOptions = ref({
  enterprise_nature: [],
  opportunity_category: [],
  lead_source: []
})

const fetchLookups = async () => {
  const res = await api.get('/lookups/')
  const categories = Array.isArray(res.data?.results) ? res.data.results : res.data
  const pick = (code) => {
    const cat = categories.find((c) => c.code === code)
    return cat ? cat.options : []
  }
  lookupOptions.value = {
    enterprise_nature: pick('enterprise_nature'),
    opportunity_category: pick('opportunity_category'),
    lead_source: pick('lead_source')
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

const fetchUsers = async () => {
  if (!canAssign.value) return
  try {
    const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
    users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    users.value = []
    usersError.value = '负责人列表加载失败'
  }
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
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

const createAccount = async () => {
  if (!accountCreate.value.full_name) {
    accountCreateError.value = '客户全称不能为空'
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

const normalizePayload = () => ({
  opportunity_name: form.value.opportunity_name,
  stage: form.value.stage,
  owner: form.value.owner ? Number(form.value.owner) : null,
  win_probability: form.value.win_probability === '' ? null : form.value.win_probability,
  expected_amount: form.value.expected_amount === '' ? null : form.value.expected_amount,
  expected_close_date: form.value.expected_close_date || null,
  remark: form.value.remark || '',
  account: form.value.account ? Number(form.value.account) : null,
  region: form.value.region ? Number(form.value.region) : null,
  enterprise_nature: form.value.enterprise_nature ? Number(form.value.enterprise_nature) : null,
  opportunity_category: form.value.opportunity_category ? Number(form.value.opportunity_category) : null,
  lead_source: form.value.lead_source ? Number(form.value.lead_source) : null
})

const save = async () => {
  if (!form.value.opportunity_name) {
    error.value = '商机名称不能为空'
    return
  }
  error.value = ''
  saving.value = true
  try {
    const res = await api.post('/opportunities/', normalizePayload())
    router.push(`/opportunities/${res.data.id}`)
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
  router.push('/opportunities')
}

onMounted(async () => {
  await fetchLookups()
  await fetchUsers()
  await fetchRegions()
  await loadAccounts('')
  if (auth.user?.id && !form.value.owner) {
    form.value.owner = Number(auth.user.id)
  }
  if (auth.user?.region && !form.value.region) {
    form.value.region = Number(auth.user.region)
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
