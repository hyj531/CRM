<template>
  <div class="opportunity-detail">
    <div v-if="opportunity">
      <div class="detail-header">
        <div class="detail-title-wrap">
          <button class="back-button" type="button" @click="goBack" aria-label="返回">←</button>
          <div class="detail-title">{{ opportunity.opportunity_name }}</div>
          <div class="detail-meta">
            <span :class="['badge', stageBadgeClass(opportunity.stage)]">{{ stageLabel(opportunity.stage) }}</span>
            <span>客户：{{ opportunity.account_name || '-' }}</span>
            <span>区域：{{ opportunity.region_name || '-' }}</span>
            <span>负责人：{{ opportunity.owner_name || opportunity.owner }}</span>
            <span>预计金额：{{ opportunity.expected_amount || '-' }}</span>
            <span>成交概率：{{ opportunity.win_probability || 0 }}%</span>
            <span>阶段停留：{{ opportunity.stage_stay_days || 0 }}天</span>
            <span>创建人：{{ opportunity.created_by_name || '-' }}</span>
            <span>创建日期：{{ formatDate(opportunity.created_at) }}</span>
            <span>更新人：{{ opportunity.updated_by_name || '-' }}</span>
            <span>更新日期：{{ formatDate(opportunity.updated_at) }}</span>
          </div>
        </div>
        <div class="page-actions">
          <button class="button" @click="save">保存</button>
        </div>
      </div>

      <div v-if="saved" style="margin-bottom: 10px; color: #2b8a3e;">已保存</div>
      <div v-if="error" style="margin-bottom: 10px; color: #c92a2a;">{{ error }}</div>

      <div class="card">
        <div class="section-title">核心信息</div>
        <div class="form-grid">
          <div>
            <label>商机名称</label>
            <input v-model="opportunity.opportunity_name" />
          </div>
          <div>
            <label>客户</label>
            <div ref="accountPickerRef" class="account-picker">
              <div class="account-search">
                <input
                  v-model="accountQuery"
                  placeholder="输入客户全称/简称，自动搜索"
                  @focus="handleAccountFocus"
                  @blur="handleAccountBlur"
                />
                <button class="button secondary" type="button" @click="triggerAccountSearch">搜索</button>
                <button v-if="opportunity.account" class="button secondary" type="button" @click="clearAccount">
                  清除
                </button>
              </div>
              <div v-if="showAccountDropdown && accountSearchHint" class="account-hint">{{ accountSearchHint }}</div>
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
                  @mousedown.prevent="selectAccount(acc)"
                >
                  {{ acc.full_name }}{{ acc.short_name ? `（${acc.short_name}）` : '' }}
                </button>
              </div>
            </div>
          </div>
          <div>
            <label>阶段</label>
            <select v-model="opportunity.stage">
              <option v-for="s in stages" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
          <div>
            <label>预计金额</label>
            <input v-model.number="opportunity.expected_amount" type="number" />
          </div>
          <div>
            <label>成交概率%</label>
            <input v-model.number="opportunity.win_probability" type="number" min="0" max="100" />
          </div>
          <div>
            <label>预计成交时间</label>
            <input v-model="opportunity.expected_close_date" type="date" />
          </div>
          <div>
            <label>商机分类</label>
            <select v-model="opportunity.opportunity_category">
              <option :value="null">未设置</option>
              <option v-for="opt in lookupOptions.opportunity_category" :key="opt.id" :value="opt.id">
                {{ opt.name }}
              </option>
            </select>
          </div>
          <div>
            <label>企业性质</label>
            <select v-model="opportunity.enterprise_nature">
              <option :value="null">未设置</option>
              <option v-for="opt in lookupOptions.enterprise_nature" :key="opt.id" :value="opt.id">
                {{ opt.name }}
              </option>
            </select>
          </div>
          <div>
            <label>所属区域</label>
            <select v-model.number="opportunity.region">
              <option :value="null">未设置</option>
              <option v-for="region in regions" :key="region.id" :value="region.id">
                {{ region.name || region.code || `ID ${region.id}` }}
              </option>
            </select>
          </div>
          <div>
            <label>负责人</label>
            <select v-if="canAssign" v-model.number="opportunity.owner">
              <option v-if="!users.length" :value="opportunity.owner">{{ ownerLabel(opportunity) }}</option>
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
            </select>
            <input v-else :value="ownerLabel(opportunity)" disabled />
            <div v-if="usersError" style="font-size: 12px; color: #c92a2a;">{{ usersError }}</div>
          </div>
          <div>
            <label>实际成交金额</label>
            <input v-model.number="opportunity.actual_amount" type="number" />
          </div>
          <div>
            <label>实际成交时间</label>
            <input v-model="opportunity.actual_close_date" type="date" />
          </div>
          <div style="grid-column: 1 / -1;">
            <label>备注</label>
            <textarea v-model="opportunity.remark" rows="3"></textarea>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="section-title">新建跟进</div>
        <div class="form-grid">
          <div>
            <label>跟进目标</label>
            <input v-model="followupForm.subject" placeholder="例如：需求确认/方案沟通" />
          </div>
          <div>
            <label>跟进时间</label>
            <input v-model="followupForm.due_at" type="datetime-local" />
          </div>
        </div>
        <div style="margin-top: 10px;">
          <label>跟进内容</label>
          <textarea v-model="followupForm.description" rows="4"></textarea>
        </div>
        <div style="margin-top: 10px;">
          <button class="button" :disabled="followupSaving" @click="saveFollowup">
            {{ followupSaving ? '保存中...' : (editingActivityId ? '保存修改' : '保存跟进') }}
          </button>
          <button
            v-if="editingActivityId"
            class="button secondary"
            style="margin-left: 8px;"
            @click="cancelEditFollowup"
          >
            取消编辑
          </button>
          <span v-if="followupSuccess" style="margin-left: 10px; color: #2b8a3e;">
            {{ followupSuccess }}
          </span>
          <span v-if="followupError" style="margin-left: 10px; color: #c92a2a;">
            {{ followupError }}
          </span>
        </div>
      </div>

      <div class="card">
        <div class="section-title">跟进明细</div>
        <table class="table" v-if="activities.length">
          <thead>
            <tr>
              <th>目标</th>
              <th>时间</th>
              <th>内容</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in activities" :key="item.id">
              <td>
                <button class="link-button" type="button" @click="openFollowupModal(item)">
                  {{ item.subject }}
                </button>
              </td>
              <td>{{ formatDate(item.due_at) }}</td>
              <td>{{ item.description || '-' }}</td>
              <td>
                <button
                  v-if="canEditActivity"
                  class="button secondary small"
                  @click="startEditFollowup(item)"
                >
                  编辑
                </button>
                <button
                  v-if="canDeleteActivity"
                  class="button secondary small"
                  @click="deleteFollowup(item.id)"
                >
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else style="color: #888;">暂无跟进明细</div>
      </div>

      <div v-if="showFollowupModal" class="modal-backdrop">
        <div class="modal-card">
          <div class="modal-header">
            <div class="modal-title">跟进详情</div>
            <button class="button secondary small" type="button" @click="closeFollowupModal">关闭</button>
          </div>
          <div class="form-grid">
            <div>
              <label>跟进目标</label>
              <input v-model="modalForm.subject" :disabled="!canEditActivity" />
            </div>
            <div>
              <label>跟进时间</label>
              <input v-model="modalForm.due_at" type="datetime-local" :disabled="!canEditActivity" />
            </div>
          </div>
          <div style="margin-top: 10px;">
            <label>跟进内容</label>
            <textarea v-model="modalForm.description" rows="4" :disabled="!canEditActivity"></textarea>
          </div>
          <div class="detail-meta" style="margin-top: 10px;">
            <span>创建人：{{ modalActivity?.created_by_name || '-' }}</span>
            <span>创建日期：{{ formatDate(modalActivity?.created_at) }}</span>
            <span>更新人：{{ modalActivity?.updated_by_name || '-' }}</span>
            <span>更新日期：{{ formatDate(modalActivity?.updated_at) }}</span>
          </div>
          <div style="margin-top: 12px;">
            <button
              v-if="canEditActivity"
              class="button"
              type="button"
              :disabled="modalSaving"
              @click="saveModalFollowup"
            >
              {{ modalSaving ? '保存中...' : '保存' }}
            </button>
            <button class="button secondary" type="button" style="margin-left: 8px;" @click="closeFollowupModal">
              关闭
            </button>
            <span v-if="modalError" style="margin-left: 10px; color: #c92a2a;">{{ modalError }}</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="section-title">附件</div>
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
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const props = defineProps({
  id: String
})

