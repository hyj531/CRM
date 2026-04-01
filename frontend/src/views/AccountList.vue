<template>
  <div class="account-page">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">客户总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">启用客户</div>
        <div class="stat-value">{{ activeCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">归档客户</div>
        <div class="stat-value">{{ archivedCount }}</div>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="filter-bar account-filters">
      <div class="filter-left">
        <input v-model="search" placeholder="搜索客户全称/简称/行业/电话" @keyup.enter="applyFilters" />
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="archived">归档</option>
        </select>
        <button class="button" @click="applyFilters">搜索</button>
        <button class="button secondary" @click="resetFilters">清除</button>
      </div>
    </div>

    <div class="card list-card">
      <div class="list-head">
        <div class="list-head-info">
          <div>共 {{ totalCount }} 条客户</div>
        </div>
        <div class="list-head-actions">
          <button class="button" @click="goCreate">新建客户</button>
          <div class="toolbar-left">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-created_at">最新创建</option>
              <option value="name">名称A→Z</option>
              <option value="-name">名称Z→A</option>
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
      <div class="table-wrap account-table-wrap">
        <table class="table account-table">
            <thead>
              <tr>
                <th>客户全称</th>
                <th>客户简称</th>
                <th>级别</th>
                <th>行业</th>
                <th>企业性质</th>
                <th>信用代码</th>
                <th>状态</th>
                <th>负责人</th>
                <th>所属区域</th>
                <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedAccounts" :key="item.id">
                <td>
                  <router-link class="link-button" :to="`/accounts/${item.id}`">
                    {{ item.full_name }}
                  </router-link>
                </td>
                <td>{{ item.short_name || '-' }}</td>
                <td>{{ lookupName(item.customer_level, lookupOptions.customer_level) }}</td>
                <td>{{ item.industry || '-' }}</td>
                <td>{{ lookupName(item.enterprise_nature, lookupOptions.enterprise_nature) }}</td>
                <td>{{ item.credit_code || '-' }}</td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ item.owner_name || item.owner || '-' }}</td>
                <td>{{ item.region_name || item.region || '-' }}</td>
                <td>
                  <router-link class="link-button" :to="`/accounts/${item.id}`">详情</router-link>
                  <button v-if="canDelete" class="button secondary" @click="deleteAccount(item.id)">删除</button>
                </td>
            </tr>
            <tr v-if="!pagedAccounts.length">
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
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const accounts = ref([])
const total = ref(0)
const error = ref('')
const router = useRouter()
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.account?.delete))
const lookupOptions = ref({
  customer_level: [],
  enterprise_nature: [],
  industry: []
})
const search = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-created_at')

const totalCount = computed(() => total.value)
const activeCount = computed(() => accounts.value.filter((item) => item.status === 'active').length)
const archivedCount = computed(() => accounts.value.filter((item) => item.status === 'archived').length)

const statusLabel = (value) => {
  const map = {
    active: '启用',
    archived: '归档'
  }
  return map[value] || value || '-'
}

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedAccounts = computed(() => accounts.value)

const lookupName = (value, list) => {
  const item = list.find((opt) => String(opt.id) === String(value))
  return item ? item.name : (value || '-')
}

const fetchLookups = async () => {
  const res = await api.get('/lookups/')
  const categories = Array.isArray(res.data?.results) ? res.data.results : res.data
  const pick = (code) => {
    const cat = categories.find((c) => c.code === code)
    return cat ? cat.options : []
  }
  lookupOptions.value = {
    customer_level: pick('customer_level'),
    enterprise_nature: pick('enterprise_nature'),
    industry: pick('industry')
  }
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
  const res = await api.get('/accounts/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    accounts.value = res.data.results
    total.value = res.data.count
  } else {
    accounts.value = res.data
    total.value = res.data.length || 0
  }
}
const goCreate = () => {
  router.push('/accounts/new')
}

const exportCsv = () => {
  const params = buildParams()
  delete params.page
  delete params.page_size
  api.get('/accounts/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'accounts.csv'
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

const deleteAccount = async (id) => {
  if (!confirm('确认删除该客户？')) return
  try {
    await api.delete(`/accounts/${id}/`)
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
  await fetchData()
})

watch([statusFilter, ordering], () => {
  applyFilters()
})
</script>

<style scoped>
.account-page .section-title {
  font-size: 14px;
}

.account-form-card label {
  font-size: 14px;
}

.account-form-card input,
.account-form-card select,
.account-form-card textarea {
  font-size: 14px;
}

.account-page .list-card .table th,
.account-page .list-card .table td {
  font-size: 14px;
  padding: 6px 8px;
  line-height: 1.2;
}
</style>
