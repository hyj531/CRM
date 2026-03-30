<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ isNew ? '新建回款' : '回款详情' }}</h2>
        <div class="page-subtitle">回款登记与期次管理</div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="savePayment">
          {{ saving ? '保存中...' : '保存回款' }}
        </button>
        <button class="button secondary" @click="goBack">返回列表</button>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>

    <div class="card">
      <div class="section-title">回款信息</div>
      <div class="form-grid">
        <div>
          <label>关联合同</label>
          <div class="filter-autocomplete">
            <input
              v-model="contractSearch"
              placeholder="输入合同/甲方关键词进行搜索"
              @focus="showContractDropdown = true"
              @input="showContractDropdown = true"
              @blur="hideContractDropdown"
            />
            <div v-if="showContractDropdown && contractSearch" class="filter-suggestions">
              <div
                v-for="ct in filteredContracts"
                :key="ct.id"
                class="filter-suggestion"
                @mousedown.prevent="selectContract(ct)"
              >
                {{ contractLabel(ct) }}
              </div>
              <div v-if="!filteredContracts.length" class="filter-empty">无匹配合同</div>
            </div>
          </div>
        </div>
        <div>
          <label>回款金额</label>
          <input v-model.number="form.amount" type="number" />
        </div>
        <div>
          <label>回款状态</label>
          <select v-model="form.status">
            <option value="planned">未回款</option>
            <option value="partial">部分回款</option>
            <option value="paid">已回款</option>
          </select>
        </div>
        <div>
          <label>回款日期</label>
          <input v-model="form.paid_at" type="date" />
        </div>
        <div>
          <label>回款编号/备注</label>
          <input v-model="form.reference" />
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
const contracts = ref([])
const accounts = ref([])
const contractSearch = ref('')
const showContractDropdown = ref(false)
const error = ref('')
const success = ref('')
const saving = ref(false)

const form = ref({
  contract: null,
  amount: null,
  status: 'planned',
  paid_at: '',
  reference: ''
})

const paymentId = computed(() => {
  const raw = route.params.id
  if (!raw) return null
  const id = Number(raw)
  return Number.isFinite(id) ? id : null
})

const isNew = computed(() => !paymentId.value)

const goBack = () => {
  router.push('/payments')
}

const contractLabel = (contract) => {
  if (!contract) return ''
  const name = contract.name || contract.contract_no || `合同${contract.id}`
  const accountId = contract.account
  const acc = accounts.value.find((item) => item.id === accountId)
  const accountName = acc ? (acc.full_name || acc.short_name || `甲方${acc.id}`) : (accountId ? `甲方${accountId}` : '')
  return accountName ? `${name}（${accountName}）` : name
}

const filteredContracts = computed(() => {
  const keyword = contractSearch.value.trim().toLowerCase()
  if (!keyword) return contracts.value
  return contracts.value.filter((ct) => {
    const name = (ct.name || ct.contract_no || '').toLowerCase()
    const accountId = ct.account
    const acc = accounts.value.find((item) => item.id === accountId)
    const accountName = acc ? `${acc.full_name || ''} ${acc.short_name || ''}`.toLowerCase() : ''
    return name.includes(keyword) || accountName.includes(keyword)
  })
})

const selectContract = (ct) => {
  form.value.contract = ct.id
  contractSearch.value = contractLabel(ct)
  showContractDropdown.value = false
}

const hideContractDropdown = () => {
  setTimeout(() => {
    showContractDropdown.value = false
  }, 120)
}

const fetchContracts = async () => {
  const res = await api.get('/contracts/', { params: { page: 1, page_size: 1000 } })
  contracts.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const fetchAccounts = async () => {
  const res = await api.get('/accounts/', { params: { page: 1, page_size: 1000 } })
  accounts.value = Array.isArray(res.data.results) ? res.data.results : res.data
}

const fetchPayment = async () => {
  if (!paymentId.value) return
  const res = await api.get(`/payments/${paymentId.value}/`)
  const data = res.data || {}
  form.value = {
    contract: data.contract != null ? Number(data.contract) : null,
    amount: data.amount != null ? Number(data.amount) : null,
    status: data.status || 'planned',
    paid_at: data.paid_at || '',
    reference: data.reference || ''
  }
  const ct = contracts.value.find((c) => c.id === data.contract)
  contractSearch.value = ct ? contractLabel(ct) : ''
}

const savePayment = async () => {
  if (!form.value.contract) {
    error.value = '请选择关联合同'
    return
  }
  if (!form.value.amount) {
    error.value = '回款金额不能为空'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = {
      ...form.value,
      contract: Number(form.value.contract),
      amount: Number(form.value.amount),
      paid_at: form.value.paid_at || null
    }
    if (isNew.value) {
      await api.post('/payments/', payload)
      success.value = '回款已保存'
      router.push('/payments')
    } else {
      await api.patch(`/payments/${paymentId.value}/`, payload)
      success.value = '回款已更新'
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

onMounted(async () => {
  await fetchAccounts()
  await fetchContracts()
  if (!isNew.value) {
    await fetchPayment()
  }
})

watch(contractSearch, (val) => {
  if (!val) {
    form.value.contract = null
  }
})
</script>

<style scoped>
.filter-autocomplete {
  position: relative;
}

.filter-suggestions {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
  max-height: 220px;
  overflow: auto;
  z-index: 20;
}

.filter-suggestion {
  padding: 8px 10px;
  cursor: pointer;
}

.filter-suggestion:hover {
  background: #f1f5f9;
}

.filter-empty {
  padding: 8px 10px;
  color: #94a3b8;
}
</style>
