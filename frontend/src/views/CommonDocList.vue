<template>
  <div>
    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>

    <div class="common-doc-layout">
      <div class="card directory-panel">
        <div class="section-title">目录</div>

        <div v-if="canManageDirectories" class="directory-create">
          <input v-model.trim="newDirectoryName" placeholder="新目录名称" @keyup.enter="createDirectory" />
          <button class="button" :disabled="!newDirectoryName" @click="createDirectory">新增目录</button>
        </div>

        <div v-if="directories.length" class="directory-list">
          <button
            v-for="dir in directories"
            :key="dir.id"
            class="directory-item"
            :class="{ active: selectedDirectoryId === dir.id }"
            @click="selectDirectory(dir.id)"
          >
            <span>{{ dir.name }}</span>
          </button>
        </div>
        <div v-else style="color: #888;">暂无可见目录</div>

        <div v-if="selectedDirectory" class="directory-meta">
          <div><strong>创建人：</strong>{{ selectedDirectory.created_by_name || '-' }}</div>
          <div><strong>创建时间：</strong>{{ formatDate(selectedDirectory.created_at) }}</div>
          <div><strong>更新人：</strong>{{ selectedDirectory.updated_by_name || '-' }}</div>
          <div><strong>更新时间：</strong>{{ formatDate(selectedDirectory.updated_at) }}</div>
        </div>

        <div v-if="canManageDirectories && selectedDirectory" class="directory-actions">
          <input v-model.trim="renameDirectoryName" placeholder="重命名目录" />
          <button class="button secondary" :disabled="!renameDirectoryName" @click="renameDirectory">重命名</button>
          <button class="button secondary" @click="deleteDirectory">删除目录</button>
          <button class="button secondary" @click="openPermissionModal">权限设置</button>
        </div>
      </div>

      <div class="card doc-panel">
        <div class="list-head">
          <div class="list-head-info">
            <div>{{ selectedDirectory ? `目录：${selectedDirectory.name}` : '请选择目录' }}</div>
          </div>
          <div class="list-head-actions">
            <input
              v-model="search"
              class="filter-search"
              placeholder="搜索标题/原始文件名/备注"
              @keyup.enter="fetchDocuments"
            />
            <button class="button" @click="fetchDocuments">搜索</button>
          </div>
        </div>

        <div v-if="selectedDirectory && (selectedDirectory.can_upload || canManageDirectories)" class="doc-form">
          <div class="form-grid">
            <div>
              <label>文档标题</label>
              <input v-model.trim="docForm.title" placeholder="可选，不填默认文件名" />
            </div>
            <div>
              <label>文档备注</label>
              <input v-model.trim="docForm.description" placeholder="可选" />
            </div>
            <div>
              <label>{{ editingDocId ? '替换文件（可选）' : '选择文件' }}</label>
              <input type="file" @change="onFileChange" />
            </div>
          </div>
          <div style="margin-top: 10px;">
            <button class="button" :disabled="savingDoc" @click="saveDocument">
              {{ savingDoc ? '保存中...' : (editingDocId ? '保存修改' : '上传文档') }}
            </button>
            <button v-if="editingDocId" class="button secondary" @click="cancelEdit">取消编辑</button>
          </div>
        </div>

        <div class="table-wrap">
          <table class="table common-doc-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>备注</th>
                <th>创建人</th>
                <th>创建时间</th>
                <th>更新人</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in documents" :key="item.id">
                <td>{{ item.title || item.original_name || `文档${item.id}` }}</td>
                <td>{{ item.description || '-' }}</td>
                <td>{{ item.created_by_name || '-' }}</td>
                <td>{{ formatDate(item.created_at) }}</td>
                <td>{{ item.updated_by_name || '-' }}</td>
                <td>{{ formatDate(item.updated_at) }}</td>
                <td>
                  <button
                    v-if="canPreview(item)"
                    class="button secondary"
                    :disabled="previewLoading && previewItem?.id === item.id"
                    @click="openPreview(item)"
                  >
                    {{ previewLoading && previewItem?.id === item.id ? '加载中...' : '预览' }}
                  </button>
                  <button
                    class="button secondary"
                    :disabled="downloadingId === item.id || !(selectedDirectory?.can_download || canManageDirectories)"
                    @click="downloadDocument(item)"
                  >
                    {{ downloadingId === item.id ? '下载中...' : '下载' }}
                  </button>
                  <button
                    v-if="selectedDirectory && (selectedDirectory.can_edit || canManageDirectories)"
                    class="button secondary"
                    @click="startEdit(item)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="selectedDirectory && (selectedDirectory.can_delete || canManageDirectories)"
                    class="button secondary"
                    @click="deleteDocument(item)"
                  >
                    删除
                  </button>
                </td>
              </tr>
              <tr v-if="!documents.length">
                <td colspan="7" style="color: #888;">暂无文档</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="showPreviewModal" class="modal-mask" @click.self="closePreview">
      <div class="modal-card preview-modal">
        <div class="section-title">在线预览</div>
        <div style="margin-bottom: 8px; color: #64748b;">
          {{ previewItem?.title || previewItem?.original_name || '-' }}
        </div>
        <div v-if="previewError" style="color: #c92a2a; margin-bottom: 8px;">{{ previewError }}</div>
        <div v-if="previewLoading" style="color: #64748b;">加载中...</div>
        <div v-else-if="previewType === 'image'" class="preview-content">
          <img class="preview-image" :src="previewUrl" alt="文档预览" />
        </div>
        <div v-else-if="previewType === 'pdf'" class="preview-content">
          <iframe class="preview-frame" :src="previewUrl" title="PDF预览"></iframe>
        </div>
        <div v-else-if="previewType === 'text'" class="preview-content">
          <pre class="preview-text">{{ previewText }}</pre>
        </div>
        <div style="margin-top: 12px;">
          <button class="button secondary" @click="closePreview">关闭</button>
          <button
            v-if="previewItem"
            class="button"
            :disabled="downloadingId === previewItem.id"
            @click="downloadDocument(previewItem)"
          >
            {{ downloadingId === previewItem.id ? '下载中...' : '下载' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showPermissionModal" class="modal-mask" @click.self="closePermissionModal">
      <div class="modal-card">
        <div class="section-title">目录权限设置</div>
        <div style="margin-bottom: 8px; color: #64748b;">目录：{{ selectedDirectory?.name || '-' }}</div>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>角色</th>
                <th>查看</th>
                <th>下载</th>
                <th>上传</th>
                <th>编辑</th>
                <th>删除</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in permissionItems" :key="item.role">
                <td>{{ item.role_name }}</td>
                <td><input v-model="item.can_view" type="checkbox" /></td>
                <td><input v-model="item.can_download" type="checkbox" /></td>
                <td><input v-model="item.can_upload" type="checkbox" /></td>
                <td><input v-model="item.can_edit" type="checkbox" /></td>
                <td><input v-model="item.can_delete" type="checkbox" /></td>
              </tr>
              <tr v-if="!permissionItems.length">
                <td colspan="6" style="color: #888;">暂无角色数据</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top: 12px;">
          <button class="button" :disabled="savingPermissions" @click="savePermissions">
            {{ savingPermissions ? '保存中...' : '保存权限' }}
          </button>
          <button class="button secondary" @click="closePermissionModal">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

const directories = ref([])
const selectedDirectoryId = ref(null)
const documents = ref([])
const error = ref('')
const search = ref('')
const savingDoc = ref(false)
const downloadingId = ref(null)
const previewLoading = ref(false)
const showPreviewModal = ref(false)
const previewItem = ref(null)
const previewType = ref('')
const previewText = ref('')
const previewUrl = ref('')
const previewError = ref('')

const newDirectoryName = ref('')
const renameDirectoryName = ref('')

const editingDocId = ref(null)
const docForm = ref({
  title: '',
  description: '',
  file: null
})

const showPermissionModal = ref(false)
const permissionItems = ref([])
const savingPermissions = ref(false)

const canManageDirectories = computed(() => Boolean(auth.user?.is_staff || auth.user?.is_superuser))
const selectedDirectory = computed(() => directories.value.find((item) => item.id === selectedDirectoryId.value) || null)
const PREVIEW_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']
const PREVIEW_TEXT_EXTENSIONS = ['txt', 'md', 'log', 'csv', 'json', 'xml', 'yaml', 'yml', 'html', 'htm']
const PREVIEW_TEXT_MAX_BYTES = 1024 * 1024

const parseListData = (data) => (Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []))

const formatDate = (value) => {
  if (!value) return '-'
  return String(value).slice(0, 10)
}

const fileName = (item) => item?.original_name || item?.title || `doc-${item?.id || 'file'}`

const fileExt = (item) => {
  const name = fileName(item).toLowerCase()
  return name.includes('.') ? name.split('.').pop() : ''
}

const previewKind = (item) => {
  const ext = fileExt(item)
  if (PREVIEW_IMAGE_EXTENSIONS.includes(ext)) return 'image'
  if (ext === 'pdf') return 'pdf'
  if (PREVIEW_TEXT_EXTENSIONS.includes(ext)) return 'text'
  return ''
}

const canPreview = (item) => Boolean(previewKind(item))

const clearPreviewBlobUrl = () => {
  if (previewUrl.value && previewUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
}

const selectDirectory = (id) => {
  closePreview()
  selectedDirectoryId.value = id
  renameDirectoryName.value = selectedDirectory.value?.name || ''
  cancelEdit()
  fetchDocuments()
}

const fetchDirectories = async () => {
  const res = await api.get('/common-doc-directories/', {
    params: { page: 1, page_size: 1000, ordering: 'sort_order,id' }
  })
  directories.value = parseListData(res.data)
  if (!directories.value.length) {
    selectedDirectoryId.value = null
    documents.value = []
    return
  }
  if (!selectedDirectoryId.value || !directories.value.some((item) => item.id === selectedDirectoryId.value)) {
    selectedDirectoryId.value = directories.value[0].id
  }
  renameDirectoryName.value = selectedDirectory.value?.name || ''
}

const fetchDocuments = async () => {
  if (!selectedDirectoryId.value) {
    documents.value = []
    return
  }
  const params = {
    directory: selectedDirectoryId.value,
    page: 1,
    page_size: 1000,
    ordering: '-updated_at'
  }
  if (search.value) params.search = search.value
  const res = await api.get('/common-documents/', { params })
  documents.value = parseListData(res.data)
}

const onFileChange = (event) => {
  const file = event.target.files && event.target.files[0]
  docForm.value.file = file || null
}

const resetDocForm = () => {
  editingDocId.value = null
  docForm.value = { title: '', description: '', file: null }
}

const cancelEdit = () => {
  resetDocForm()
}

const saveDocument = async () => {
  if (!selectedDirectoryId.value) {
    error.value = '请先选择目录'
    return
  }
  if (!editingDocId.value && !docForm.value.file) {
    error.value = '请先选择文件'
    return
  }
  savingDoc.value = true
  error.value = ''
  try {
    const formData = new FormData()
    if (!editingDocId.value) {
      formData.append('directory', String(selectedDirectoryId.value))
    }
    if (docForm.value.title) formData.append('title', docForm.value.title)
    else formData.append('title', '')
    if (docForm.value.description) formData.append('description', docForm.value.description)
    else formData.append('description', '')
    if (docForm.value.file) formData.append('file', docForm.value.file)

    if (editingDocId.value) {
      await api.patch(`/common-documents/${editingDocId.value}/`, formData)
    } else {
      await api.post('/common-documents/', formData)
    }
    await fetchDocuments()
    resetDocForm()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '保存失败，请检查权限或输入内容'
  } finally {
    savingDoc.value = false
  }
}

const startEdit = (item) => {
  editingDocId.value = item.id
  docForm.value = {
    title: item.title || '',
    description: item.description || '',
    file: null
  }
}

const deleteDocument = async (item) => {
  if (!confirm(`确认删除文档“${item.title || item.original_name || item.id}”？`)) return
  error.value = ''
  try {
    await api.delete(`/common-documents/${item.id}/`)
    await fetchDocuments()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '删除失败，请检查权限'
  }
}

const parseFilename = (contentDisposition, fallback) => {
  if (!contentDisposition) return fallback
  const utfMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch && utfMatch[1]) {
    try {
      return decodeURIComponent(utfMatch[1])
    } catch {
      return fallback
    }
  }
  const asciiMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i)
  return asciiMatch?.[1] || fallback
}

