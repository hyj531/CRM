<template>
  <div class="approval-page">
    <div class="card approval-card">
      <div class="approval-header">
        <div>
          <div class="approval-title">{{ targetTitle || '审批表单' }}</div>
          <div class="approval-meta">
            <span>状态：{{ statusLabel(task?.status) }}</span>
            <span>步骤：{{ task?.step_name || '-' }}</span>
            <span>发起人：{{ instance?.started_by_name || '-' }}</span>
          </div>
        </div>
        <div class="approval-type">{{ targetTypeLabel }}</div>
      </div>

      <div v-if="error" class="approval-alert error">{{ error }}</div>
      <div v-if="success" class="approval-alert success">{{ success }}</div>

      <div class="approval-section">
        <div class="section-title">审批信息</div>
        <div class="approval-grid">
          <div v-for="item in targetFields" :key="item.label" class="approval-field">
            <label>{{ item.label }}</label>
            <div class="field-value">{{ formatValue(item.value) }}</div>
          </div>
        </div>
      </div>

      <div v-if="attachments.length" class="approval-section">
        <div class="section-title">附件</div>
        <div class="attachment-list">
          <div v-for="file in attachments" :key="file.id" class="attachment-item">
            <div>
              <div class="attachment-name">{{ file.original_name || '附件' }}</div>
              <div class="attachment-meta">上传人：{{ file.owner_name || '-' }} · {{ formatValue(file.created_at) }}</div>
            </div>
            <a v-if="file.file_url" class="text-link" :href="file.file_url" target="_blank" rel="noopener">查看</a>
          </div>
        </div>
      </div>

      <div class="approval-section">
        <div class="section-title">审批意见</div>
        <textarea v-model="comment" rows="3" placeholder="请输入审批意见（可选）"></textarea>
        <div class="approval-actions">
          <button class="button" :disabled="decisionLoading || !isPending" @click="submitDecision(true)">
            {{ decisionLoading ? '处理中...' : '同意' }}
          </button>
          <button class="button secondary" :disabled="decisionLoading || !isPending" @click="submitDecision(false)">
            驳回
          </button>
          <span v-if="!isPending" class="approval-hint">该审批已处理</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const taskId = computed(() => route.params.id)

const loading = ref(false)
const error = ref('')
const success = ref('')
const taskDetail = ref(null)
const comment = ref('')
const decisionLoading = ref(false)

const task = computed(() => taskDetail.value?.task)
const instance = computed(() => taskDetail.value?.instance)
const target = computed(() => taskDetail.value?.target || {})
const targetTitle = computed(() => target.value?.title || '')
const targetFields = computed(() => target.value?.fields || [])
const attachments = computed(() => target.value?.attachments || [])

const statusLabel = (value) => {
  const map = {
    pending: '待审批',
    approved: '已同意',
    rejected: '已驳回',
    blocked: '未轮到'
  }
  return map[value] || '-'
}

const targetTypeLabel = computed(() => {
  const map = {
    contract: '合同审批',
    invoice: '开票审批',
    quote: '报价审批'
  }
  return map[target.value?.type] || '审批'
})

const isPending = computed(() => task.value?.status === 'pending')

const formatValue = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  return value
}

const fetchDetail = async () => {
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    const resp = await api.get(`/approval-tasks/${taskId.value}/detail/`)
    taskDetail.value = resp.data
  } catch (err) {
    error.value = err.response?.data?.detail || '加载审批信息失败'
  } finally {
    loading.value = false
  }
}

const submitDecision = async (approved) => {
  error.value = ''
  success.value = ''
  decisionLoading.value = true
  try {
    await api.post(`/approval-tasks/${taskId.value}/decision/`, {
      approved,
      comment: comment.value
    })
    success.value = approved ? '审批已通过' : '审批已驳回'
    await fetchDetail()
  } catch (err) {
    error.value = err.response?.data?.detail || '审批提交失败'
  } finally {
    decisionLoading.value = false
  }
}

watch(taskId, () => {
  if (taskId.value) {
    fetchDetail()
  }
})

onMounted(() => {
  if (taskId.value) {
    fetchDetail()
  }
})
</script>

<style scoped>
.approval-page {
  padding: 24px;
}

.approval-card {
  display: grid;
  gap: 18px;
}

.approval-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.approval-title {
  font-size: 20px;
  font-weight: 700;
}

.approval-meta {
  margin-top: 6px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--muted);
}

.approval-type {
  background: var(--accent-soft);
  color: var(--accent-strong);
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.approval-section textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--line);
  padding: 10px 12px;
  font-size: 13px;
  resize: vertical;
  min-height: 90px;
}

.approval-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 20px;
}

.approval-field label {
  font-size: 12px;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}

.field-value {
  font-size: 13px;
  color: var(--ink);
  background: #f8fafc;
  border: 1px solid var(--line);
  padding: 8px 10px;
  border-radius: 10px;
  min-height: 34px;
  display: flex;
  align-items: center;
}

.attachment-list {
  display: grid;
  gap: 10px;
}

.attachment-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px dashed var(--line);
  background: #fffaf3;
}

.attachment-name {
  font-size: 13px;
  font-weight: 600;
}

.attachment-meta {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.approval-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.approval-alert {
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
}

.approval-alert.error {
  background: #fff2f0;
  color: #c92a2a;
}

.approval-alert.success {
  background: #eef9f0;
  color: #2b8a3e;
}

.approval-hint {
  font-size: 12px;
  color: var(--muted);
}

@media (max-width: 720px) {
  .approval-page {
    padding: 16px;
  }

  .approval-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .approval-grid {
    grid-template-columns: 1fr;
  }
}
</style>
