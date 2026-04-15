<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">审批配置</h1>
        <div class="page-subtitle">支持多区域通用流程，节点按角色或用户解析审批人</div>
      </div>
    </div>

    <div v-if="error" class="approval-config-alert error">{{ error }}</div>
    <div v-if="success" class="approval-config-alert success">{{ success }}</div>

    <div v-if="!canManage" class="card">
      当前账号无审批配置权限，请联系管理员开通。
    </div>

    <div v-else class="approval-config-grid">
      <div class="card approval-config-list">
        <div class="section-title">流程列表</div>
        <div class="approval-config-toolbar">
          <select v-model="targetType">
            <option value="contract">合同审批</option>
            <option value="invoice">开票审批</option>
          </select>
          <button class="button secondary" @click="newFlow">新建流程</button>
        </div>
        <div class="approval-flow-items">
          <button
            v-for="flow in flows"
            :key="flow.id"
            class="approval-flow-item"
            :class="{ active: selectedFlowId === flow.id }"
            @click="selectFlow(flow)"
          >
            <div class="flow-title">{{ flow.name }}</div>
            <div class="flow-meta">
              <span>{{ flow.scope_mode === 'all_regions' ? '全部区域' : `指定区域(${flow.region_ids?.length || 0})` }}</span>
              <span :class="['badge', flowStatusBadge(flow)]">{{ flowStatusLabel(flow) }}</span>
            </div>
          </button>
          <div v-if="!flows.length" class="empty-line">暂无流程</div>
        </div>
      </div>

      <div class="card approval-config-editor">
        <div class="section-title">流程编辑</div>
        <div class="form-grid two-cols">
          <div>
            <label>流程名称</label>
            <input v-model.trim="form.name" placeholder="例如：合同审批主流程" />
          </div>
          <div>
            <label>适用范围</label>
            <select v-model="form.scope_mode">
              <option value="all_regions">全部区域</option>
              <option value="selected_regions">指定区域</option>
            </select>
          </div>
          <div>
            <label>流程状态</label>
            <select v-model="form.status">
              <option value="draft">草稿</option>
              <option value="published">已发布</option>
              <option value="archived">已归档</option>
            </select>
          </div>
          <div>
            <label>优先级（越大越优先）</label>
            <input v-model.number="form.priority" type="number" min="0" />
          </div>
          <div>
            <label>生效开始时间</label>
            <input v-model="form.effective_from" type="datetime-local" />
          </div>
          <div>
            <label>生效结束时间</label>
            <input v-model="form.effective_to" type="datetime-local" />
          </div>
          <div v-if="form.scope_mode === 'selected_regions'" class="full">
            <label>适用区域（可多选）</label>
            <select v-model="form.region_ids" multiple size="6">
              <option v-for="item in regions" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
          </div>
        </div>

        <div class="section-title" style="margin-top: 14px;">审批节点</div>
        <table class="table">
          <thead>
            <tr>
              <th style="width: 70px;">顺序</th>
              <th>节点名称</th>
              <th style="width: 120px;">类型</th>
              <th style="width: 120px;">作用域</th>
              <th>审批角色/审批人</th>
              <th style="width: 180px;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(step, index) in form.steps" :key="step.local_key">
              <td>{{ index + 1 }}</td>
              <td><input v-model.trim="step.name" placeholder="节点名称" /></td>
              <td>
                <select v-model="step.assignee_type" @change="onAssigneeTypeChange(step)">
                  <option value="role">角色</option>
                  <option value="user">用户</option>
                </select>
              </td>
              <td>
                <select v-model="step.assignee_scope" :disabled="step.assignee_type === 'user'">
                  <option value="region">按区域</option>
                  <option value="global">全局</option>
                </select>
              </td>
              <td>
                <select v-if="step.assignee_type === 'role'" v-model="step.approver_role">
                  <option :value="null">请选择角色</option>
                  <option v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</option>
                </select>
                <select v-else v-model="step.approver_user">
                  <option :value="null">请选择用户</option>
                  <option v-for="user in users" :key="user.id" :value="user.id">{{ user.username }}</option>
                </select>
              </td>
              <td class="step-actions">
                <button class="button secondary" :disabled="index === 0" @click="moveStep(index, -1)">上移</button>
                <button class="button secondary" :disabled="index === form.steps.length - 1" @click="moveStep(index, 1)">下移</button>
                <button class="button secondary" @click="removeStep(index)">删除</button>
              </td>
            </tr>
            <tr v-if="!form.steps.length">
              <td colspan="6" class="empty-line">请先新增审批节点</td>
            </tr>
          </tbody>
        </table>
        <div class="step-add">
          <button class="button secondary" @click="addStep">新增节点</button>
        </div>

        <div class="approval-config-actions">
          <button class="button" :disabled="saving" @click="saveFlow">{{ saving ? '保存中...' : '保存配置' }}</button>
          <button class="button secondary" :disabled="publishing || !selectedFlowId" @click="publishFlow">
            {{ publishing ? '发布中...' : '发布生效' }}
          </button>
          <button class="button secondary" :disabled="previewing || !selectedFlowId" @click="previewAssignees">
            {{ previewing ? '预览中...' : '预览审批人' }}
          </button>
          <select v-model="previewRegionId">
            <option value="">预览全部区域</option>
            <option v-for="item in regions" :key="item.id" :value="String(item.id)">
              {{ item.name }}
            </option>
          </select>
        </div>

        <div v-if="previewItems.length" class="preview-block">
          <div v-for="item in previewItems" :key="item.region_id" class="preview-region">
            <div class="preview-title">区域：{{ item.region_name }}</div>
            <table class="table">
              <thead>
                <tr>
                  <th style="width: 80px;">步骤</th>
                  <th>节点名称</th>
                  <th>命中审批人</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in item.steps" :key="`${item.region_id}-${row.step_id}`">
                  <td>{{ row.step_order }}</td>
                  <td>{{ row.step_name }}</td>
                  <td>
                    <span v-if="row.matched_count">
                      {{ row.matched.map((x) => x.username).join('，') }}
                    </span>
                    <span v-else class="warn-text">未命中</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canManage = computed(() => Boolean(auth.user?.can_manage_approval_config || auth.user?.is_staff || auth.user?.is_superuser))

