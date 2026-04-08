<template>
  <div class="account-detail">
    <div class="page-header">
      <div>
        <div class="account-header-line">
          <h2 class="page-title">{{ isNew ? '新建客户' : '客户详情' }}</h2>
          <div class="detail-meta">
            <span>创建人：{{ audit.created_by_name || '-' }}</span>
            <span>创建日期：{{ formatDate(audit.created_at) }}</span>
            <span>更新人：{{ audit.updated_by_name || '-' }}</span>
            <span>更新日期：{{ formatDate(audit.updated_at) }}</span>
          </div>
        </div>
        <div class="page-subtitle">客户主数据与联系人维护</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="saveAccount">
          {{ saving ? '保存中...' : '保存客户' }}
        </button>
        <button class="button secondary" @click="goBack">返回列表</button>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="card account-form-card">
        <div class="section-title">客户信息</div>
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
          <div>
            <label>所属区域</label>
            <select v-model.number="form.region">
              <option :value="null">默认所属区域</option>
              <option v-for="r in regions" :key="r.id" :value="r.id">
                {{ r.name || r.code || `ID ${r.id}` }}
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
        </div>
    </div>

    <div class="card">
        <div class="section-title">联系人</div>
        <div v-if="!accountId" style="color: #888;">请先保存客户，再添加联系人。</div>
        <div v-else>
          <div class="form-grid">
            <div>
              <label>姓名</label>
              <input v-model="contactForm.name" placeholder="联系人姓名" />
            </div>
            <div>
              <label>职位</label>
              <input v-model="contactForm.title" placeholder="职位" />
            </div>
            <div>
              <label>电话</label>
              <input v-model="contactForm.phone" placeholder="电话" />
            </div>
            <div>
              <label>邮箱</label>
              <input v-model="contactForm.email" placeholder="邮箱" />
            </div>
            <div>
              <label>是否关键人</label>
              <select v-model="contactForm.is_key_person">
                <option :value="false">否</option>
                <option :value="true">是</option>
              </select>
            </div>
            <div>
              <label>偏好/标签</label>
              <input v-model="contactForm.preference" placeholder="偏好/标签" />
            </div>
          </div>
          <div style="margin-top: 10px;">
            <label>备注</label>
            <textarea v-model="contactForm.remark" rows="3"></textarea>
          </div>
          <div class="filter-actions" style="margin-top: 12px;">
            <button class="button" :disabled="contactSaving" @click="saveContact">
              {{ contactSaving ? '保存中...' : (editingContactId ? '保存修改' : '添加联系人') }}
            </button>
            <button class="button secondary" @click="resetContactForm">清空</button>
            <button v-if="editingContactId" class="button secondary" @click="cancelEditContact">取消编辑</button>
          </div>
          <div v-if="contactError" style="color: #c92a2a; margin-top: 8px;">{{ contactError }}</div>
          <div v-if="contactSuccess" style="color: #2b8a3e; margin-top: 8px;">{{ contactSuccess }}</div>
          <div style="margin-top: 12px;">
            <div class="section-title" style="font-size: 13px;">已有联系人 ({{ contacts.length }})</div>
            <div v-if="contacts.length">
              <div v-for="item in contacts" :key="item.id" class="list-row">
                <div>
                  <div class="list-title">
                    <button class="link-button" type="button" @click="openContactModal(item)">
                      {{ item.name }}
                    </button>
                  </div>
                  <div class="list-meta">
                    <span>职位：{{ item.title || '-' }}</span>
                    <span>电话：{{ item.phone || '-' }}</span>
                    <span>邮箱：{{ item.email || '-' }}</span>
                    <span>关键人：{{ item.is_key_person ? '是' : '否' }}</span>
                  </div>
                </div>
                <div v-if="canEditContact">
                  <button class="button secondary" @click="startEditContact(item)">编辑</button>
                </div>
              </div>
            </div>
            <div v-else style="padding: 10px 0; color: #888;">暂无联系人</div>
          </div>
        </div>
    </div>

    <div v-if="showContactModal" class="modal-backdrop">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title">联系人详情</div>
          <button class="button secondary small" type="button" @click="closeContactModal">关闭</button>
        </div>
        <div class="form-grid">
          <div>
            <label>姓名</label>
            <input v-model="modalForm.name" :disabled="!canEditContact" />
          </div>
          <div>
            <label>职位</label>
            <input v-model="modalForm.title" :disabled="!canEditContact" />
          </div>
          <div>
            <label>电话</label>
            <input v-model="modalForm.phone" :disabled="!canEditContact" />
          </div>
          <div>
            <label>邮箱</label>
            <input v-model="modalForm.email" :disabled="!canEditContact" />
          </div>
          <div>
            <label>是否关键人</label>
            <select v-model="modalForm.is_key_person" :disabled="!canEditContact">
              <option :value="false">否</option>
              <option :value="true">是</option>
            </select>
          </div>
          <div>
            <label>偏好/标签</label>
            <input v-model="modalForm.preference" :disabled="!canEditContact" />
          </div>
        </div>
        <div style="margin-top: 10px;">
          <label>备注</label>
          <textarea v-model="modalForm.remark" rows="3" :disabled="!canEditContact"></textarea>
        </div>
        <div class="detail-meta" style="margin-top: 10px;">
          <span>创建人：{{ modalContact?.created_by_name || '-' }}</span>
          <span>创建日期：{{ formatDate(modalContact?.created_at) }}</span>
          <span>更新人：{{ modalContact?.updated_by_name || '-' }}</span>
          <span>更新日期：{{ formatDate(modalContact?.updated_at) }}</span>
        </div>
        <div style="margin-top: 12px;">
          <button
            v-if="canEditContact"
            class="button"
            type="button"
            :disabled="modalSaving"
            @click="saveContactModal"
          >
            {{ modalSaving ? '保存中...' : '保存' }}
          </button>
          <button class="button secondary" type="button" style="margin-left: 8px;" @click="closeContactModal">
            关闭
          </button>
          <span v-if="modalError" style="margin-left: 10px; color: #c92a2a;">{{ modalError }}</span>
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
const error = ref('')
const success = ref('')
const saving = ref(false)
const lookupOptions = ref({
  customer_level: [],
  enterprise_nature: [],
  industry: []
})
const contacts = ref([])
const contactError = ref('')
const contactSuccess = ref('')
const contactSaving = ref(false)
const editingContactId = ref(null)
const showContactModal = ref(false)
const modalContact = ref(null)
const modalForm = ref({
  name: '',
  title: '',
  phone: '',
  email: '',
  is_key_person: false,
  preference: '',
  remark: ''
})
const modalSaving = ref(false)
const modalError = ref('')
const regions = ref([])
const users = ref([])
const audit = ref({
  created_by_name: '',
  created_at: '',
  updated_by_name: '',
  updated_at: ''
})

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
  status: 'active',
  region: null,
  owner: null
})

