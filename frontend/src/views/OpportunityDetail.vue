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
            <label>阶段</label>
            <select v-model="opportunity.stage">
              <option v-for="s in stages" :key="s.value" :value="s.value">{{ s.label }}</option>
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
            <label>成交概率%</label>
            <input v-model.number="opportunity.win_probability" type="number" min="0" max="100" />
          </div>
          <div>
            <label>预计金额</label>
            <input v-model.number="opportunity.expected_amount" type="number" />
          </div>
          <div>
            <label>预计成交时间</label>
            <input v-model="opportunity.expected_close_date" type="date" />
          </div>
          <div>
            <label>实际成交金额</label>
            <input v-model.number="opportunity.actual_amount" type="number" />
          </div>
          <div>
            <label>实际成交时间</label>
            <input v-model="opportunity.actual_close_date" type="date" />
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
            <label>商机分类</label>
            <select v-model="opportunity.opportunity_category">
              <option :value="null">未设置</option>
              <option v-for="opt in lookupOptions.opportunity_category" :key="opt.id" :value="opt.id">
                {{ opt.name }}
              </option>
            </select>
          </div>
          <div>
            <label>线索来源</label>
            <select v-model="opportunity.lead_source">
              <option :value="null">未设置</option>
              <option v-for="opt in lookupOptions.lead_source" :key="opt.id" :value="opt.id">
                {{ opt.name }}
              </option>
            </select>
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
            <label>跟进方式</label>
            <select v-model="followupForm.activity_type">
              <option v-for="t in followupTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
          <div>
            <label>跟进主题</label>
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
          <button class="button" :disabled="followupSaving" @click="createFollowup">
            {{ followupSaving ? '保存中...' : '保存跟进' }}
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
              <th>方式</th>
              <th>主题</th>
              <th>时间</th>
              <th>内容</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in activities" :key="item.id">
              <td>{{ item.activity_type }}</td>
              <td>{{ item.subject }}</td>
              <td>{{ item.due_at || '-' }}</td>
              <td>{{ item.description || '-' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else style="color: #888;">暂无跟进明细</div>
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
import { computed, onMounted, ref } from 'vue'
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
const activities = ref([])
const attachments = ref([])
const attachmentForm = ref({
  file: null,
  description: ''
})
const uploading = ref(false)
const uploadError = ref('')
const toLocalDateTime = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60000
  return new Date(now.getTime() - offset).toISOString().slice(0, 16)
}

const followupForm = ref({
  activity_type: 'internal',
  subject: '',
  description: '',
  due_at: toLocalDateTime()
})
const followupSaving = ref(false)
const followupError = ref('')
const followupSuccess = ref('')
const goBack = () => router.back()

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

const followupTypes = [
  { value: 'call', label: '电话' },
  { value: 'meeting', label: '会议' },
  { value: 'email', label: '邮件' },
  { value: 'visit', label: '拜访' },
  { value: 'internal', label: '内部穿透' }
]

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

const ownerLabel = (item) => {
  if (!item) return ''
  return item.owner_name || item.owner || ''
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

const fetchDetail = async () => {
  const res = await api.get(`/opportunities/${props.id}/`)
  opportunity.value = res.data
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

const createFollowup = async () => {
  if (!followupForm.value.subject) {
    followupError.value = '跟进主题不能为空'
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
    await api.post('/activities/', payload)
    followupForm.value = { activity_type: 'internal', subject: '', description: '', due_at: toLocalDateTime() }
    followupSuccess.value = '跟进已保存'
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
  await fetchActivities()
  await fetchAttachments()
})
</script>
