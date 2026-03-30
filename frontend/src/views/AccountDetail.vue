<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ isNew ? '新建客户' : '客户详情' }}</h2>
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
              {{ contactSaving ? '保存中...' : '添加联系人' }}
            </button>
            <button class="button secondary" @click="resetContactForm">清空</button>
          </div>
          <div v-if="contactError" style="color: #c92a2a; margin-top: 8px;">{{ contactError }}</div>
          <div v-if="contactSuccess" style="color: #2b8a3e; margin-top: 8px;">{{ contactSuccess }}</div>
          <div style="margin-top: 12px;">
            <div class="section-title" style="font-size: 13px;">已有联系人 ({{ contacts.length }})</div>
            <div v-if="contacts.length">
              <div v-for="item in contacts" :key="item.id" class="list-row">
                <div>
                  <div class="list-title">{{ item.name }}</div>
                  <div class="list-meta">
                    <span>职位：{{ item.title || '-' }}</span>
                    <span>电话：{{ item.phone || '-' }}</span>
                    <span>邮箱：{{ item.email || '-' }}</span>
                    <span>关键人：{{ item.is_key_person ? '是' : '否' }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else style="padding: 10px 0; color: #888;">暂无联系人</div>
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
    status: data.status || 'active'
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
    await api.post('/contacts/', payload)
    contactSuccess.value = '联系人已添加'
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

onMounted(async () => {
  await fetchLookups()
  if (!isNew.value) {
    await fetchAccount()
    await fetchContacts()
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
  }
})
</script>