const contactForm = ref({
  name: '',
  title: '',
  phone: '',
  email: '',
  is_key_person: false,
  preference: '',
  remark: ''
})

const accountId = computed(() => {
  const raw = route.params.id
  if (!raw) return null
  const id = Number(raw)
  return Number.isFinite(id) ? id : null
})

const isNew = computed(() => !accountId.value)
const canEditContact = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.contact?.update))

const goBack = () => {
  router.push('/accounts')
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

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchUsers = async () => {
  const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
  users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const applyDefaultOwnerRegion = () => {
  if (!isNew.value) return
  if (form.value.region == null && auth.user?.region != null) {
    form.value.region = Number(auth.user.region)
  }
  if (form.value.owner == null && auth.user?.id != null) {
    form.value.owner = Number(auth.user.id)
  }
}

const formatDate = (value) => {
  if (!value) return '-'
  if (typeof value === 'string') return value.slice(0, 10)
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toISOString().slice(0, 10)
}

const fetchAccount = async () => {
  if (!accountId.value) return
  const res = await api.get(`/accounts/${accountId.value}/`)
  const data = res.data || {}
  form.value = {
    full_name: data.full_name || '',
    short_name: data.short_name || '',
    customer_level: data.customer_level != null ? Number(data.customer_level) : null,
    industry: data.industry || '',
    enterprise_nature: data.enterprise_nature != null ? Number(data.enterprise_nature) : null,
    scale: data.scale || '',
    credit_code: data.credit_code || '',
    address: data.address || '',
    phone: data.phone || '',
    website: data.website || '',
    status: data.status || 'active',
    region: data.region != null ? Number(data.region) : null,
    owner: data.owner != null ? Number(data.owner) : null
  }
  audit.value = {
    created_by_name: data.created_by_name || '',
    created_at: data.created_at || '',
    updated_by_name: data.updated_by_name || '',
    updated_at: data.updated_at || ''
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
      website: form.value.website || '',
      region: form.value.region != null ? Number(form.value.region) : null,
      owner: form.value.owner != null ? Number(form.value.owner) : null
    }
    if (isNew.value) {
      const res = await api.post('/accounts/', payload)
      const created = res.data
      success.value = '客户已保存'
      if (created?.id) {
        router.replace(`/accounts/${created.id}`)
      }
    } else {
      await api.patch(`/accounts/${accountId.value}/`, payload)
      success.value = '客户已更新'
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

const fetchContacts = async () => {
  if (!accountId.value) {
    contacts.value = []
    return
  }
  try {
    const res = await api.get('/contacts/', {
      params: { page: 1, page_size: 200, ordering: '-created_at', account: accountId.value }
    })
    contacts.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    contacts.value = []
  }
}

const resetContactForm = () => {
  contactForm.value = {
    name: '',
    title: '',
    phone: '',
    email: '',
    is_key_person: false,
    preference: '',
    remark: ''
  }
  editingContactId.value = null
  contactError.value = ''
  contactSuccess.value = ''
}

const saveContact = async () => {
  if (!accountId.value) return
  if (!contactForm.value.name) {
    contactError.value = '联系人姓名不能为空'
    return
  }
  contactSaving.value = true
  contactError.value = ''
  contactSuccess.value = ''
  try {
    const payload = {
      ...contactForm.value,
      account: accountId.value
    }
    if (editingContactId.value) {
      await api.patch(`/contacts/${editingContactId.value}/`, payload)
      contactSuccess.value = '联系人已更新'
      editingContactId.value = null
    } else {
      await api.post('/contacts/', payload)
      contactSuccess.value = '联系人已添加'
    }
    resetContactForm()
    await fetchContacts()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      contactError.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      contactError.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    contactSaving.value = false
  }
}

const startEditContact = (item) => {
  if (!item) return
  editingContactId.value = item.id
  contactError.value = ''
  contactSuccess.value = ''
  contactForm.value = {
    name: item.name || '',
    title: item.title || '',
    phone: item.phone || '',
    email: item.email || '',
    is_key_person: Boolean(item.is_key_person),
    preference: item.preference || '',
    remark: item.remark || ''
  }
}

const cancelEditContact = () => {
  editingContactId.value = null
  resetContactForm()
}

const openContactModal = (item) => {
  if (!item) return
  modalContact.value = item
  modalForm.value = {
    name: item.name || '',
    title: item.title || '',
    phone: item.phone || '',
    email: item.email || '',
    is_key_person: Boolean(item.is_key_person),
    preference: item.preference || '',
    remark: item.remark || ''
  }
  modalError.value = ''
  modalSaving.value = false
  showContactModal.value = true
}

const closeContactModal = () => {
  showContactModal.value = false
  modalContact.value = null
  modalForm.value = {
    name: '',
    title: '',
    phone: '',
    email: '',
    is_key_person: false,
    preference: '',
    remark: ''
  }
  modalError.value = ''
  modalSaving.value = false
}

const saveContactModal = async () => {
  if (!modalContact.value) return
  if (!modalForm.value.name) {
    modalError.value = '联系人姓名不能为空'
    return
  }
  modalError.value = ''
  modalSaving.value = true
  try {
    const payload = {
      ...modalForm.value,
      account: modalContact.value.account || accountId.value
    }
    await api.patch(`/contacts/${modalContact.value.id}/`, payload)
    await fetchContacts()
    closeContactModal()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      modalError.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      modalError.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    modalSaving.value = false
  }
}

onMounted(async () => {
  if (!auth.user) {
    await auth.fetchMe()
  }
  await fetchLookups()
  await fetchRegions()
  await fetchUsers()
  if (!isNew.value) {
    await fetchAccount()
    await fetchContacts()
  } else {
    applyDefaultOwnerRegion()
  }
})

watch(accountId, async (val) => {
  resetContactForm()
  contactSuccess.value = ''
  if (val) {
    await fetchAccount()
    await fetchContacts()
  } else {
    contacts.value = []
    applyDefaultOwnerRegion()
  }
})
</script>

<style scoped>
.account-detail label {
  font-size: 11px;
}

.account-header-line {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.account-header-line .page-title {
  margin: 0;
}

.account-header-line .detail-meta {
  margin: 0;
}

.account-detail input,
.account-detail select,
.account-detail textarea {
  padding: 6px 8px;
  border-radius: 7px;
  font-size: 13px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
}

.modal-card {
  width: min(720px, calc(100% - 32px));
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 18px 60px rgba(15, 23, 42, 0.18);
  padding: 18px 20px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}
</style>