const downloadDocument = async (item) => {
  downloadingId.value = item.id
  error.value = ''
  try {
    const res = await api.get(`/common-documents/${item.id}/download/`, { responseType: 'blob' })
    const blobUrl = URL.createObjectURL(res.data)
    const filename = parseFilename(
      res.headers?.['content-disposition'],
      item.original_name || item.title || `doc-${item.id}`
    )
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    link.click()
    URL.revokeObjectURL(blobUrl)
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '下载失败，请检查权限'
  } finally {
    downloadingId.value = null
  }
}

const closePreview = () => {
  showPreviewModal.value = false
  previewLoading.value = false
  previewItem.value = null
  previewType.value = ''
  previewText.value = ''
  previewError.value = ''
  clearPreviewBlobUrl()
}

const openPreview = async (item) => {
  if (!canPreview(item)) {
    error.value = '该文件类型暂不支持在线预览，请下载查看。'
    return
  }
  closePreview()
  showPreviewModal.value = true
  previewLoading.value = true
  previewItem.value = item
  previewType.value = previewKind(item)
  try {
    const res = await api.get(`/common-documents/${item.id}/preview/`, { responseType: 'blob' })
    const blob = res.data
    if (previewType.value === 'text') {
      if (blob.size > PREVIEW_TEXT_MAX_BYTES) {
        previewError.value = '文本文件过大，暂不支持在线预览，请下载查看。'
        return
      }
      previewText.value = await blob.text()
      return
    }
    previewUrl.value = URL.createObjectURL(blob)
  } catch (err) {
    const detail = err.response?.data
    previewError.value = detail?.detail || '预览失败，请下载查看。'
  } finally {
    previewLoading.value = false
  }
}

