<template>
  <div>
    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="card" style="padding: 12px 16px;">
        <div class="filter-bar dashboard-filters" style="margin-bottom: 0;">
          <div class="filter-left">
            <select v-model="filters.year">
              <option value="">全部年度</option>
              <option v-for="y in years" :key="y" :value="String(y)">{{ y }}年</option>
            </select>
            <select v-model="filters.month" :disabled="!filters.year">
              <option value="">全部月度</option>
              <option v-for="m in months" :key="m" :value="String(m)">{{ m }}月</option>
            </select>
            <select v-model="filters.region">
              <option value="">全部区域</option>
              <option v-for="r in regions" :key="r.id" :value="String(r.id)">
                {{ r.name || r.code || `ID ${r.id}` }}
              </option>
          </select>
          <select v-model="filters.owner">
            <option value="">全部负责人</option>
            <option v-for="u in users" :key="u.id" :value="String(u.id)">
              {{ u.username || u.email || `ID ${u.id}` }}
            </option>
          </select>
          <button class="button" @click="applyFilters">应用筛选</button>
          <button class="button secondary" @click="resetFilters">清除</button>
        </div>
      </div>
      <div v-if="usersError" style="font-size: 12px; color: #c92a2a; margin-top: 6px;">{{ usersError }}</div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">商机数量</div>
        <div class="stat-value">{{ totals.count }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">预计成交金额</div>
        <div class="stat-value">{{ formatMoney(totals.total_value) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">概率成交金额</div>
        <div class="stat-value">{{ formatMoney(totals.weighted_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">商机转化率</div>
        <div class="stat-value">{{ conversionRate }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">合同总额</div>
        <div class="stat-value">{{ formatMoney(contractSummary.contract_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已回款</div>
        <div class="stat-value">{{ formatMoney(contractSummary.paid_total) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">应收款</div>
        <div class="stat-value">{{ formatMoney(contractSummary.receivable_total) }}</div>
      </div>
    </div>

    <div class="dashboard-grid">
      <div class="card dashboard-card">
        <div class="section-title">商机阶段分布</div>
        <div class="bar-list">
          <div v-for="item in stageList" :key="item.stage" class="bar-item">
            <div class="bar-label">{{ item.label }}</div>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: stagePercent(item) + '%' }"></div>
            </div>
            <div class="bar-value">{{ item.count }}</div>
          </div>
        </div>
      </div>
      <div class="card dashboard-card">
        <div class="section-title">商机漏斗（金额）</div>
        <div class="bar-list">
          <div v-for="item in stageList" :key="item.stage + '-amount'" class="bar-item">
            <div class="bar-label">{{ item.label }}</div>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: amountPercent(item) + '%' }"></div>
            </div>
            <div class="bar-value">{{ formatMoney(item.total_value) }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="dashboard-grid">
      <div class="card dashboard-card">
        <div class="section-title">合同与回款汇总</div>
        <div class="mini-grid">
          <div class="mini-card">
            <div class="mini-label">合同总额</div>
            <div class="mini-value">{{ formatMoney(contractSummary.contract_total) }}</div>
          </div>
          <div class="mini-card">
            <div class="mini-label">已回款</div>
            <div class="mini-value">{{ formatMoney(contractSummary.paid_total) }}</div>
          </div>
          <div class="mini-card">
            <div class="mini-label">应收款</div>
            <div class="mini-value">{{ formatMoney(contractSummary.receivable_total) }}</div>
          </div>
          <div class="mini-card">
            <div class="mini-label">开票总额</div>
            <div class="mini-value">{{ formatMoney(invoiceTotal) }}</div>
          </div>
        </div>
      </div>
      <div class="card dashboard-card dashboard-table">
        <div class="section-title">区域业绩</div>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>区域</th>
                <th>商机数</th>
                <th>预计金额</th>
                <th>合同金额</th>
                <th>回款金额</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in regionPerformance" :key="item.region_id">
                <td>{{ item.region_name || '-' }}</td>
                <td>{{ item.opportunity_count }}</td>
                <td>{{ formatMoney(item.expected_amount) }}</td>
                <td>{{ formatMoney(item.contract_amount) }}</td>
                <td>{{ formatMoney(item.payment_amount) }}</td>
              </tr>
              <tr v-if="!regionPerformance.length">
                <td colspan="5" style="text-align: center; color: #8a94a6;">暂无区域业绩数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="card dashboard-table">
      <div class="section-title">个人业绩</div>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>负责人</th>
              <th>商机数</th>
              <th>预计金额</th>
              <th>合同金额</th>
              <th>回款金额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in ownerPerformance" :key="item.owner_id">
              <td>{{ item.owner_name || '-' }}</td>
              <td>{{ item.opportunity_count }}</td>
              <td>{{ formatMoney(item.expected_amount) }}</td>
              <td>{{ formatMoney(item.contract_amount) }}</td>
              <td>{{ formatMoney(item.payment_amount) }}</td>
            </tr>
            <tr v-if="!ownerPerformance.length">
              <td colspan="5" style="text-align: center; color: #8a94a6;">暂无个人业绩数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const loading = ref(false)
const error = ref('')
const report = ref(null)
const regions = ref([])
const users = ref([])
const usersError = ref('')
const currentYear = new Date().getFullYear()
const filters = ref({
  year: String(currentYear),
  month: '',
  region: '',
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

const formatMoney = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

const years = computed(() => {
  return Array.from({ length: 5 }, (_, idx) => currentYear - idx)
})

const months = computed(() => {
  return Array.from({ length: 12 }, (_, idx) => idx + 1)
})

const totals = computed(() => {
  if (report.value?.opportunity_totals) return report.value.opportunity_totals
  const stageItems = report.value?.opportunity_stages || []
  const count = stageItems.reduce((sum, item) => sum + (Number(item.count) || 0), 0)
  const total_value = stageItems.reduce((sum, item) => sum + (Number(item.total_value) || 0), 0)
  return { count, total_value, weighted_total: 0, won_count: 0, lost_count: 0 }
})

const conversionRate = computed(() => {
  const total = Number(totals.value.count) || 0
  if (!total) return '0%'
  const won = Number(totals.value.won_count || 0)
  const rate = (won / total) * 100
  return `${rate.toFixed(2)}%`
})

const stageList = computed(() => {
  if (report.value?.opportunity_stages?.length) return report.value.opportunity_stages
  const raw = report.value?.opportunities || []
  const map = raw.reduce((acc, item) => {
    acc[item.stage] = item
    return acc
  }, {})
  return stages.map((stage) => ({
    stage: stage.value,
    label: stage.label,
    count: Number(map[stage.value]?.count || 0),
    total_value: Number(map[stage.value]?.total_value || 0)
  }))
})

const contractSummary = computed(() => {
  if (report.value?.contract_summary) return report.value.contract_summary
  return {
    contract_total: report.value?.contracts?.total_amount || 0,
    paid_total: report.value?.payments?.total_amount || 0,
    receivable_total: 0
  }
})

const invoiceTotal = computed(() => report.value?.invoices?.total_amount || 0)

const ownerPerformance = computed(() => report.value?.owner_performance || [])
const regionPerformance = computed(() => report.value?.region_performance || [])

const stagePercent = (item) => {
  const total = Number(totals.value.count) || 0
  if (!total) return 0
  return Math.round((Number(item.count) || 0) / total * 100)
}

const amountPercent = (item) => {
  const total = Number(totals.value.total_value) || 0
  if (!total) return 0
  return Math.round((Number(item.total_value) || 0) / total * 100)
}

const buildParams = () => {
  const params = {}
  if (filters.value.year) params.year = filters.value.year
  if (filters.value.year && filters.value.month) params.month = filters.value.month
  if (filters.value.region) params.region = filters.value.region
  if (filters.value.owner) params.owner = filters.value.owner
  return params
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchUsers = async () => {
  usersError.value = ''
  try {
    const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
    users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    users.value = []
    usersError.value = '负责人列表加载失败'
  }
}

const applyFilters = () => {
  fetchReport()
}

const resetFilters = () => {
  filters.value = { year: String(currentYear), month: '', region: '', owner: '' }
  fetchReport()
}

const fetchReport = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/reports/', { params: buildParams() })
    report.value = res.data || {}
  } catch (err) {
    error.value = '看板数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchRegions()
  await fetchUsers()
  await fetchReport()
})
</script>
