<template>
  <div class="approval-cockpit">
    <div class="cockpit-hero card">
      <div class="hero-main">
        <div class="hero-main-left">
          <button class="button secondary hero-back" @click="goBackSource">返回</button>
          <div class="title-main">{{ targetTitle || '审批实例' }}</div>
          <div :class="['status-pill', `status-${instance?.status || 'pending'}`]">
            {{ instanceStatusLabel(instance?.status) }}
          </div>
          <div class="head-type">{{ targetTypeLabel }}</div>
        </div>
        <div class="hero-main-right">
          <span class="meta-chip">发起人：{{ instance?.started_by_name || '-' }}</span>
          <span class="meta-chip">发起时间：{{ formatValue(instance?.created_at) }}</span>
          <span class="meta-chip">最近动作：{{ latestActionSummary }}</span>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="success" class="alert success">{{ success }}</div>

    <div class="cockpit-main">
      <div class="main-left">
        <div v-if="instance" class="card">
          <div class="section-title">审批信息</div>
          <div class="approval-grid">
            <div v-for="item in targetFieldsForGrid" :key="item.label" class="approval-field">
              <label>{{ item.label }}</label>
              <div class="field-value">{{ formatTargetFieldValue(item.value) }}</div>
            </div>
          </div>
          <div v-if="hasTargetRemark" class="approval-remark">
            <label>{{ targetRemarkField?.label || '备注' }}</label>
            <div class="field-value field-value-remark">{{ formatTargetFieldValue(targetRemarkField?.value) }}</div>
          </div>
        </div>

        <div v-if="instance" class="card">
          <div class="section-title">附件</div>
          <div v-if="attachments.length" class="attachment-list">
            <div v-for="file in attachments" :key="file.id" class="attachment-item">
              <div>
                <div class="attachment-name">{{ file.original_name || '附件' }}</div>
                <div class="attachment-meta">上传人：{{ file.owner_name || '-' }} · {{ formatValue(file.created_at) }}</div>
              </div>
              <a v-if="file.file_url" class="text-link" :href="file.file_url" target="_blank" rel="noopener">查看</a>
            </div>
          </div>
          <div v-else class="empty-text">无附件</div>
        </div>

        <div v-if="instance" class="card">
          <div class="section-title">节点审批记录</div>
          <div v-if="groupedTasks.length">
            <div v-for="group in groupedTasks" :key="`group-${group.step_order}`" class="task-group">
              <div class="task-group-title">步骤{{ group.step_order }} · {{ group.step_name || '-' }}</div>
              <table class="table">
                <thead>
                  <tr>
                    <th>审批人</th>
                    <th>状态</th>
                    <th>处理时间</th>
                    <th>意见</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="task in group.tasks" :key="task.id">
                    <td>{{ task.assignee_name || '-' }}</td>
                    <td>
                      <span :class="['task-status-tag', taskStatusClass(task.status)]">
                        {{ taskStatusLabel(task.status) }}
                      </span>
                    </td>
                    <td>{{ formatValue(task.decided_at) }}</td>
                    <td>{{ task.comment || '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="empty-text">暂无节点记录</div>
        </div>
      </div>

      <div class="main-right">
        <div v-if="instance" class="card timeline-card">
          <div class="section-title">流程时间线</div>
          <div class="timeline-progress">
            <div class="timeline-progress-head">
              <div class="timeline-progress-title">流程进度</div>
              <div class="timeline-progress-meta">{{ finishedStepCount }}/{{ stepGroups.length || 0 }} 步完成</div>
            </div>
            <div class="progress-meter">
              <div class="progress-meter-bar" :style="{ width: `${progressPercent}%` }"></div>
            </div>
            <div class="timeline-step-list">
              <div
                v-for="group in stepGroups"
                :key="`timeline-step-${group.step_order}`"
                :class="['timeline-step-item', `status-${group.status || 'waiting'}`]"
              >
                <div class="timeline-step-main">
                  <span class="timeline-step-order">步骤{{ group.step_order }}</span>
                  <span class="timeline-step-name" :title="group.step_name || '-'">{{ group.step_name || '-' }}</span>
                </div>
                <div class="timeline-step-approvers">
                  审批人：{{ stepApproverLabel(group.step_order) }}
                </div>
                <div class="timeline-step-right">
                  <span class="timeline-step-ratio">{{ group.approved_count }}/{{ group.total_count }}</span>
                  <span class="timeline-step-state">{{ stepStatusLabel(group.status) }}</span>
                </div>
              </div>
              <div v-if="!stepGroups.length" class="step-empty">暂无步骤</div>
            </div>
          </div>
          <div class="timeline-section-title">流程动作</div>
          <div v-if="logs.length" class="timeline">
            <div v-for="log in logs" :key="log.id" class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <div class="timeline-title">
                  {{ actionLabel(log.action) }}
                  <span class="timeline-actor">{{ log.actor_name || '-' }}</span>
                </div>
                <div class="timeline-time">{{ formatValue(log.created_at) }}</div>
                <div v-if="log.comment" class="timeline-comment">备注：{{ log.comment }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty-text">暂无流程日志</div>
        </div>
      </div>
    </div>

    <div v-if="instance" class="card action-bar">
      <div class="action-bar-head">
        <div class="action-bar-title">审批处理</div>
        <div class="action-bar-tip">可操作待办：{{ actionableTasks.length }}</div>
      </div>
      <div class="action-bar-main" :class="{ 'with-task-selector': actionableTasks.length > 1 }">
        <select v-if="actionableTasks.length > 1" v-model="selectedTaskId">
          <option v-for="task in actionableTasks" :key="task.id" :value="String(task.id)">
            {{ task.step_name || '审批节点' }} #{{ task.id }} · {{ task.assignee_name || '-' }}
          </option>
        </select>
        <textarea v-model="comment" rows="2" placeholder="输入审批意见（可选）"></textarea>
        <button class="button" :disabled="decisionLoading || !canApprove" @click="submitDecision(true)">
          {{ decisionLoading ? '处理中...' : approveButtonLabel }}
        </button>
        <button v-if="showRejectButton" class="button secondary" :disabled="decisionLoading || !canReject" @click="submitDecision(false)">
          驳回
        </button>
        <button class="button secondary" :disabled="operationLoading || !canTransfer" @click="openOperation('transfer')">
          转办
        </button>
        <button v-if="showAddSignButton" class="button secondary" :disabled="operationLoading || !canAddSign" @click="openOperation('add_sign')">
          加签
        </button>
      </div>
      <div v-if="!canApprove && !canTransfer && !canAddSign" class="empty-text">当前无可处理审批任务</div>
    </div>

    <div v-if="showOperationDialog" class="modal-mask" @click.self="closeOperationDialog">
      <div class="modal-card operation-modal">
        <div class="modal-head">
          <div class="modal-title">{{ operationDialogTitle }}</div>
          <button class="button secondary modal-close" :disabled="operationLoading" @click="closeOperationDialog">关闭</button>
        </div>
        <div class="modal-body">
          <div class="modal-row">
            <label>目标审批人</label>
            <select v-model="operationAssigneeId" :disabled="operationLoading || userOptionsLoading">
              <option value="">请选择</option>
              <option v-for="userItem in operationCandidateUsers" :key="userItem.id" :value="String(userItem.id)">
                {{ userItem.username }}
              </option>
            </select>
          </div>
          <div class="modal-row">
            <label>备注（可选）</label>
            <textarea
              v-model="operationComment"
              rows="3"
              :placeholder="operationType === 'add_sign' ? '输入加签说明（可选）' : '输入转办说明（可选）'"
              :disabled="operationLoading"
            ></textarea>
          </div>
        </div>
        <div class="modal-actions">
          <button class="button secondary" :disabled="operationLoading" @click="closeOperationDialog">取消</button>
          <button class="button" :disabled="operationLoading || !operationAssigneeId" @click="submitOperation">
            {{ operationLoading ? '处理中...' : operationSubmitLabel }}
          </button>
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

const loading = ref(false)
const error = ref('')
const success = ref('')
const detail = ref(null)
const decisionLoading = ref(false)
const comment = ref('')
const selectedTaskId = ref('')
const showOperationDialog = ref(false)
const operationType = ref('transfer')
const operationAssigneeId = ref('')
const operationComment = ref('')
const operationLoading = ref(false)
const userOptionsLoading = ref(false)
const userOptions = ref([])

const instanceId = computed(() => (route.name === 'approval-instance' ? String(route.params.id || '') : ''))
const taskRouteId = computed(() => (route.name === 'approval-task' ? String(route.params.id || '') : ''))
const preferredTaskId = computed(() => String(route.query.task_id || ''))

const instance = computed(() => detail.value?.instance || null)
const target = computed(() => detail.value?.target || {})
const targetTitle = computed(() => target.value?.title || '')
const targetFields = computed(() => target.value?.fields || [])
const targetRemarkField = computed(() => (
  targetFields.value.find((item) => item?.label === '备注') || null
))
const targetFieldsForGrid = computed(() => (
  targetFields.value.filter((item) => item?.label !== '备注')
))
const hasTargetRemark = computed(() => Boolean(targetRemarkField.value))
const attachments = computed(() => target.value?.attachments || [])
const tasks = computed(() => detail.value?.tasks || [])
const logs = computed(() => detail.value?.logs || [])
const stepGroups = computed(() => detail.value?.step_groups || [])

const targetTypeLabel = computed(() => {
  const map = { contract: '合同审批', invoice: '开票审批', quote: '报价审批' }
  return map[target.value?.type] || '审批'
})

const isAdminUser = computed(() => Boolean(auth.user?.is_superuser || auth.user?.is_staff))

const myPendingTasks = computed(() => (
  tasks.value.filter((task) => task.status === 'pending' && task.assignee === auth.user?.id)
))

const pendingTasks = computed(() => tasks.value.filter((task) => task.status === 'pending'))

const actionableTasks = computed(() => (isAdminUser.value ? pendingTasks.value : myPendingTasks.value))

const selectedTask = computed(() => (
  actionableTasks.value.find((task) => String(task.id) === selectedTaskId.value) || null
))

const selectedTaskKind = computed(() => {
  if (!selectedTask.value) return 'normal'
  if (selectedTask.value.task_kind === 'add_sign') return 'add_sign'
  if (selectedTask.value.parent_task_id) return 'add_sign'
  return 'normal'
})

const canDecideSelectedTask = computed(() => {
  const task = selectedTask.value
  if (!task || task.status !== 'pending') return false
  if (task.assignee === auth.user?.id) return true
  return Boolean(auth.user?.is_superuser)
})

const canApprove = computed(() => canDecideSelectedTask.value)
const canReject = computed(() => canDecideSelectedTask.value && selectedTaskKind.value !== 'add_sign')
const showRejectButton = computed(() => Boolean(selectedTask.value) && selectedTaskKind.value !== 'add_sign')
const approveButtonLabel = computed(() => (selectedTaskKind.value === 'add_sign' ? '提交意见' : '同意'))

const canOperateSelectedTask = computed(() => {
  const task = selectedTask.value
  if (!task || task.status !== 'pending') return false
  return task.assignee === auth.user?.id || isAdminUser.value
})

const canTransfer = computed(() => canOperateSelectedTask.value)
const canAddSign = computed(() => canOperateSelectedTask.value && selectedTaskKind.value !== 'add_sign')
const showAddSignButton = computed(() => Boolean(selectedTask.value) && selectedTaskKind.value !== 'add_sign')

const operationDialogTitle = computed(() => (
  operationType.value === 'add_sign' ? '发起加签' : '转办任务'
))

const operationSubmitLabel = computed(() => (
  operationType.value === 'add_sign' ? '确认加签' : '确认转办'
))

const operationCandidateUsers = computed(() => {
  const selectedId = Number(selectedTask.value?.assignee || 0)
  return userOptions.value.filter((item) => Number(item.id) !== selectedId)
})

const groupedTasks = computed(() => {
  const groups = {}
  tasks.value.forEach((task) => {
    if (task.status === 'blocked') return
    const order = task.step_order || 0
    if (!groups[order]) {
      groups[order] = {
        step_order: order,
        step_name: task.step_name || '',
        tasks: []
      }
    }
    groups[order].tasks.push(task)
  })
  return Object.values(groups).sort((a, b) => a.step_order - b.step_order)
})

const stepApproverMap = computed(() => {
  const mapping = {}
  tasks.value.forEach((task) => {
    const stepOrder = task.step_order || 0
    const assigneeName = String(task.assignee_name || '').trim()
    if (!assigneeName) return
    if (!mapping[stepOrder]) {
      mapping[stepOrder] = new Set()
    }
    mapping[stepOrder].add(assigneeName)
  })
  return mapping
})

const stepApproverLabel = (stepOrder) => {
  const names = stepApproverMap.value[stepOrder] ? Array.from(stepApproverMap.value[stepOrder]) : []
  return names.length ? names.join('、') : '-'
}

const goBackSource = () => {
  const from = String(route.query.from || '')
  if (from.startsWith('contract:')) {
    const id = from.split(':')[1]
    router.push(`/contracts/${id}`)
    return
  }
  if (from.startsWith('invoice:')) {
    const id = from.split(':')[1]
    router.push(`/invoices/${id}`)
    return
  }
  if (from === 'approvals') {
    router.push('/approvals/tasks')
    return
  }
  router.back()
}

const instanceStatusLabel = (value) => {
  const map = {
    pending: '审批中',
    approved: '已通过',
    rejected: '已驳回',
    withdrawn: '已撤回'
  }
  return map[value] || '-'
}

const taskStatusLabel = (value) => {
  const map = {
    pending: '待审批',
    approved: '已同意',
    rejected: '已驳回',
    blocked: '未轮到',
    canceled: '已关闭'
  }
  return map[value] || '-'
}

const taskStatusClass = (value) => {
  const map = {
    pending: 'task-status-pending',
    approved: 'task-status-approved',
    rejected: 'task-status-rejected',
    blocked: 'task-status-blocked',
    canceled: 'task-status-canceled'
  }
  return map[value] || 'task-status-blocked'
}

const actionLabel = (value) => {
  const map = {
    submitted: '发起审批',
    task_activated: '任务激活',
    approved: '审批通过',
    rejected: '审批驳回',
    withdrawn: '审批撤回',
    completed: '流程完成',
    todo_create: '待办创建',
    todo_complete: '待办关闭',
    todo_failed: '待办失败'
  }
  return map[value] || value || '-'
}

const formatValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

const formatTargetFieldValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  const text = String(value)
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(text)) {
    return text.replace('T', ' ').slice(0, 19)
  }
  return text
}

const stepStatusLabel = (value) => {
  const map = {
    done: '已完成',
    active: '进行中',
    waiting: '未开始',
    rejected: '已驳回',
    canceled: '已关闭'
  }
  return map[value] || '进行中'
}

const latestActionSummary = computed(() => {
  const latest = instance.value?.latest_action
  if (!latest) return '-'
  return `${actionLabel(latest.action)} · ${latest.actor_name || '-'} · ${formatValue(latest.created_at)}`
})

const finishedStepCount = computed(() => {
  const doneStates = new Set(['done', 'rejected', 'canceled'])
  return stepGroups.value.filter((group) => doneStates.has(group.status)).length
})

const progressPercent = computed(() => {
  if (!stepGroups.value.length) return 0
  return Math.min(100, Math.round((finishedStepCount.value / stepGroups.value.length) * 100))
})

const extractErrorMessage = (err, fallback) => {
  const detailMessage = err?.response?.data?.detail
  if (detailMessage) return detailMessage
  const status = err?.response?.status
  if (status) return `${fallback}（HTTP ${status}）`
  return fallback
}

const fetchUserOptions = async () => {
  userOptionsLoading.value = true
  try {
    const resp = await api.get('/users/', {
      params: {
        page: 1,
        page_size: 1000,
        ordering: 'username',
        is_active: true
      }
    })
    const raw = Array.isArray(resp.data?.results) ? resp.data.results : (Array.isArray(resp.data) ? resp.data : [])
    userOptions.value = raw
      .filter((item) => item && item.id && item.username)
      .map((item) => ({ id: item.id, username: item.username }))
  } catch (err) {
    error.value = extractErrorMessage(err, '加载人员列表失败')
  } finally {
    userOptionsLoading.value = false
  }
}

const syncSelectedTask = () => {
  const ids = actionableTasks.value.map((task) => String(task.id))
  if (!ids.length) {
    selectedTaskId.value = ''
    return
  }
  if (preferredTaskId.value && ids.includes(preferredTaskId.value)) {
    selectedTaskId.value = preferredTaskId.value
    return
  }
  if (!ids.includes(selectedTaskId.value)) {
    selectedTaskId.value = ids[0]
  }
}

const fetchInstanceDetail = async () => {
  if (!instanceId.value) return
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    const resp = await api.get(`/approval-instances/${instanceId.value}/detail/`)
    detail.value = resp.data
    syncSelectedTask()
  } catch (err) {
    error.value = extractErrorMessage(err, '加载审批信息失败')
  } finally {
    loading.value = false
  }
}