const createDirectory = async () => {
  if (!newDirectoryName.value) return
  error.value = ''
  try {
    await api.post('/common-doc-directories/', { name: newDirectoryName.value, is_active: true })
    newDirectoryName.value = ''
    await fetchDirectories()
    await fetchDocuments()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '新增目录失败'
  }
}

const renameDirectory = async () => {
  if (!selectedDirectory.value || !renameDirectoryName.value) return
  error.value = ''
  try {
    await api.patch(`/common-doc-directories/${selectedDirectory.value.id}/`, { name: renameDirectoryName.value })
    await fetchDirectories()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '重命名失败'
  }
}

const deleteDirectory = async () => {
  if (!selectedDirectory.value) return
  if (!confirm(`确认删除目录“${selectedDirectory.value.name}”？`)) return
  error.value = ''
  try {
    await api.delete(`/common-doc-directories/${selectedDirectory.value.id}/`)
    await fetchDirectories()
    await fetchDocuments()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '删除目录失败'
  }
}

const openPermissionModal = async () => {
  if (!selectedDirectory.value) return
  error.value = ''
  try {
    const res = await api.get(`/common-doc-directories/${selectedDirectory.value.id}/permissions/`)
    permissionItems.value = Array.isArray(res.data?.items) ? res.data.items : []
    showPermissionModal.value = true
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '加载权限失败'
  }
}

