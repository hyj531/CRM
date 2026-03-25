<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">联系人</h2>
        <div class="page-subtitle">客户关键联系人维护</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="saveContact">
          {{ saving ? '保存中...' : (editingId ? '保存修改' : '保存联系人') }}
        </button>
        <button v-if="editingId" class="button secondary" @click="cancelEdit">取消编辑</button>
        <button class="button secondary" @click="fetchData">刷新</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">联系人总数</div>
        <div class="stat-value">{{ totalCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">关键人</div>
        <div class="stat-value">{{ keyPersonCount }}</div>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="content-grid">
      <div class="card">
        <div class="section-title">{{ editingId ? '编辑联系人' : '新建联系人' }}</div>
        <div class="form-grid">
          <div>
            <label>姓名</label>
            <input v-model="form.name" />
          </div>
          <div>
            <label>所属客户</label>
            <select v-model.number="form.account">
              <option :value="null">请选择客户</option>
              <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                {{ acc.full_name }}{{ acc.short_name ? `（${acc.short_name}）` : '' }}
              </option>
            </select>
          </div>
          <div>
            <label>职位</label>
            <input v-model="form.title" />
          </div>
          <div>
            <label>电话</label>
            <input v-model="form.phone" />
          </div>
          <div>
            <label>邮箱</label>
            <input v-model="form.email" />
          </div>
          <div>
            <label>是否关键人</label>
            <select v-model="form.is_key_person">
              <option :value="false">否</option>
              <option :value="true">是</option>
            </select>
          </div>
          <div>
            <label>偏好/标签</label>
            <input v-model="form.preference" />
          </div>
        </div>
        <div style="margin-top: 10px;">
          <label>备注</label>
          <textarea v-model="form.remark" rows="3"></textarea>
        </div>
      </div>

      <div class="card list-card">
        <div class="list-head">
          <div>共 {{ totalCount }} 条联系人</div>
          <div>客户与角色展示</div>
        </div>
        <div class="filter-bar" style="padding: 12px 16px;">
          <div class="filter-left">
            <input v-model="search" placeholder="搜索姓名/电话/邮箱" @keyup.enter="applyFilters" />
            <select v-model="keyPersonFilter">
              <option value="">全部</option>
              <option value="true">关键人</option>
              <option value="false">非关键人</option>
            </select>
            <button class="button" @click="applyFilters">搜索</button>
            <button class="button secondary" @click="resetFilters">清除</button>
          </div>
          <div class="filter-right">
            <span class="toolbar-label">排序方式</span>
            <select v-model="ordering" class="compact-select">
              <option value="-created_at">最新创建</option>
              <option value="name">姓名A→Z</option>
              <option value="-name">姓名Z→A</option>
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
                <th>姓名</th>
                <th>客户</th>
                <th>职位</th>
                <th>电话</th>
                <th>邮箱</th>
                <th>关键人</th>
              <th>偏好</th>
              <th>备注</th>
              <th>负责人</th>
              <th>所属区域</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedContacts" :key="item.id">
                <td>{{ item.name }}</td>
                <td>{{ accountName(item.account) }}</td>
                <td>{{ item.title || '-' }}</td>
                <td>{{ item.phone || '-' }}</td>
                <td>{{ item.email || '-' }}</td>
                <td>{{ item.is_key_person ? '是' : '否' }}</td>
              <td>{{ item.preference || '-' }}</td>
              <td>{{ item.remark || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>{{ item.region_name || item.region || '-' }}</td>
              <td>
                <button v-if="canEdit" class="button secondary" @click="startEdit(item)">编辑</button>
                <button v-if="canDelete" class="button secondary" @click="deleteContact(item.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!pagedContacts.length">
              <td colspan="11" style="color: #888;">暂无数据</td>
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

const contacts = ref([])
const total = ref(0)
const accounts = ref([])
const error = ref('')
const success = ref('')
const saving = ref(false)
const auth = useAuthStore()
const canDelete = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contact?.delete))
const canEdit = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contact?.update))
const search = ref('')
const keyPersonFilter = ref('')
const currentPage = ref(1)
const pageSize = 10
const ordering = ref('-created_at')
const editingId = ref(null)

const form = ref({
  name: '',
  account: null,
  title: '',
  phone: '',
  email: '',
  is_key_person: false,
  preference: '',
  remark: ''
})

const totalCount = computed(() => total.value)
const keyPersonCount = computed(() => contacts.value.filter((item) => item.is_key_person).length)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const pagedContacts = computed(() => contacts.value)

const resetForm = () => {
  form.value = {
    name: '',
    account: null,
    title: '',
    phone: '',
    email: '',
    is_key_person: false,
    preference: '',
    remark: ''
  }
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
  if (keyPersonFilter.value !== '') params.is_key_person = keyPersonFilter.value
  return params
}

const fetchData = async () => {
  const res = await api.get('/contacts/', { params: buildParams() })
  if (res.data && Array.isArray(res.data.results)) {
    contacts.value = res.data.results
    total.value = res.data.count
  } else {
    contacts.value = res.data
    total.value = res.data.length || 0
  }
}

const fetchAccounts = async () => {
  const res = await api.get('/accounts/', { params: { page: 1, page_size: 1000 } })
  accounts.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const saveContact = async () => {
  if (!form.value.name) {
    error.value = '联系人姓名不能为空'
    return
  }
  if (!form.value.account) {
    error.value = '请选择所属客户'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      account: Number(form.value.account)
    }
    if (editingId.value) {
      await api.patch(`/contacts/${editingId.value}/`, payload)
      success.value = '联系人已更新'
      editingId.value = null
    } else {
      await api.post('/contacts/', payload)
      success.value = '联系人已保存'
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
    name: item.name || '',
    account: item.account != null ? Number(item.account) : null,
    title: item.title || '',
    phone: item.phone || '',
    email: item.email || '',
    is_key_person: Boolean(item.is_key_person),
    preference: item.preference || '',
    remark: item.remark || ''
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
  api.get('/contacts/export/', { params, responseType: 'blob' })
    .then((res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'contacts.csv'
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
  keyPersonFilter.value = ''
  applyFilters()
}

const changePage = (page) => {
  currentPage.value = page
  fetchData()
}

const deleteContact = async (id) => {
  if (!confirm('确认删除该联系人？')) return
  try {
    await api.delete(`/contacts/${id}/`)
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
  await fetchData()
})

watch([keyPersonFilter, ordering], () => {
  applyFilters()
})
</script>