const bridgeTaskRoute = async () => {
  if (!taskRouteId.value) return
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    const resp = await api.get(`/approval-tasks/${taskRouteId.value}/detail/`)
    const resolvedInstanceId = resp.data?.instance?.id
    if (!resolvedInstanceId) {
      error.value = '审批实例不存在或不可访问'
      return
    }
    await router.replace({
      name: 'approval-instance',
      params: { id: String(resolvedInstanceId) },
      query: {
        task_id: String(taskRouteId.value),
        from: String(route.query.from || 'approvals')
      }
    })
  } catch (err) {
    error.value = extractErrorMessage(err, '加载审批信息失败')
  } finally {
    loading.value = false
  }
}

const fetchEntry = async () => {
  if (route.name === 'approval-task') {
    await bridgeTaskRoute()
    return
  }
  await fetchInstanceDetail()
}

const submitDecision = async (approved) => {
  if (!selectedTaskId.value) return
  if (approved && !canApprove.value) return
  if (!approved && !canReject.value) return
  error.value = ''
  success.value = ''
  decisionLoading.value = true
  try {
    await api.post(`/approval-tasks/${selectedTaskId.value}/decision/`, {
      approved,
      comment: comment.value || ''
    })
    if (approved && selectedTaskKind.value === 'add_sign') {
      success.value = '加签意见已提交'
    } else {
      success.value = approved ? '审批已通过' : '审批已驳回'
    }
    comment.value = ''
    await fetchInstanceDetail()
  } catch (err) {
    error.value = extractErrorMessage(err, '审批提交失败')
  } finally {
    decisionLoading.value = false
  }
}