const opportunity = ref(null)
const router = useRouter()
const saved = ref(false)
const error = ref('')
const auth = useAuthStore()
const canAssign = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.opportunity?.update))
const users = ref([])
const usersError = ref('')
const usersLoading = ref(false)
const regions = ref([])
const accountPickerRef = ref(null)
const accountOptions = ref([])
const accountQuery = ref('')
const accountLoading = ref(false)
const selectedAccount = ref(null)
const accountFocused = ref(false)
const activities = ref([])
const attachments = ref([])
const attachmentForm = ref({
  file: null,
  description: ''
})
const uploading = ref(false)
const uploadError = ref('')
let searchTimer = null
let accountBlurTimer = null
const toLocalDateTime = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - offset).toISOString().slice(0, 16)
}

const formatDate = (value) => {
  if (!value) return '-'
  if (typeof value === 'string') {
    return value.slice(0, 10)
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toISOString().slice(0, 10)
}

const followupForm = ref({
  activity_type: 'internal',
  subject: '',
  description: '',
  due_at: toLocalDateTime()
})
const editingActivityId = ref(null)
const followupSaving = ref(false)
const followupError = ref('')
const followupSuccess = ref('')
const showFollowupModal = ref(false)
const modalActivity = ref(null)
const modalForm = ref({
  activity_type: 'internal',
  subject: '',
  description: '',
  due_at: ''
})
const modalSaving = ref(false)
const modalError = ref('')
const goBack = () => router.back()

const stages = [
  { value: 'lead', label: '线索阶段' },
  { value: 'opportunity', label: '商机阶段' },
  { value: 'demand', label: '需求引导' },
  { value: 'solution', label: '方案阶段' },
  { value: 'bid', label: '投标阶段' },
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

const followupTypes = [
  { value: 'call', label: '电话' },
  { value: 'meeting', label: '会议' },
  { value: 'email', label: '邮件' },
  { value: 'visit', label: '拜访' },
  { value: 'internal', label: '内部穿透' }
]

const canEditActivity = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.activity?.update))
const canDeleteActivity = computed(() => Boolean(auth.user?.is_staff || auth.user?.permissions?.activity?.delete))