const targetType = ref('contract')
const flows = ref([])
const regions = ref([])
const roles = ref([])
const users = ref([])
const selectedFlowId = ref(null)
const previewRegionId = ref('')
const previewItems = ref([])

const error = ref('')
const success = ref('')
const saving = ref(false)
const publishing = ref(false)
const previewing = ref(false)

let localKeySeed = 1
const nextLocalKey = () => `step-${Date.now()}-${localKeySeed++}`

const createStep = () => ({
  id: null,
  local_key: nextLocalKey(),
  name: '',
  assignee_type: 'role',
  assignee_scope: 'region',
  approver_role: null,
  approver_user: null
})

const createForm = () => ({
  id: null,
  name: '',
  target_type: targetType.value,
  scope_mode: 'all_regions',
  region_ids: [],
  status: 'draft',
  priority: 100,
  effective_from: '',
  effective_to: '',
  is_active: false,
  steps: [createStep()]
})

const flowStatusValue = (flow) => {
  if (flow?.status) return flow.status
  return flow?.is_active ? 'published' : 'draft'
}

const flowStatusLabel = (flow) => {
  const map = {
    draft: '草稿',
    published: '已发布',
    archived: '已归档'
  }
  return map[flowStatusValue(flow)] || '草稿'
}

const flowStatusBadge = (flow) => {
  const value = flowStatusValue(flow)
  if (value === 'published') return 'green'
  if (value === 'archived') return 'orange'
  return 'gray'
}

const toDatetimeLocalInput = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const toApiDatetime = (value) => {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

const form = ref(createForm())

const normalizeArray = (resp) => {
  const data = resp?.data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data)) return data
  return []
}

