<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">商机</h2>
        <div class="page-subtitle">商机信息维护</div>
      </div>
      <div class="page-actions">
        <button class="button" @click="goCreate">新建商机</button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">商机总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">转化率</div>
        <div class="stat-value">{{ conversionRate }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">预计金额合计</div>
        <div class="stat-value">{{ totalAmount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成交数</div>
        <div class="stat-value">{{ wonCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">商机关闭数</div>
        <div class="stat-value">{{ lostCount }}</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: !filters.stage }" @click="setStage('')">
        全部 ({{ totalCount }})
      </button>
      <button
        v-for="s in stages"
        :key="s.value"
        class="tab"
        :class="{ active: filters.stage === s.value }"
        @click="setStage(s.value)"
      >
        {{ s.label }} ({{ stageCount(s.value) }})
      </button>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">筛选</div>
        <div class="field">
          <label>关键词</label>
          <input v-model="search" placeholder="搜索商机名称" @keyup.enter="applyFilters" />
        </div>
        <div class="field">
          <label>客户</label>
          <select v-model="filters.account">
            <option value="">全部</option>
            <option v-for="acc in accounts" :key="acc.id" :value="String(acc.id)">
              {{ accountLabel(acc) }}
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
        <div class="field">
          <label>负责人</label>
          <select v-model="filters.owner">
            <option value="">全部</option>
            <option v-for="u in visibleUsers" :key="u.id" :value="String(u.id)">
              {{ userLabel(u) }}
            </option>
          </select>
          <div v-if="usersError" style="font-size: 12px; color: #c92a2a;">{{ usersError }}</div>
        </div>
        <div class="field">
          <label>商机分类</label>
          <select v-model="filters.opportunity_category">
            <option value="">全部</option>
            <option v-for="opt in lookupOptions.opportunity_category" :key="opt.id" :value="String(opt.id)">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>客户级别</label>
          <select v-model="filters.customer_level">
            <option value="">全部</option>
            <option v-for="opt in lookupOptions.customer_level" :key="opt.id" :value="String(opt.id)">
              {{ opt.name }}
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
          <div>共 {{ totalCount }} 条商机</div>
          <div>最新跟进实时同步</div>
        </div>
        <div class="list-toolbar">
          <div class="toolbar-left">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-created_at">最新创建</option>
              <option value="-expected_amount">预计金额高→低</option>
              <option value="expected_amount">预计金额低→高</option>
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
        <div v-for="item in pagedOpportunities" :key="item.id" class="list-row">
          <div>
            <router-link class="list-title link-button" :to="`/opportunities/${item.id}`">
              {{ item.opportunity_name }}
            </router-link>
            <div class="list-meta">
              <span :class="['badge', stageBadgeClass(item.stage)]">{{ stageLabel(item.stage) }}</span>
              <span>预计金额：{{ item.expected_amount || '-' }}</span>
              <span>客户：{{ item.account_name || '-' }}</span>
              <span>区域：{{ item.region_name || '-' }}</span>
              <span>负责人：{{ item.owner_name || item.owner }}</span>
              <span>最新跟进：{{ item.latest_followup_note || '-' }}</span>
            </div>
          </div>
          <div class="list-actions">
            <router-link class="link-button" :to="`/opportunities/${item.id}`">详情</router-link>
            <button v-if="canDelete" class="button secondary" @click="deleteOpportunity(item.id)">删除</button>
          </div>
        </div>
        <div v-if="!pagedOpportunities.length" style="padding: 16px; color: #888;">暂无数据</div>
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

const opportunities = ref([])
const total = ref(0)
const router = useRouter()
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.opportunity?.delete))
const search = ref('')
const error = ref('')
const filters = ref({
  stage: '',
  opportunity_category: '',
  customer_level: '',
  region: '',
  account: '',
  owner: ''
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
  opportunity_category: [],
  customer_level: []
})
const regions = ref([])
const accounts = ref([])
const users = ref([])
const usersError = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-created_at')

const stageLabel = (stage) => {
  const map = {
    lead: '线索阶段',
    opportunity: '商机阶段',
    demand: '需求引导',
    solution: '方案阶段',
    business: '商务谈判',
    contract: '合同审批',
    won: '成交关闭',
    framework: '框架合作',
    lost: '商机关闭'
  }
  return map[stage] || stage
}

const stageBadgeClass = (stage) => {
  if (stage === 'won' || stage === 'framework') return 'green'
  if (stage === 'lost') return 'gray'
  return 'orange'
}

const accountLabel = (acc) => acc.full_name || acc.short_name || acc.name || `ID ${acc.id}`
const userLabel = (user) => {
  if (!user) return ''
  const name = [user.first_name, user.last_name].filter(Boolean).join('')
  return name ? `${user.username}（${name}）` : user.username
}

const externalRegionId = computed(() => {
  const match = regions.value.find((r) => r.name === '外部人员' || r.code === '外部人员')
  return match ? Number(match.id) : null
})

const visibleUsers = computed(() => {
  const extId = externalRegionId.value
  if (!extId) return users.value
  return users.value.filter((u) => Number(u.region) !== extId)
})

const buildParams = () => {
  const params = {
    page: currentPage.value,
    page_size: pageSize,
    ordering: ordering.value
  }
  if (search.value) params.search = search.value
  if (filters.value.stage) params.stage = filters.value.stage
  if (filters.value.opportunity_category) params.opportunity_category = filters.value.opportunity_category
  if (filters.value.customer_level) params.customer_level = filters.value.customer_level
  if (filters.value.region) params.region = filters.value.region
  if (filters.value.account) params.account = filters.value.account
  if (filters.value.owner) params.owner = filters.value.owner
  return params
}

const fetchData = async () => {
  error.value = ''
  const params = buildParams()
  try {
    const res = await api.get('/opportunities/', { params })
    if (res.data && Array.isArray(res.data.results)) {
      opportunities.value = res.data.results
      total.value = res.data.count
    } else {
      opportunities.value = res.data
      total.value = res.data.length || 0
    }
  } catch (err) {
    opportunities.value = []
    total.value = 0
    const status = err.response?.status
    if (status === 401) {
      error.value = '登录已过期，请重新登录'
    } else {
      error.value = '加载失败，请确认已登录且后端服务可用'
    }
  }
}

const totalCount = computed(() => total.value)
const totalAmount = computed(() => {
  const sum = opportunities.value.reduce((total, item) => total + (Number(item.expected_amount) || 0), 0)
  return sum ? sum.toFixed(2) : '0.00'
})
const wonCount = computed(() => opportunities.value.filter((item) => item.stage === 'won').length)
const lostCount = computed(() => opportunities.value.filter((item) => item.stage === 'lost').length)
const conversionRate = computed(() => {
  const totalItems = totalCount.value || 0
  if (!totalItems) return '0%'
  const rate = (wonCount.value / totalItems) * 100
  return `${rate.toFixed(2)}%`
})

const stageCount = (stageValue) => opportunities.value.filter((item) => item.stage === stageValue).length

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedOpportunities = computed(() => {
  return opportunities.value
})

const setStage = (value) => {
  filters.value.stage = value
  applyFilters()
}

const goCreate = () => {
  router.push('/opportunities/new')
}

const fetchLookups = async () => {
  const res = await api.get('/lookups/')
  const categories = Array.isArray(res.data?.results) ? res.data.results : res.data
  const pick = (code) => {
    const cat = categories.find((c) => c.code === code)
    return cat ? cat.options : []
  }
  lookupOptions.value = {
    opportunity_category: pick('opportunity_category'),
    customer_level: pick('customer_level')
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

const fetchUsers = async () => {
  usersError.value = ''
  try {
    const res = await api.get('/users/', {
      params: { page: 1, page_size: 200, ordering: 'username', opportunity_owner: 1 }
    })
    users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    users.value = []
    usersError.value = '负责人列表加载失败'
  }
}

const resetFilters = () => {
  search.value = ''
  filters.value = { stage: '', opportunity_category: '', customer_level: '', region: '', account: '', owner: '' }
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
  api.get('/opportunities/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'opportunities.csv'
      link.click()
      URL.revokeObjectURL(url)
    })
}

const deleteOpportunity = async (id) => {
  if (!confirm('确认删除该商机？')) return
  try {
    await api.delete(`/opportunities/${id}/`)
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
  await fetchUsers()
  await fetchData()
})

watch(ordering, () => {
  applyFilters()
})
</script>