const openOperation = (type) => {
  if (type === 'add_sign' && !canAddSign.value) return
  if (type === 'transfer' && !canTransfer.value) return
  operationType.value = type
  operationAssigneeId.value = ''
  operationComment.value = ''
  showOperationDialog.value = true
}

const closeOperationDialog = () => {
  if (operationLoading.value) return
  showOperationDialog.value = false
}

const submitOperation = async () => {
  if (!selectedTaskId.value || !operationAssigneeId.value) return
  if (operationType.value === 'add_sign' && !canAddSign.value) return
  if (operationType.value === 'transfer' && !canTransfer.value) return
  error.value = ''
  success.value = ''
  operationLoading.value = true
  try {
    const path = operationType.value === 'add_sign' ? 'add_sign' : 'transfer'
    await api.post(`/approval-tasks/${selectedTaskId.value}/${path}/`, {
      assignee_id: Number(operationAssigneeId.value),
      comment: operationComment.value || ''
    })
    success.value = operationType.value === 'add_sign' ? '已发起加签' : '已完成转办'
    showOperationDialog.value = false
    operationAssigneeId.value = ''
    operationComment.value = ''
    await fetchInstanceDetail()
  } catch (err) {
    error.value = extractErrorMessage(err, operationType.value === 'add_sign' ? '发起加签失败' : '转办失败')
  } finally {
    operationLoading.value = false
  }
}