const resetMessages = () => {
  error.value = ''
  success.value = ''
}

const hydrateFlowToForm = (flow) => {
  form.value = {
    id: flow.id,
    name: flow.name || '',
    target_type: flow.target_type || targetType.value,
    scope_mode: flow.scope_mode || 'all_regions',
    region_ids: Array.isArray(flow.region_ids) ? flow.region_ids.map((x) => Number(x)) : [],
    status: flowStatusValue(flow),
    priority: Number.isFinite(Number(flow.priority)) ? Number(flow.priority) : 100,
    effective_from: toDatetimeLocalInput(flow.effective_from),
    effective_to: toDatetimeLocalInput(flow.effective_to),
    is_active: Boolean(flow.is_active),
    steps: Array.isArray(flow.steps) && flow.steps.length
      ? flow.steps.map((step) => ({
          id: step.id,
          local_key: nextLocalKey(),
          name: step.name || '',
          assignee_type: step.assignee_type || 'role',
          assignee_scope: step.assignee_scope || 'region',
          approver_role: step.approver_role != null ? Number(step.approver_role) : null,
          approver_user: step.approver_user != null ? Number(step.approver_user) : null
        }))
      : [createStep()]
  }
}

const loadMeta = async () => {
  const [regionsResp, rolesResp, usersResp] = await Promise.all([
    api.get('/regions/', { params: { page: 1, page_size: 1000, ordering: 'name' } }),
    api.get('/roles/', { params: { page: 1, page_size: 1000, ordering: 'name' } }),
    api.get('/users/', { params: { page: 1, page_size: 1000, ordering: 'username' } })
  ])
  regions.value = normalizeArray(regionsResp)
  roles.value = normalizeArray(rolesResp)
  users.value = normalizeArray(usersResp)
}

const loadFlows = async () => {
  const resp = await api.get('/approval-flow-configs/', {
    params: { target_type: targetType.value }
  })
  flows.value = normalizeArray(resp)
  if (selectedFlowId.value) {
    const selected = flows.value.find((item) => item.id === selectedFlowId.value)
    if (selected) {
      hydrateFlowToForm(selected)
      return
    }
  }
  selectedFlowId.value = null
  form.value = createForm()
}

const selectFlow = (flow) => {
  resetMessages()
  selectedFlowId.value = flow.id
  previewItems.value = []
  hydrateFlowToForm(flow)
}

const newFlow = () => {
  resetMessages()
  selectedFlowId.value = null
  previewItems.value = []
  form.value = createForm()
}

const addStep = () => {
  form.value.steps.push(createStep())
}

const removeStep = (index) => {
  form.value.steps.splice(index, 1)
  if (!form.value.steps.length) {
    form.value.steps.push(createStep())
  }
}

const moveStep = (index, delta) => {
  const target = index + delta
  if (target < 0 || target >= form.value.steps.length) return
  const tmp = form.value.steps[index]
  form.value.steps[index] = form.value.steps[target]
  form.value.steps[target] = tmp
}

const onAssigneeTypeChange = (step) => {
  if (step.assignee_type === 'user') {
    step.assignee_scope = 'region'
    step.approver_role = null
  } else {
    step.approver_user = null
  }
}

const buildPayload = () => ({
  name: form.value.name,
  target_type: targetType.value,
  scope_mode: form.value.scope_mode,
  status: form.value.status,
  priority: Number.isFinite(Number(form.value.priority)) ? Number(form.value.priority) : 100,
  effective_from: toApiDatetime(form.value.effective_from),
  effective_to: toApiDatetime(form.value.effective_to),
  region_ids: form.value.scope_mode === 'selected_regions'
    ? form.value.region_ids.map((x) => Number(x))
    : [],
  is_active: form.value.status === 'published',
  steps: form.value.steps.map((step, index) => ({
    id: step.id || undefined,
    order: index + 1,
    name: step.name,
    assignee_type: step.assignee_type,
    assignee_scope: step.assignee_type === 'user' ? 'region' : step.assignee_scope,
    approver_role: step.assignee_type === 'role' ? step.approver_role : null,
    approver_user: step.assignee_type === 'user' ? step.approver_user : null
  }))
})

