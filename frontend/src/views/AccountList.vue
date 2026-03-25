<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">客户</h2>
        <div class="page-subtitle">客户主数据与关联信息维护</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="saveAccount">
          {{ saving ? '保存中...' : (editingId ? '保存修改' : '保存客户') }}
        </button>
        <button v-if="editingId" class="button secondary" @click="cancelEdit">取消编辑</button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

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
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">{{ editingId ? '编辑客户' : '新建客户' }}</div>
        <div class="form-grid">
          <div>
            <label>客户全称</label>
            <input v-model="form.full_name" placeholder="客户全称" />
          </div>
          <div>
            <label>客户简称</label>
            <input v-model="form.short_name" placeholder="客户简称" />
          </div>
          <div>
            <label>客户级别</label>
            <select v-model.number="form.customer_level">
              <option :value="null">未设置</option>
              <option v-for="opt in lookupOptions.customer_level" :key="opt.id" :value="opt.id">
                {{ opt.name }}
              </option>
            </select>
          </div>
          <div>
            <label>行业</label>
            <select v-model="form.industry">
              <option value="">未设置</option>
              <option v-for="opt in lookupOptions.industry" :key="opt.id" :value="opt.name">
                {{ opt.name }}
              </option>
            </select>
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
            <label>企业规模</label>
            <input v-model="form.scale" />
          </div>
          <div>
            <label>统一社会信用代码</label>
            <input v-model="form.credit_code" />
          </div>
          <div>
            <label>地址</label>
            <input v-model="form.address" />
          </div>
          <div>
            <label>电话</label>
            <input v-model="form.phone" />
          </div>
          <div>
            <label>官网</label>
            <input v-model="form.website" />
          </div>
          <div>
            <label>状态</label>
            <select v-model="form.status">
              <option value="active">启用</option>
              <option value="archived">归档</option>
            </select>
          </div>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 条客户</div>
          <div>字段完整展示</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
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
          <div class="filter-right">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-created_at">最新创建</option>
              <option value="name">名称A→Z</option>
              <option value="-name">名称Z→A</option>
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
                <th>客户全称</th>
                <th>客户简称</th>
                <th>级别</th>
                <th>行业</th>
                <th>企业性质</th>
                <th>规模</th>
                <th>信用代码</th>
                <th>地址</th>
                <th>电话</th>
                <th>官网</th>
              <th>状态</th>
              <th>负责人</th>
              <th>所属区域</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedAccounts" :key="item.id">
                <td>{{ item.full_name }}</td>
                <td>{{ item.short_name || '-' }}</td>
                <td>{{ lookupName(item.customer_level, lookupOptions.customer_level) }}</td>
                <td>{{ item.industry || '-' }}</td>
                <td>{{ lookupName(item.enterprise_nature, lookupOptions.enterprise_nature) }}</td>
                <td>{{ item.scale || '-' }}</td>
                <td>{{ item.credit_code || '-' }}</td>
                <td>{{ item.address || '-' }}</td>
                <td>{{ item.phone || '-' }}</td>
                <td>{{ item.website || '-' }}</td>
              <td>{{ item.status }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || item.region || '-' }}</td>
              <td>
                <button v-if="canEdit" class="button secondary" @click="startEdit(item)">编辑</button>
                <button v-if="canDelete" class="button secondary" @click="deleteAccount(item.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!pagedAccounts.length">
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

const accounts = ref([])
const total = ref(0)
const error = ref('')
const success = ref('')
const saving = ref(false)
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.account?.delete))
const canEdit = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.account?.update))
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
const editingId = ref(null)

const form = ref({
  full_name: '',
  short_name: '',
  customer_level: null,
  industry: '',
  enterprise_nature: null,
  scale: '',
  credit_code: '',
  address: '',
  phone: '',
  website: '',
  status: 'active'
})

const totalCount = computed(() => total.value)
const activeCount = computed(() => accounts.value.filter((item) => item.status === 'active').length)
const archivedCount = computed(() => accounts.value.filter((item) => item.status === 'archived').length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedAccounts = computed(() => accounts.value)

const resetForm = () => {
  form.value = {
    full_name: '',
    short_name: '',
    customer_level: null,
    industry: '',
    enterprise_nature: null,
    scale: '',
    credit_code: '',
    address: '',
    phone: '',
    website: '',
    status: 'active'
  }
}

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

const saveAccount = async () => {
  if (!form.value.full_name) {
    error.value = '客户全称不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      customer_level: form.value.customer_level ? Number(form.value.customer_level) : null,
      enterprise_nature: form.value.enterprise_nature ? Number(form.value.enterprise_nature) : null,
      website: form.value.website || ''
    }
    if (editingId.value) {
      await api.patch(`/accounts/${editingId.value}/`, payload)
      success.value = '客户已更新'
      editingId.value = null
    } else {
      await api.post('/accounts/', payload)
      success.value = '客户已保存'
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
    full_name: item.full_name || '',
    short_name: item.short_name || '',
    customer_level: item.customer_level != null ? Number(item.customer_level) : null,
    industry: item.industry || '',
    enterprise_nature: item.enterprise_nature != null ? Number(item.enterprise_nature) : null,
    scale: item.scale || '',
    credit_code: item.credit_code || '',
    address: item.address || '',
    phone: item.phone || '',
    website: item.website || '',
    status: item.status || 'active'
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