const stageLabel = (stage) => {
  const map = {
    lead: '线索阶段',
    opportunity: '商机阶段',
    demand: '需求引导',
    solution: '方案阶段',
    bid: '投标阶段',
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

const ownerLabel = (item) => {
  if (!item) return ''
  return item.owner_name || item.owner || ''
}

const accountLabel = (acc) => {
  if (!acc) return ''
  return acc.full_name || acc.short_name || acc.name || `ID ${acc.id}`
}

const accountSearchHint = computed(() => {
  const query = accountQuery.value.trim()
  if (!query) return ''
  if (query.length < 2) return '请输入至少 2 个字'
  return ''
})

const selectedAccountLabel = computed(() => {
  const acc = selectedAccount.value
  if (!opportunity.value?.account || !acc) return ''
  return `${acc.full_name || acc.short_name || `ID ${acc.id}`}${acc.short_name ? `（${acc.short_name}）` : ''}`
})

const showAccountDropdown = computed(() => accountFocused.value && accountQuery.value.trim().length > 0)

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
  if (!id) return null
  try {
    const res = await api.get(`/accounts/${id}/`)
    return res.data
  } catch (err) {
    return null
  }
}

const fetchDetail = async () => {
  const res = await api.get(`/opportunities/${props.id}/`)
  opportunity.value = res.data
  if (opportunity.value?.account) {
    const acc = await fetchAccountById(opportunity.value.account)
    if (acc) {
      selectedAccount.value = acc
      accountQuery.value = accountLabel(acc)
      accountOptions.value = [acc]
    } else {
      selectedAccount.value = null
      accountQuery.value = ''
      accountOptions.value = []
    }
  } else {
    selectedAccount.value = null
    accountQuery.value = ''
    accountOptions.value = []
  }
}

const fetchUsers = async () => {
  if (!canAssign.value) return
  usersLoading.value = true
  usersError.value = ''
  try {
    const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
    users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    users.value = []
    usersError.value = '负责人列表加载失败'
  } finally {
    usersLoading.value = false
  }
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const triggerAccountSearch = () => {
  const query = accountQuery.value.trim()
  if (!query || query.length < 2) return
  loadAccounts(query)
}

const handleAccountFocus = () => {
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
    accountBlurTimer = null
  }
  accountFocused.value = true
}

const handleAccountBlur = (event) => {
  const nextTarget = event?.relatedTarget
  if (nextTarget && accountPickerRef.value?.contains(nextTarget)) {
    return
  }
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
  }
  accountBlurTimer = setTimeout(() => {
    const activeElement = document.activeElement
    if (activeElement && accountPickerRef.value?.contains(activeElement)) {
      return
    }
    accountFocused.value = false
    accountBlurTimer = null
  }, 120)
}