const saveFlow = async () => {
  resetMessages()
  saving.value = true
  try {
    const payload = buildPayload()
    let resp
    if (selectedFlowId.value) {
      resp = await api.put(`/approval-flow-configs/${selectedFlowId.value}/`, payload)
    } else {
      resp = await api.post('/approval-flow-configs/', payload)
    }
    success.value = '审批流程已保存'
    selectedFlowId.value = resp.data?.id || selectedFlowId.value
    await loadFlows()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || JSON.stringify(detail)
    } else {
      error.value = '保存失败，请检查配置'
    }
  } finally {
    saving.value = false
  }
}

const publishFlow = async () => {
  if (!selectedFlowId.value) return
  resetMessages()
  publishing.value = true
  try {
    await api.post(`/approval-flow-configs/${selectedFlowId.value}/publish/`)
    success.value = '审批流程已发布'
    await loadFlows()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || JSON.stringify(detail)
    } else {
      error.value = '发布失败，请检查配置'
    }
  } finally {
    publishing.value = false
  }
}

const previewAssignees = async () => {
  if (!selectedFlowId.value) return
  resetMessages()
  previewing.value = true
  try {
    const params = {}
    if (previewRegionId.value) params.region_id = previewRegionId.value
    const resp = await api.get(`/approval-flow-configs/${selectedFlowId.value}/preview-assignees/`, { params })
    previewItems.value = Array.isArray(resp.data?.items) ? resp.data.items : []
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || JSON.stringify(detail)
    } else {
      error.value = '预览失败，请稍后重试'
    }
  } finally {
    previewing.value = false
  }
}

watch(targetType, async () => {
  selectedFlowId.value = null
  previewItems.value = []
  form.value = createForm()
  if (canManage.value) {
    await loadFlows()
  }
})

onMounted(async () => {
  if (!canManage.value) return
  try {
    await loadMeta()
    await loadFlows()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || JSON.stringify(detail)
    } else {
      error.value = '初始化审批配置失败'
    }
  }
})
</script>

<style scoped>
.approval-config-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 14px;
}

.approval-config-alert {
  padding: 10px 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  font-size: 13px;
}

.approval-config-alert.error {
  background: #ffe8e8;
  color: #b42318;
  border: 1px solid #f8c4c4;
}

.approval-config-alert.success {
  background: #e8f8ef;
  color: #0a7a42;
  border: 1px solid #b6e8cb;
}

.approval-config-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.approval-config-toolbar select {
  flex: 1;
}

.approval-flow-items {
  display: grid;
  gap: 8px;
}

.approval-flow-item {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 10px;
  text-align: left;
  padding: 10px;
  cursor: pointer;
}

.approval-flow-item.active {
  border-color: #e5a347;
  box-shadow: inset 0 0 0 1px #e5a347;
}

.flow-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.flow-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #64748b;
  font-size: 12px;
}

.form-grid.two-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.form-grid.two-cols .full {
  grid-column: 1 / -1;
}

.form-grid label {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 4px;
}

.form-grid input,
.form-grid select,
td input,
td select {
  width: 100%;
}

.step-actions {
  display: flex;
  gap: 6px;
}

.step-add {
  margin-top: 10px;
}

.approval-config-actions {
  margin-top: 14px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.preview-block {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}

.preview-region {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px;
}

.preview-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.warn-text {
  color: #b54708;
  font-weight: 600;
}

.empty-line {
  color: #7c879a;
  text-align: center;
  padding: 10px;
}

@media (max-width: 1200px) {
  .approval-config-grid {
    grid-template-columns: 1fr;
  }
}
</style>