watch(
  () => route.fullPath,
  () => {
    fetchEntry()
  }
)

watch(actionableTasks, () => {
  syncSelectedTask()
})

onMounted(() => {
  fetchUserOptions()
  fetchEntry()
})
</script>

<style scoped>
.approval-cockpit {
  --cockpit-line: #d9e3f0;
  --cockpit-muted: #5b677c;
  --cockpit-soft: #f8fbff;
  --cockpit-blue-soft: #eef5ff;
  --cockpit-blue-line: #8bb6ff;
  --cockpit-green-soft: #ebfbf3;
  --cockpit-green-line: #7dd3ae;
  --cockpit-red-soft: #fff1f2;
  --cockpit-red-line: #f9a8b4;
  --cockpit-wait-soft: #f7f9fc;
  --cockpit-wait-line: #d5dde9;
  display: grid;
  gap: 10px;
  padding: 16px;
}

.approval-cockpit .card {
  margin-bottom: 0;
}

.cockpit-hero {
  background: linear-gradient(135deg, #ffffff 0%, #f6faff 55%, #fff8ee 100%);
  border-color: var(--cockpit-line);
  box-shadow: 0 16px 28px rgba(19, 32, 58, 0.08);
  padding: 12px 14px;
}

.hero-back {
  padding: 6px 12px;
  min-height: 30px;
  font-size: 12px;
}

.hero-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.hero-main-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.hero-main-right {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  max-width: 58%;
}

.meta-chip {
  font-size: 12px;
  color: #51607a;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid #dbe4f3;
  border-radius: 999px;
  padding: 3px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.title-main {
  font-size: 20px;
  line-height: 1.2;
  letter-spacing: -0.2px;
  font-weight: 700;
  color: #122442;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}

.title-meta {
  margin-top: 8px;
  color: var(--cockpit-muted);
  font-size: 13px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.status-pill {
  font-size: 11px;
  line-height: 1;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-weight: 600;
  white-space: nowrap;
}

.status-pill.status-pending {
  color: #1d4ed8;
  border-color: #93c5fd;
  background: #eff6ff;
}

.status-pill.status-approved {
  color: #047857;
  border-color: #86efac;
  background: #ecfdf5;
}

.status-pill.status-rejected {
  color: #be123c;
  border-color: #fda4af;
  background: #fff1f2;
}

.status-pill.status-withdrawn {
  color: #6b7280;
  border-color: #d1d5db;
  background: #f3f4f6;
}

.head-type {
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  padding: 6px 10px;
  border-radius: 999px;
  background: #fff4e5;
  color: #9a3412;
  border: 1px solid #f3d1a0;
  font-weight: 600;
  white-space: nowrap;
}

.progress-meter {
  margin-top: 6px;
  height: 6px;
  border-radius: 999px;
  background: #ecf1f7;
  overflow: hidden;
}

.progress-meter-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #d97706 0%, #f59e0b 100%);
  transition: width 0.3s ease;
}

.step-empty {
  color: #7a869d;
  font-size: 12px;
  padding: 4px 0;
}

.timeline-card {
  padding: 10px 12px;
}

.timeline-progress {
  margin-top: 6px;
  border: 1px solid var(--cockpit-line);
  border-radius: 10px;
  padding: 8px;
  background: #f8fbff;
}

.timeline-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.timeline-progress-title {
  font-size: 12px;
  font-weight: 600;
  color: #223a61;
}

.timeline-progress-meta {
  font-size: 11px;
  color: var(--cockpit-muted);
}

.timeline-step-list {
  margin-top: 6px;
  display: grid;
  gap: 6px;
}

.timeline-step-item {
  border: 1px solid var(--cockpit-wait-line);
  border-radius: 8px;
  padding: 6px 8px;
  background: var(--cockpit-wait-soft);
  display: grid;
  gap: 4px;
}

.timeline-step-item.status-done {
  border-color: var(--cockpit-green-line);
  background: var(--cockpit-green-soft);
}

.timeline-step-item.status-active {
  border-color: var(--cockpit-blue-line);
  background: var(--cockpit-blue-soft);
}

.timeline-step-item.status-rejected,
.timeline-step-item.status-canceled {
  border-color: var(--cockpit-red-line);
  background: var(--cockpit-red-soft);
}

.timeline-step-main,
.timeline-step-right {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.timeline-step-order {
  font-size: 10px;
  color: #64748b;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 999px;
  padding: 1px 6px;
  white-space: nowrap;
}

.timeline-step-name {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  color: #152947;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.timeline-step-approvers {
  font-size: 11px;
  color: #4f5f7a;
  line-height: 1.35;
}

.timeline-step-ratio {
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  white-space: nowrap;
}

.timeline-step-state {
  font-size: 10px;
  color: #334155;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: 999px;
  padding: 1px 6px;
  white-space: nowrap;
}

.timeline-section-title {
  margin-top: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #223a61;
}

.cockpit-main {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(320px, 1fr);
  gap: 10px;
}

.main-left,
.main-right {
  display: grid;
  gap: 10px;
}

.approval-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.approval-field label {
  font-size: 12px;
  color: var(--cockpit-muted);
  display: block;
  margin-bottom: 4px;
}

.approval-remark {
  margin-top: 12px;
}

.approval-remark label {
  font-size: 12px;
  color: var(--cockpit-muted);
  display: block;
  margin-bottom: 4px;
}

.field-value {
  border: 1px solid var(--cockpit-line);
  border-radius: 8px;
  padding: 9px 10px;
  background: var(--cockpit-soft);
  font-size: 13px;
}

.field-value-remark {
  white-space: pre-wrap;
  word-break: break-word;
}

.attachment-list {
  display: grid;
  gap: 8px;
}

.attachment-item {
  border: 1px dashed #d7e2f0;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  background: #fbfdff;
}

.attachment-name {
  font-size: 13px;
  font-weight: 600;
  color: #173057;
}

.attachment-meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--cockpit-muted);
}

.task-group + .task-group {
  margin-top: 14px;
}

.task-group-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #1e3558;
}

.task-status-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid transparent;
}