const closePermissionModal = () => {
  showPermissionModal.value = false
  permissionItems.value = []
}

const savePermissions = async () => {
  if (!selectedDirectory.value) return
  savingPermissions.value = true
  error.value = ''
  try {
    await api.put(`/common-doc-directories/${selectedDirectory.value.id}/permissions/`, {
      items: permissionItems.value
    })
    closePermissionModal()
    await fetchDirectories()
    await fetchDocuments()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '保存权限失败'
  } finally {
    savingPermissions.value = false
  }
}

watch(selectedDirectoryId, () => {
  const dir = selectedDirectory.value
  renameDirectoryName.value = dir?.name || ''
})

onMounted(async () => {
  try {
    await fetchDirectories()
    await fetchDocuments()
  } catch (err) {
    const detail = err.response?.data
    error.value = detail?.detail || '加载常用文档失败'
  }
})

onBeforeUnmount(() => {
  clearPreviewBlobUrl()
})
</script>

<style scoped>
.common-doc-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
}

.directory-panel {
  min-height: 70vh;
}

.doc-panel {
  min-height: 70vh;
}

.directory-create {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.directory-create input {
  flex: 1;
}

.directory-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.directory-item {
  text-align: left;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
}

.directory-item.active {
  border-color: #3b82f6;
  background: #eff6ff;
}

.directory-meta {
  margin-top: 12px;
  font-size: 13px;
  color: #475569;
  display: grid;
  gap: 4px;
}

.directory-actions {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.doc-form {
  margin: 10px 0 14px;
}

.common-doc-table {
  min-width: 980px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}

.modal-card {
  width: min(980px, 92vw);
  max-height: 82vh;
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
}

.preview-modal {
  width: min(1100px, 94vw);
}

.preview-content {
  min-height: 360px;
  max-height: 68vh;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  padding: 8px;
}

.preview-image {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}

.preview-frame {
  width: 100%;
  min-height: 62vh;
  border: none;
  background: #fff;
}

.preview-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.5;
  color: #1e293b;
}

@media (max-width: 1024px) {
  .common-doc-layout {
    grid-template-columns: 1fr;
  }
}
</style>