const selectAccount = (acc) => {
  if (!opportunity.value) return
  opportunity.value.account = acc.id
  opportunity.value.account_name = accountLabel(acc)
  selectedAccount.value = acc
  accountQuery.value = accountLabel(acc)
  accountFocused.value = false
  accountOptions.value = [acc]
}

const clearAccount = () => {
  if (!opportunity.value) return
  opportunity.value.account = null
  opportunity.value.account_name = ''
  selectedAccount.value = null
  accountQuery.value = ''
  accountOptions.value = []
  accountFocused.value = false
}

const fetchActivities = async () => {
  const res = await api.get('/activities/', {
    params: { opportunity: props.id, ordering: '-due_at', page: 1, page_size: 50 }
  })
  activities.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchAttachments = async () => {
  const res = await api.get('/opportunity-attachments/', {
    params: { opportunity: props.id, ordering: '-created_at', page: 1, page_size: 50 }
  })
  attachments.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const onFileChange = (event) => {
  const file = event.target.files && event.target.files[0]
  attachmentForm.value.file = file || null
  uploadError.value = ''
}

const uploadAttachment = async () => {
  if (!attachmentForm.value.file) return
  uploading.value = true
  uploadError.value = ''
  try {
    const formData = new FormData()
    formData.append('opportunity', String(props.id))
    formData.append('file', attachmentForm.value.file)
    if (attachmentForm.value.description) {
      formData.append('description', attachmentForm.value.description)
    }
    await api.post('/opportunity-attachments/', formData)
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

const startEditFollowup = (item) => {
  editingActivityId.value = item.id
  followupForm.value = {
    activity_type: item.activity_type || 'internal',
    subject: item.subject || '',
    description: item.description || '',
    due_at: item.due_at ? item.due_at.slice(0, 16) : toLocalDateTime()
  }
  followupError.value = ''
  followupSuccess.value = ''
}

const cancelEditFollowup = () => {
  editingActivityId.value = null
  followupForm.value = { activity_type: 'internal', subject: '', description: '', due_at: toLocalDateTime() }
  followupError.value = ''
  followupSuccess.value = ''
}

const openFollowupModal = (item) => {
  modalActivity.value = item
  modalForm.value = {
    activity_type: item.activity_type || 'internal',
    subject: item.subject || '',
    description: item.description || '',
    due_at: item.due_at ? item.due_at.slice(0, 16) : ''
  }
  modalError.value = ''
  modalSaving.value = false
  showFollowupModal.value = true
}

const closeFollowupModal = () => {
  showFollowupModal.value = false
  modalActivity.value = null
  modalForm.value = { activity_type: 'internal', subject: '', description: '', due_at: '' }
  modalError.value = ''
  modalSaving.value = false
}

const saveModalFollowup = async () => {
  if (!modalActivity.value) return
  if (!modalForm.value.subject) {
    modalError.value = '跟进目标不能为空'
    return
  }
  modalError.value = ''
  modalSaving.value = true
  try {
    const payload = {
      activity_type: modalForm.value.activity_type,
      subject: modalForm.value.subject,
      description: modalForm.value.description,
      opportunity: Number(props.id),
      due_at: modalForm.value.due_at || null
    }
    await api.patch(`/activities/${modalActivity.value.id}/`, payload)
    await fetchActivities()
    closeFollowupModal()
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      modalError.value = '无编辑权限'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        modalError.value = messages || '保存失败，请检查必填项或后端服务'
      } else {
        modalError.value = '保存失败，请检查必填项或后端服务'
      }
    }
  } finally {
    modalSaving.value = false
  }
}

const saveFollowup = async () => {
  if (!followupForm.value.subject) {
    followupError.value = '跟进目标不能为空'
    return
  }
  followupError.value = ''
  followupSuccess.value = ''
  followupSaving.value = true
  try {
    const payload = {
      activity_type: followupForm.value.activity_type,
      subject: followupForm.value.subject,
      description: followupForm.value.description,
      opportunity: Number(props.id),
      due_at: followupForm.value.due_at || null
    }
    if (editingActivityId.value) {
      await api.patch(`/activities/${editingActivityId.value}/`, payload)
      followupSuccess.value = '跟进已更新'
      editingActivityId.value = null
    } else {
      await api.post('/activities/', payload)
      followupSuccess.value = '跟进已保存'
    }
    followupForm.value = { activity_type: 'internal', subject: '', description: '', due_at: toLocalDateTime() }
    await fetchActivities()
  } catch (err) {
    const status = err.response?.status
    if (status === 401) {
      followupError.value = '登录已过期，请重新登录'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        followupError.value = messages || '保存失败，请检查必填项或后端服务'
      } else {
        followupError.value = '保存失败，请检查必填项或后端服务'
      }
    }
  } finally {
    followupSaving.value = false
  }
}

const deleteFollowup = async (id) => {
  if (!confirm('确认删除该跟进记录？')) return
  followupError.value = ''
  followupSuccess.value = ''
  try {
    await api.delete(`/activities/${id}/`)
    if (editingActivityId.value === id) {
      cancelEditFollowup()
    }
    followupSuccess.value = '跟进已删除'
    await fetchActivities()
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      followupError.value = '无删除权限'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        followupError.value = detail.detail || '删除失败，请检查权限或后端服务'
      } else {
        followupError.value = '删除失败，请检查权限或后端服务'
      }
    }
  }
}