.task-status-pending {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #93c5fd;
}

.task-status-approved {
  color: #047857;
  background: #ecfdf5;
  border-color: #86efac;
}

.task-status-rejected {
  color: #be123c;
  background: #fff1f2;
  border-color: #fda4af;
}

.task-status-blocked {
  color: #64748b;
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.task-status-canceled {
  color: #52525b;
  background: #f4f4f5;
  border-color: #d4d4d8;
}

.timeline {
  position: relative;
  display: grid;
  gap: 12px;
  margin-top: 8px;
}

.timeline::before {
  content: "";
  position: absolute;
  left: 6px;
  top: 2px;
  bottom: 2px;
  width: 2px;
  background: linear-gradient(180deg, #d97706 0%, #e3e8f0 90%);
}

.timeline-item {
  position: relative;
  padding-left: 22px;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  border: 2px solid #d97706;
  background: #ffffff;
  position: absolute;
  left: 1px;
  top: 4px;
}

.timeline-time {
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
}

.timeline-content {
  border: 1px solid var(--cockpit-line);
  background: #f9fbff;
  border-radius: 8px;
  padding: 8px 10px;
}

.timeline-title {
  font-size: 13px;
  font-weight: 600;
  color: #142b4e;
}

.timeline-actor {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.timeline-comment {
  margin-top: 6px;
  font-size: 12px;
  color: var(--cockpit-muted);
}

.action-bar {
  position: sticky;
  bottom: 10px;
  z-index: 20;
  border-color: #d9e4f2;
  box-shadow: 0 16px 30px rgba(19, 32, 58, 0.16);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(8px);
}

.action-bar-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.action-bar-title {
  font-size: 14px;
  font-weight: 600;
  color: #162c4d;
}

.action-bar-tip {
  font-size: 12px;
  color: var(--cockpit-muted);
}

.action-bar-main {
  margin-top: 10px;
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto auto auto auto;
  gap: 10px;
  align-items: center;
}

.action-bar-main.with-task-selector {
  grid-template-columns: 220px minmax(240px, 1fr) auto auto auto auto;
}

.action-bar textarea,
.action-bar select {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
}

.action-bar-main .button {
  min-width: 74px;
  padding: 8px 12px;
}

.action-bar textarea {
  min-height: 44px;
  resize: vertical;
}

.empty-text {
  margin-top: 8px;
  color: #7a869d;
  font-size: 12px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
  z-index: 70;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-card {
  width: min(520px, 100%);
  background: #ffffff;
  border: 1px solid #d7e3f4;
  border-radius: 12px;
  box-shadow: 0 20px 36px rgba(17, 24, 39, 0.2);
  padding: 14px;
}

.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f2747;
}

.modal-close {
  min-width: 62px;
}

.modal-body {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.modal-row {
  display: grid;
  gap: 6px;
}

.modal-row label {
  font-size: 12px;
  color: #465874;
}

.modal-row select,
.modal-row textarea {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
}

.modal-row textarea {
  resize: vertical;
}

.modal-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.alert {
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
}

.alert.error {
  background: #fff2f0;
  color: #c92a2a;
}

.alert.success {
  background: #eef9f0;
  color: #2b8a3e;
}

@media (max-width: 1080px) {
  .hero-main {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-main-right {
    max-width: 100%;
    justify-content: flex-start;
  }

  .title-main {
    max-width: none;
  }

  .cockpit-main {
    grid-template-columns: 1fr;
  }

  .approval-grid {
    grid-template-columns: 1fr;
  }

  .action-bar-main {
    grid-template-columns: 1fr;
  }

  .action-bar-main.with-task-selector {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .title-main {
    font-size: 18px;
  }

  .hero-main-left {
    flex-wrap: wrap;
  }
}
</style>