const save = async () => {
  if (!opportunity.value || !opportunity.value.opportunity_name) {
    error.value = '商机名称不能为空'
    return
  }
  error.value = ''
  saved.value = false
  const toNullableInt = (value) => {
    if (value === '' || value === null || value === undefined) {
      return null
    }
    const num = Number(value)
    return Number.isNaN(num) ? null : num
  }
  const payload = {
    opportunity_name: opportunity.value.opportunity_name,
    account: toNullableInt(opportunity.value.account),
    stage: opportunity.value.stage,
    win_probability: opportunity.value.win_probability,
    expected_amount: opportunity.value.expected_amount,
    expected_close_date: opportunity.value.expected_close_date,
    actual_amount: opportunity.value.actual_amount,
    actual_close_date: opportunity.value.actual_close_date,
    enterprise_nature: toNullableInt(opportunity.value.enterprise_nature),
    opportunity_category: toNullableInt(opportunity.value.opportunity_category),
    lead_source: toNullableInt(opportunity.value.lead_source),
    latest_followup_at: opportunity.value.latest_followup_at,
    latest_followup_note: opportunity.value.latest_followup_note,
    remark: opportunity.value.remark,
    region: toNullableInt(opportunity.value.region),
  }
  if (canAssign.value) {
    payload.owner = toNullableInt(opportunity.value.owner)
  }
  await api.patch(`/opportunities/${props.id}/`, payload)
  saved.value = true
}

onMounted(async () => {
  await fetchLookups()
  await fetchDetail()
  await fetchUsers()
  await fetchRegions()
  await fetchActivities()
  await fetchAttachments()
})

watch(accountQuery, (value) => {
  const query = value.trim()
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  if (!query || query.length < 2) {
    if (!query) {
      accountOptions.value = selectedAccount.value ? [selectedAccount.value] : []
    }
    return
  }
  searchTimer = setTimeout(() => {
    loadAccounts(query)
  }, 300)
})

onBeforeUnmount(() => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
    accountBlurTimer = null
  }
})
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 1000;
}

.modal-card {
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
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
}
</style>
