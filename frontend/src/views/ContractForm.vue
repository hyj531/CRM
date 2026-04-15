<template>
  <div class="opportunity-detail contract-detail">
    <div class="detail-header">
      <div class="detail-title-wrap">
        <button class="back-button" type="button" @click="goBack" aria-label="返回">←</button>
        <div>
          <div class="detail-title">{{ headerTitle }}</div>
          <div class="detail-meta">
            <span>状态：{{ statusLabel(form.status) }}</span>
            <span>审批：{{ approvalLabel(form.approval_status) }}</span>
            <span>甲方：{{ selectedAccountLabel || '-' }}</span>
            <span>金额：{{ formatMoney(form.amount) }}</span>
            <span>当前产值：{{ formatMoney(form.current_output) }}</span>
            <span>应收款：{{ receivableAmount || '-' }}</span>
            <span>签署日期：{{ form.signed_at || '-' }}</span>
            <span>创建人：{{ form.created_by_name || '-' }}</span>
            <span>创建日期：{{ formatDate(form.created_at) }}</span>
            <span>更新人：{{ form.updated_by_name || '-' }}</span>
            <span>更新日期：{{ formatDate(form.updated_at) }}</span>
          </div>
        </div>
      </div>
      <div class="page-actions">
        <button class="button" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : (isEdit ? '保存修改' : '保存合同') }}
        </button>
        <button
          v-if="showStartRevision"
          class="button secondary"
          :disabled="startingRevision"
          @click="startRevision"
        >
          {{ startingRevision ? '处理中...' : '发起修订' }}
        </button>
        <button
          v-if="showContractSubmitApproval"
          class="button secondary"
          :disabled="submittingApproval"
          @click="submitApproval"
        >
          {{ submittingApproval ? '提交中...' : '提交审批' }}
        </button>
        <button class="button secondary" @click="cancel">取消</button>
      </div>
    </div>

    <div v-if="error" style="color: #c92a2a; margin-bottom: 10px;">{{ error }}</div>
    <div v-if="success" style="color: #2b8a3e; margin-bottom: 10px;">{{ success }}</div>
    <div v-if="pendingApprovalReadonly" style="color: #888; margin-bottom: 10px;">
      合同审批进行中，除合同状态外主信息只读。
    </div>
    <div v-else-if="approvedReadonly" style="color: #888; margin-bottom: 10px;">
      合同已审批通过：仅可修改签署日期、合同状态和上传附件；修改其它字段请先点击“发起修订”并重新提交审批。
    </div>

    <div class="card">
      <div class="section-title">审批进度</div>
      <div v-if="approvalProgressLoading" style="color: #888;">审批进度加载中...</div>
      <div v-else-if="approvalProgressError" style="color: #c92a2a;">{{ approvalProgressError }}</div>
      <div v-else-if="!approvalProgress?.has_instance" style="color: #888;">暂无审批记录</div>
      <div v-else class="form-grid">
        <div>
          <label>流程状态</label>
          <input :value="approvalInstanceStatusLabel(approvalProgress.instance_status)" disabled />
        </div>
        <div>
          <label>当前步骤</label>
          <input :value="approvalProgress.current_step_name || '-'" disabled />
        </div>
        <div>
          <label>当前审批人</label>
          <input :value="approvalProgressApprovers || '-'" disabled />
        </div>
        <div>
          <label>最近动作</label>
          <input :value="approvalProgressLatestActionLabel" disabled />
        </div>
      </div>
      <div v-if="approvalProgress?.has_instance" style="margin-top: 10px;">
        <button class="button secondary" @click="openApprovalDetail">查看审批详情</button>
      </div>
    </div>

    <div class="card">
      <div class="section-title">合同信息</div>
      <div class="form-grid">
        <div>
          <label>合同编号</label>
          <input
            v-model="form.contract_no"
            :disabled="contractNoReadonly"
            :placeholder="isEdit ? '合同编号' : '保存后自动生成（YYYYMMDD001）'"
          />
          <div v-if="!isEdit" style="font-size: 12px; color: #888; margin-top: 4px;">
            保存后自动生成（YYYYMMDD001）
          </div>
        </div>
        <div>
          <label>合同名称</label>
          <input v-model="form.name" :disabled="contractMainReadonly" placeholder="合同名称" />
        </div>
        <div>
          <label>关联甲方</label>
          <div class="account-picker">
            <div class="account-search">
              <input
                v-model="accountQuery"
                :disabled="contractMainReadonly"
                placeholder="输入甲方全称/简称，自动搜索"
                @focus="handleAccountFocus"
                @blur="handleAccountBlur"
              />
              <button class="button secondary" type="button" :disabled="contractMainReadonly" @click="triggerSearch">搜索</button>
              <button v-if="form.account" class="button secondary" type="button" :disabled="contractMainReadonly" @click="clearAccount">
                清除
              </button>
            </div>
            <div v-if="showAccountDropdown && searchHint" class="account-hint">{{ searchHint }}</div>
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
                :disabled="contractMainReadonly"
                @click="selectAccount(acc)"
              >
                {{ acc.full_name }}{{ acc.short_name ? `（${acc.short_name}）` : '' }}
              </button>
            </div>
            <div v-if="showQuickCreate && !contractMainReadonly" class="account-create">
              <div class="section-title">新增甲方</div>
              <div class="form-grid">
                <div>
                  <label>甲方全称</label>
                  <input v-model="accountCreate.full_name" placeholder="甲方全称" />
                </div>
                <div>
                  <label>甲方简称</label>
                  <input v-model="accountCreate.short_name" placeholder="甲方简称" />
                </div>
              </div>
              <div style="margin-top: 10px;">
                <button class="button" type="button" :disabled="accountCreateSaving" @click="createAccount">
                  {{ accountCreateSaving ? '保存中...' : '保存甲方' }}
                </button>
                <span v-if="accountCreateError" style="margin-left: 10px; color: #c92a2a;">
                  {{ accountCreateError }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div>
          <label>乙方公司</label>
          <select v-model.number="form.vendor_company" :disabled="contractMainReadonly">
            <option :value="null">请选择乙方公司</option>
            <option v-for="opt in lookupOptions.vendor_company" :key="opt.id" :value="opt.id">
              {{ opt.name }}
            </option>
          </select>
        </div>
        <div>
          <label>关联商机</label>
          <select v-model.number="form.opportunity" :disabled="contractMainReadonly">
            <option :value="null">未关联</option>
            <option v-for="opp in opportunities" :key="opp.id" :value="opp.id">
              {{ opp.opportunity_name }}
            </option>
          </select>
        </div>
        <div>
          <label>所属区域</label>
          <select v-model.number="form.region" :disabled="contractMainReadonly">
            <option :value="null">默认所属区域</option>
            <option v-for="region in regions" :key="region.id" :value="region.id">
              {{ region.name || region.code || `ID ${region.id}` }}
            </option>
          </select>
        </div>
        <div>
          <label>负责人</label>
          <select v-model.number="form.owner" :disabled="contractMainReadonly">
            <option :value="null">默认负责人</option>
            <option v-for="u in users" :key="u.id" :value="u.id">
              {{ u.username || u.email || `ID ${u.id}` }}
            </option>
          </select>
        </div>
        <div>
          <label>是否为框架合同</label>
          <select v-model="form.is_framework" :disabled="contractMainReadonly">
            <option :value="false">否</option>
            <option :value="true">是</option>
          </select>
        </div>
        <div>
          <label>所属框架合同</label>
          <select v-model.number="form.framework_contract" :disabled="contractMainReadonly || form.is_framework">
            <option :value="null">不选择</option>
            <option v-for="item in frameworkContracts" :key="item.id" :value="item.id">
              {{ frameworkLabel(item) }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-title">金额与状态</div>
      <div class="form-grid">
        <div>
          <label>合同金额</label>
          <input v-model.number="form.amount" :disabled="contractMainReadonly" type="number" />
        </div>
        <div>
          <label>当前产值</label>
          <input v-model.number="form.current_output" :disabled="contractMainReadonly" type="number" />
        </div>
        <div>
          <label>应收款</label>
          <input :value="receivableAmount" type="number" disabled />
        </div>
        <div>
          <label>最终结算金额</label>
          <input v-model.number="form.final_settlement_amount" :disabled="contractMainReadonly" type="number" />
        </div>
        <div>
          <label>合同状态</label>
          <select v-model="form.status">
            <option value="draft">草稿</option>
            <option value="signed">已签署</option>
            <option value="closed">已关闭</option>
          </select>
        </div>
        <div>
          <label>审批状态</label>
          <input
            v-if="contractApprovalEnabled"
            :value="approvalLabel(form.approval_status)"
            disabled
          />
          <select v-else v-model="form.approval_status" :disabled="contractMainReadonly">
            <option value="pending">待审批</option>
            <option value="approved">已通过</option>
            <option value="rejected">已驳回</option>
            <option value="revising">修订中</option>
          </select>
        </div>
        <div>
          <label>签署日期</label>
          <input v-model="form.signed_at" :disabled="pendingApprovalReadonly" type="date" />
        </div>
        <div>
          <label>生效日期</label>
          <input v-model="form.start_date" :disabled="contractMainReadonly" type="date" />
        </div>
        <div>
          <label>到期日期</label>
          <input v-model="form.end_date" :disabled="contractMainReadonly" type="date" />
        </div>
        <div style="grid-column: 1 / -1;">
          <label>备注</label>
          <textarea v-model="form.remark" :disabled="contractMainReadonly" rows="3"></textarea>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-title">附件</div>
      <div v-if="!isEdit" style="color: #888;">保存合同后可上传附件</div>
      <div v-else>
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

    <div class="card">
      <div class="section-title">回款明细</div>
      <div v-if="!isEdit" style="color: #888;">保存合同后可录入回款明细</div>
      <div v-else>
        <div class="form-grid">
          <div>
            <label>回款金额</label>
            <input v-model.number="paymentForm.amount" type="number" />
          </div>
          <div>
            <label>回款时间</label>
            <input v-model="paymentForm.paid_at" type="date" />
          </div>
          <div style="grid-column: 1 / -1;">
            <label>回款说明</label>
            <textarea v-model="paymentForm.note" rows="3"></textarea>
          </div>
          <div>
            <label>所属区域</label>
            <select v-model.number="paymentForm.region">
              <option :value="null">请选择所属区域</option>
              <option v-for="r in regions" :key="r.id" :value="r.id">
                {{ r.name || r.code || `ID ${r.id}` }}
              </option>
            </select>
          </div>
          <div>
            <label>负责人</label>
            <select v-model.number="paymentForm.owner">
              <option :value="null">请选择负责人</option>
              <option v-for="u in users" :key="u.id" :value="u.id">
                {{ u.username || u.email || `ID ${u.id}` }}
              </option>
            </select>
          </div>
        </div>
        <div style="margin-top: 10px;">
          <button class="button" :disabled="paymentSaving || !paymentForm.amount" @click="savePayment">
            {{ paymentSaving ? '保存中...' : (editingPaymentId ? '保存修改' : '保存回款') }}
          </button>
          <button
            v-if="editingPaymentId"
            class="button secondary"
            style="margin-left: 8px;"
            @click="cancelEditPayment"
          >
            取消编辑
          </button>
          <span v-if="paymentError" style="margin-left: 10px; color: #c92a2a;">{{ paymentError }}</span>
          <span v-if="paymentSuccess" style="margin-left: 10px; color: #2b8a3e;">{{ paymentSuccess }}</span>
        </div>
        <div style="margin-top: 12px;">
          <table class="table" v-if="payments.length">
            <thead>
              <tr>
                <th>回款金额</th>
              <th>回款时间</th>
              <th>状态</th>
              <th>所属区域</th>
              <th>负责人</th>
              <th>录入人</th>
              <th>回款说明</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
              <tr v-for="item in payments" :key="item.id">
                <td>{{ item.amount }}</td>
                <td>{{ item.paid_at || '-' }}</td>
                <td>{{ paymentStatusLabel(item.status) }}</td>
                <td>{{ item.region_name || item.region || '-' }}</td>
                <td>{{ item.owner_name || item.owner || '-' }}</td>
                <td>{{ item.created_by_name || item.created_by || '-' }}</td>
                <td>{{ item.note || '-' }}</td>
                <td>{{ item.created_at || '-' }}</td>
                <td>
                  <button class="button secondary" @click="startEditPayment(item)">编辑</button>
                  <button class="button secondary" @click="deletePayment(item.id)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else style="color: #888;">暂无回款记录</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-title">开票明细</div>
      <div v-if="!isEdit" style="color: #888;">保存合同后可录入开票明细</div>
      <div v-else>
        <div class="invoice-toolbar">
          <button class="button" :disabled="invoiceSaving || invoiceSubmitting" @click="openCreateInvoiceModal">
            新增开票申请
          </button>
          <span v-if="!showInvoiceModal && invoiceError" style="margin-left: 10px; color: #c92a2a;">{{ invoiceError }}</span>
          <span v-if="!showInvoiceModal && invoiceSuccess" style="margin-left: 10px; color: #2b8a3e;">{{ invoiceSuccess }}</span>
        </div>
        <div style="margin-top: 12px;">
          <table class="table" v-if="invoices.length">
            <thead>
              <tr>
                <th>开票编号</th>
                <th>开票金额</th>
                <th>开票时间</th>
                <th>税率</th>
                <th>类型</th>
                <th>状态</th>
                <th>审批</th>
                <th>名称</th>
                <th>纳税人识别号</th>
                <th>地址</th>
                <th>电话</th>
                <th>开户银行</th>
                <th>银行账号</th>
                <th>所属区域</th>
                <th>负责人</th>
                <th>时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in invoices" :key="item.id">
                <td>{{ item.invoice_no || '-' }}</td>
                <td>{{ item.amount }}</td>
                <td>{{ item.issued_at || '-' }}</td>
                <td>{{ item.tax_rate ?? '-' }}</td>
                <td>{{ invoiceTypeLabel(item.invoice_type) }}</td>
                <td>{{ invoiceStatusLabel(item.status) }}</td>
                <td>{{ approvalLabel(item.approval_status) }}</td>
                <td>{{ item.billing_name || '-' }}</td>
                <td>{{ item.taxpayer_no || '-' }}</td>
                <td>{{ item.billing_address || '-' }}</td>
                <td>{{ item.billing_phone || '-' }}</td>
                <td>{{ item.billing_bank_name || '-' }}</td>
                <td>{{ item.billing_bank_account || '-' }}</td>
                <td>{{ item.region_name || item.region || '-' }}</td>
                <td>{{ item.owner_name || item.owner || '-' }}</td>
                <td>{{ item.created_at || '-' }}</td>
                <td>
                  <router-link class="link-button" :to="`/invoices/${item.id}`">详情</router-link>
                  <button class="button secondary" @click="startEditInvoice(item)">编辑</button>
                  <button class="button secondary" @click="deleteInvoice(item.id)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else style="color: #888;">暂无开票记录</div>
        </div>

        <div v-if="showInvoiceModal" class="modal-backdrop" @click.self="closeInvoiceModal">
          <div class="modal-card invoice-modal-card">
            <div class="modal-header">
              <div class="modal-title">{{ invoiceModalMode === 'edit' ? '编辑开票申请' : '新增开票申请' }}</div>
            </div>
            <div class="form-grid">
              <div>
                <label>开票编号</label>
                <input v-model="invoiceForm.invoice_no" />
              </div>
              <div>
                <label>名称</label>
                <input v-model="invoiceForm.billing_name" placeholder="名称" />
              </div>
              <div>
                <label>纳税人识别号 *</label>
                <input v-model="invoiceForm.taxpayer_no" placeholder="纳税人识别号" />
              </div>
              <div>
                <label>地址 *</label>
                <input v-model="invoiceForm.billing_address" placeholder="地址" />
              </div>
              <div>
                <label>电话 *</label>
                <input v-model="invoiceForm.billing_phone" placeholder="电话" />
              </div>
              <div>
                <label>开户银行 *</label>
                <input v-model="invoiceForm.billing_bank_name" placeholder="开户银行" />
              </div>
              <div>
                <label>银行账号 *</label>
                <input v-model="invoiceForm.billing_bank_account" placeholder="银行账号" />
              </div>
              <div>
                <label>开票金额</label>
                <input v-model.number="invoiceForm.amount" type="number" />
              </div>
              <div>
                <label>开票时间</label>
                <input v-model="invoiceForm.issued_at" type="date" />
              </div>
              <div>
                <label>税率</label>
                <input v-model.number="invoiceForm.tax_rate" type="number" step="0.01" />
              </div>
              <div>
                <label>开票类型</label>
                <select v-model="invoiceForm.invoice_type">
                  <option value="normal">普票</option>
                  <option value="special">专票</option>
                </select>
              </div>
              <div>
                <label>开票状态</label>
                <select v-model="invoiceForm.status">
                  <option value="draft">草稿</option>
                  <option value="issued">已开票</option>
                  <option value="paid">已回款</option>
                  <option value="void">已作废</option>
                </select>
              </div>
              <div>
                <label>所属区域</label>
                <select v-model.number="invoiceForm.region">
                  <option :value="null">请选择所属区域</option>
                  <option v-for="r in regions" :key="r.id" :value="r.id">
                    {{ r.name || r.code || `ID ${r.id}` }}
                  </option>
                </select>
              </div>
              <div>
                <label>负责人</label>
                <select v-model.number="invoiceForm.owner">
                  <option :value="null">请选择负责人</option>
                  <option v-for="u in users" :key="u.id" :value="u.id">
                    {{ u.username || u.email || `ID ${u.id}` }}
                  </option>
                </select>
              </div>
            </div>
            <div class="modal-actions">
              <button class="button" :disabled="invoiceSaving || invoiceSubmitting || !invoiceForm.amount" @click="saveInvoice">
                {{ invoiceSaving ? '保存中...' : '保存开票' }}
              </button>
              <button
                v-if="invoiceApprovalEnabled"
                class="button secondary"
                :disabled="invoiceSaving || invoiceSubmitting || !invoiceForm.amount"
                @click="submitInvoiceForApproval"
              >
                {{ invoiceSubmitting ? '提交中...' : '提交开票申请' }}
              </button>
              <button
                class="button secondary"
                :disabled="invoiceSaving || invoiceSubmitting"
                @click="closeInvoiceModal"
              >
                取消
              </button>
              <span v-if="invoiceError" style="margin-left: 10px; color: #c92a2a;">{{ invoiceError }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="isEdit && form.is_framework" class="card">
      <div class="section-title">合同明细</div>
      <div v-if="childContractsError" style="color: #c92a2a; margin-bottom: 8px;">
        {{ childContractsError }}
      </div>
      <div class="table-wrap contract-table-wrap">
        <table class="table contract-table">
          <thead>
            <tr>
              <th>合同名称</th>
              <th>合同状态</th>
              <th>审批状态</th>
              <th>甲方</th>
              <th>乙方</th>
              <th>合同金额</th>
              <th>回款</th>
              <th>当前产值</th>
              <th>应收款</th>
              <th>签署日期</th>
              <th>区域</th>
              <th>负责人</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in childContracts" :key="item.id">
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">
                  {{ item.name || item.contract_no || `合同${item.id}` }}
                </router-link>
              </td>
              <td>
                <span :class="['badge', statusBadgeClass(item.status)]">{{ statusLabel(item.status) }}</span>
              </td>
              <td>
                <span :class="['badge', approvalBadgeClass(item.approval_status)]">
                  {{ approvalLabel(item.approval_status) }}
                </span>
              </td>
              <td>{{ item.account_name || item.account || '-' }}</td>
              <td>{{ vendorName(item.vendor_company) }}</td>
              <td>{{ formatMoney(item.amount) }}</td>
              <td>{{ formatMoney(item.paid_total) }}</td>
              <td>{{ item.current_output ?? '-' }}</td>
              <td>{{ receivableAmountFor(item) }}</td>
              <td>{{ item.signed_at || '-' }}</td>
              <td>{{ item.region_name || '-' }}</td>
              <td>{{ item.owner_name || item.owner || '-' }}</td>
              <td>
                <router-link class="link-button" :to="`/contracts/${item.id}`">详情</router-link>
              </td>
            </tr>
            <tr v-if="!childContracts.length">
              <td colspan="13" style="color: #888;">暂无合同明细</td>
            </tr>
          </tbody>
        </table>
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
const saving = ref(false)
const submittingApproval = ref(false)
const error = ref('')
const success = ref('')
const opportunities = ref([])
const regions = ref([])
const users = ref([])
const frameworkContracts = ref([])
const childContracts = ref([])
const childContractsError = ref('')
const attachments = ref([])
const attachmentForm = ref({
  file: null,
  description: ''
})
const uploading = ref(false)
const uploadError = ref('')
const payments = ref([])
const paymentForm = ref({
  amount: null,
  paid_at: '',
  note: '',
  region: null,
  owner: null
})
const editingPaymentId = ref(null)
const paymentSaving = ref(false)
const paymentError = ref('')
const paymentSuccess = ref('')
const invoices = ref([])
const invoiceForm = ref({
  invoice_no: '',
  billing_name: '',
  taxpayer_no: '',
  billing_address: '',
  billing_phone: '',
  billing_bank_name: '',
  billing_bank_account: '',
  amount: null,
  issued_at: '',
  tax_rate: null,
  invoice_type: 'normal',
  status: 'draft',
  region: null,
  owner: null
})
const editingInvoiceId = ref(null)
const invoiceSaving = ref(false)
const invoiceSubmitting = ref(false)
const invoiceError = ref('')
const invoiceSuccess = ref('')
const showInvoiceModal = ref(false)
const invoiceModalMode = ref('create')
const paidTotal = ref(0)
const lookupOptions = ref({
  vendor_company: []
})
const accountOptions = ref([])
const accountQuery = ref('')
const accountLoading = ref(false)
const selectedAccount = ref(null)
const accountFocused = ref(false)
let accountBlurTimer = null
const accountCreate = ref({
  full_name: '',
  short_name: ''
})
const accountCreateSaving = ref(false)
const accountCreateError = ref('')
const approvalProgressLoading = ref(false)
const approvalProgressError = ref('')
const approvalProgress = ref(null)
const startingRevision = ref(false)

const form = ref({
  contract_no: '',
  name: '',
  account: null,
  vendor_company: null,
  opportunity: null,
  region: null,
  owner: null,
  amount: null,
  current_output: null,
  final_settlement_amount: null,
  status: 'draft',
  approval_status: 'pending',
  is_framework: false,
  framework_contract: null,
  remark: '',
  created_by_name: '',
  created_at: '',
  updated_by_name: '',
  updated_at: '',
  signed_at: '',
  start_date: '',
  end_date: ''
})

const isEdit = computed(() => Boolean(route.params.id))
const isAdmin = computed(() => Boolean(auth.user?.is_staff || auth.user?.is_superuser))
const contractApprovalEnabled = computed(() => auth.user?.approval_switches?.contract !== false)
const invoiceApprovalEnabled = computed(() => auth.user?.approval_switches?.invoice !== false)
const pendingApprovalReadonly = computed(() => (
  isEdit.value
  && contractApprovalEnabled.value
  && approvalProgress.value?.has_instance
  && approvalProgress.value?.instance_status === 'pending'
))
const approvedReadonly = computed(() => (
  isEdit.value
  && contractApprovalEnabled.value
  && form.value.approval_status === 'approved'
))
const contractMainReadonly = computed(() => pendingApprovalReadonly.value || approvedReadonly.value)
const contractNoReadonly = computed(() => !isEdit.value || contractMainReadonly.value || !isAdmin.value)
const showContractSubmitApproval = computed(() => (
  isEdit.value
  && contractApprovalEnabled.value
  && !pendingApprovalReadonly.value
  && form.value.approval_status !== 'approved'
))
const showStartRevision = computed(() => (
  isEdit.value
  && contractApprovalEnabled.value
  && approvedReadonly.value
))
const approvalProgressApprovers = computed(() => {
  const items = Array.isArray(approvalProgress.value?.pending_approvers) ? approvalProgress.value.pending_approvers : []
  if (!items.length) return ''
  return items.map((item) => item.username).filter(Boolean).join('、')
})
const approvalProgressLatestActionLabel = computed(() => {
  const action = approvalProgress.value?.latest_action
  if (!action) return '-'
  const actor = action.actor_name || '-'
  const when = formatDate(action.created_at)
  return `${approvalActionLabel(action.action)} · ${actor} · ${when}`
})
const headerTitle = computed(() => {
  if (!isEdit.value) return '新建合同'
  return form.value.name || form.value.contract_no || '合同详情'
})

const statusLabel = (value) => {
  const map = {
    draft: '草稿',
    signed: '已签署',
    active: '执行中',
    closed: '已关闭'
  }
  return map[value] || value || '-'
}

const approvalLabel = (value) => {
  const map = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回',
    revising: '修订中'
  }
  return map[value] || value || '-'
}

const approvalInstanceStatusLabel = (value) => {
  const map = {
    pending: '审批中',
    approved: '已通过',
    rejected: '已驳回',
    withdrawn: '已撤回'
  }
  return map[value] || '-'
}

const approvalActionLabel = (value) => {
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

const statusBadgeClass = (value) => {
  if (value === 'active') return 'green'
  if (value === 'closed') return 'gray'
  return 'orange'
}

const approvalBadgeClass = (value) => {
  if (value === 'approved') return 'green'
  if (value === 'revising') return 'orange'
  if (value === 'rejected') return 'gray'
  return 'orange'
}

const vendorName = (vendorId) => {
  const item = lookupOptions.value.vendor_company.find((opt) => String(opt.id) === String(vendorId))
  return item ? item.name : (vendorId || '-')
}

const frameworkLabel = (item) => {
  if (!item) return '-'
  return item.name || item.contract_no || `合同${item.id}`
}

const formatMoney = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
}

const formatDate = (value) => {
  if (!value) return '-'
  if (typeof value === 'string') return value.slice(0, 10)
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toISOString().slice(0, 10)
}

const fetchLookups = async () => {
  const res = await api.get('/lookups/')
  const categories = Array.isArray(res.data?.results) ? res.data.results : res.data
  const pick = (code) => {
    const cat = categories.find((c) => c.code === code)
    return cat ? cat.options : []
  }
  lookupOptions.value = {
    vendor_company: pick('vendor_company')
  }
}

const fetchOpportunities = async () => {
  const res = await api.get('/opportunities/', { params: { page: 1, page_size: 1000 } })
  opportunities.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchRegions = async () => {
  const res = await api.get('/regions/', { params: { page: 1, page_size: 1000 } })
  regions.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchUsers = async () => {
  const res = await api.get('/users/', { params: { page: 1, page_size: 200, ordering: 'username' } })
  users.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const fetchFrameworkContracts = async () => {
  try {
    const res = await api.get('/contracts/', { params: { is_framework: 1, page: 1, page_size: 1000 } })
    frameworkContracts.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    frameworkContracts.value = []
  }
}

const fetchChildContracts = async () => {
  if (!isEdit.value || !form.value.is_framework) {
    childContracts.value = []
    return
  }
  childContractsError.value = ''
  try {
    const res = await api.get('/contracts/', {
      params: { framework_contract: route.params.id, page: 1, page_size: 1000, ordering: '-created_at' }
    })
    childContracts.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  } catch (err) {
    childContracts.value = []
    childContractsError.value = '加载合同明细失败'
  }
}

let searchTimer = null

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
  try {
    const res = await api.get(`/accounts/${id}/`)
    return res.data
  } catch (err) {
    return null
  }
}

const triggerSearch = () => {
  const query = accountQuery.value.trim()
  if (!query) {
    return
  }
  if (query.length < 2) {
    return
  }
  loadAccounts(query)
}

const searchHint = computed(() => {
  const query = accountQuery.value.trim()
  if (!query) return ''
  if (query.length < 2) return '请输入至少 2 个字'
  return ''
})

const selectAccount = (acc) => {
  form.value.account = acc.id
  selectedAccount.value = acc
  accountQuery.value = acc.full_name || acc.short_name || ''
  accountFocused.value = false
}

const clearAccount = () => {
  form.value.account = null
  selectedAccount.value = null
  accountQuery.value = ''
}

const selectedAccountLabel = computed(() => {
  if (!form.value.account) return ''
  const acc = selectedAccount.value || accountOptions.value.find((item) => item.id === form.value.account)
  if (!acc) return `ID ${form.value.account}`
  return `${acc.full_name}${acc.short_name ? `（${acc.short_name}）` : ''}`
})
const showAccountDropdown = computed(() => accountFocused.value && accountQuery.value.trim().length > 0)
const applyDefaultOwnerRegion = () => {
  if (isEdit.value) return
  if (form.value.region == null && auth.user?.region != null) {
    form.value.region = Number(auth.user.region)
  }
  if (form.value.owner == null && auth.user?.id != null) {
    form.value.owner = Number(auth.user.id)
  }
}

const applyPaymentDefaults = () => {
  if (paymentForm.value.region == null && form.value.region != null) {
    paymentForm.value.region = Number(form.value.region)
  }
  if (paymentForm.value.owner == null && form.value.owner != null) {
    paymentForm.value.owner = Number(form.value.owner)
  }
}

const applyInvoiceDefaults = () => {
  if (invoiceForm.value.region == null && form.value.region != null) {
    invoiceForm.value.region = Number(form.value.region)
  }
  if (invoiceForm.value.owner == null && form.value.owner != null) {
    invoiceForm.value.owner = Number(form.value.owner)
  }
}

const resetPaymentForm = () => {
  paymentForm.value = {
    amount: null,
    paid_at: '',
    note: '',
    region: form.value.region != null ? Number(form.value.region) : null,
    owner: form.value.owner != null ? Number(form.value.owner) : null
  }
}

const resetInvoiceForm = () => {
  invoiceForm.value = {
    invoice_no: '',
    billing_name: '',
    taxpayer_no: '',
    billing_address: '',
    billing_phone: '',
    billing_bank_name: '',
    billing_bank_account: '',
    amount: null,
    issued_at: '',
    tax_rate: null,
    invoice_type: 'normal',
    status: 'draft',
    region: form.value.region != null ? Number(form.value.region) : null,
    owner: form.value.owner != null ? Number(form.value.owner) : null
  }
}

const fillInvoiceBillingFromLastInvoice = async () => {
  const accountId = form.value.account != null ? Number(form.value.account) : null
  if (!accountId) return
  try {
    const res = await api.get('/invoices/', {
      params: {
        account: accountId,
        page: 1,
        page_size: 1,
        ordering: '-created_at'
      }
    })
    const list = Array.isArray(res.data?.results) ? res.data.results : (Array.isArray(res.data) ? res.data : [])
    const latest = list[0]
    if (!latest) return
    invoiceForm.value.billing_name = latest.billing_name || ''
    invoiceForm.value.taxpayer_no = latest.taxpayer_no || ''
    invoiceForm.value.billing_address = latest.billing_address || ''
    invoiceForm.value.billing_phone = latest.billing_phone || ''
    invoiceForm.value.billing_bank_name = latest.billing_bank_name || ''
    invoiceForm.value.billing_bank_account = latest.billing_bank_account || ''
  } catch (err) {
    // ignore autofill failure to avoid blocking creation
  }
}

const openCreateInvoiceModal = async () => {
  editingInvoiceId.value = null
  invoiceModalMode.value = 'create'
  resetInvoiceForm()
  applyInvoiceDefaults()
  invoiceError.value = ''
  invoiceSuccess.value = ''
  showInvoiceModal.value = true
  await fillInvoiceBillingFromLastInvoice()
}

const closeInvoiceModal = () => {
  if (invoiceSaving.value || invoiceSubmitting.value) return
  showInvoiceModal.value = false
  editingInvoiceId.value = null
  invoiceModalMode.value = 'create'
  resetInvoiceForm()
  invoiceError.value = ''
}

const showQuickCreate = computed(() => {
  const query = accountQuery.value.trim()
  return query && query.length >= 2 && !accountOptions.value.length
})

const receivableAmount = computed(() => {
  const base = form.value.current_output != null ? Number(form.value.current_output) : Number(form.value.amount)
  if (Number.isNaN(base)) return ''
  const total = Number(paidTotal.value) || 0
  const value = base - total
  return Number.isFinite(value) ? value.toFixed(2) : ''
})

const receivableAmountFor = (item) => {
  if (!item) return '-'
  const paidTotal = Number(item.paid_total || 0)
  const base = item.current_output != null ? Number(item.current_output) : Number(item.amount)
  if (Number.isNaN(base)) return '-'
  const value = base - paidTotal
  return Number.isFinite(value) ? value.toFixed(2) : '-'
}

const handleAccountFocus = () => {
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
    accountBlurTimer = null
  }
  accountFocused.value = true
}

const handleAccountBlur = () => {
  if (accountBlurTimer) {
    clearTimeout(accountBlurTimer)
  }
  accountBlurTimer = setTimeout(() => {
    accountFocused.value = false
  }, 150)
}

const paymentStatusLabel = (value) => {
  const map = {
    planned: '计划中',
    partial: '部分回款',
    paid: '已回款'
  }
  return map[value] || value || '-'
}

const invoiceStatusLabel = (value) => {
  const map = {
    draft: '草稿',
    issued: '已开票',
    paid: '已回款',
    void: '已作废'
  }
  return map[value] || value || '-'
}

const invoiceTypeLabel = (value) => {
  const map = {
    normal: '普票',
    special: '专票'
  }
  return map[value] || value || '-'
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

const createAccount = async () => {
  if (!accountCreate.value.full_name) {
    accountCreateError.value = '甲方全称不能为空'
    return
  }
  accountCreateError.value = ''
  accountCreateSaving.value = true
  try {
    const payload = {
      full_name: accountCreate.value.full_name,
      short_name: accountCreate.value.short_name || ''
    }
    const res = await api.post('/accounts/', payload)
    const created = res.data
    selectedAccount.value = created
    form.value.account = created.id
    accountOptions.value = [created, ...accountOptions.value]
    accountQuery.value = created.full_name
    accountCreate.value = { full_name: '', short_name: '' }
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      accountCreateError.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      accountCreateError.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    accountCreateSaving.value = false
  }
}

const loadContract = async () => {
  if (!isEdit.value) return
  try {
    const res = await api.get(`/contracts/${route.params.id}/`)
    const data = res.data
    form.value = {
      contract_no: data.contract_no || '',
      name: data.name || '',
      account: data.account != null ? Number(data.account) : null,
      vendor_company: data.vendor_company != null ? Number(data.vendor_company) : null,
      opportunity: data.opportunity != null ? Number(data.opportunity) : null,
      region: data.region != null ? Number(data.region) : null,
      owner: data.owner != null ? Number(data.owner) : null,
      amount: data.amount != null ? Number(data.amount) : null,
      current_output: data.current_output != null ? Number(data.current_output) : null,
      final_settlement_amount: data.final_settlement_amount != null ? Number(data.final_settlement_amount) : null,
      status: data.status || 'draft',
      approval_status: data.approval_status || 'pending',
      is_framework: Boolean(data.is_framework),
      framework_contract: data.framework_contract != null ? Number(data.framework_contract) : null,
      remark: data.remark || '',
      created_by_name: data.created_by_name || '',
      created_at: data.created_at || '',
      updated_by_name: data.updated_by_name || '',
      updated_at: data.updated_at || '',
      signed_at: data.signed_at || '',
      start_date: data.start_date || '',
      end_date: data.end_date || ''
    }
    paidTotal.value = Number(data.paid_total || 0)
    if (form.value.account) {
      const acc = await fetchAccountById(form.value.account)
      if (acc) {
        selectedAccount.value = acc
        accountQuery.value = acc.full_name
        accountOptions.value = [acc, ...accountOptions.value.filter((item) => item.id !== acc.id)]
      }
    }
    if (!editingPaymentId.value) {
      applyPaymentDefaults()
    }
    if (!editingInvoiceId.value) {
      applyInvoiceDefaults()
    }
    await fetchChildContracts()
  } catch (err) {
    error.value = '加载合同失败，请确认该合同存在且有权限访问'
  }
}

const fetchApprovalProgress = async () => {
  if (!isEdit.value) {
    approvalProgress.value = null
    approvalProgressError.value = ''
    return
  }
  approvalProgressLoading.value = true
  approvalProgressError.value = ''
  try {
    const res = await api.get(`/contracts/${route.params.id}/approval_progress/`)
    approvalProgress.value = res.data || null
  } catch (err) {
    approvalProgress.value = null
    approvalProgressError.value = '审批进度加载失败'
  } finally {
    approvalProgressLoading.value = false
  }
}

const openApprovalDetail = () => {
  if (!approvalProgress.value?.has_instance || !approvalProgress.value?.instance_id) return
  router.push({
    name: 'approval-instance',
    params: { id: String(approvalProgress.value.instance_id) },
    query: { from: `contract:${route.params.id}` }
  })
}

const fetchAttachments = async () => {
  if (!isEdit.value) return
  const res = await api.get('/contract-attachments/', {
    params: { contract: route.params.id, ordering: '-created_at', page: 1, page_size: 50 }
  })
  attachments.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const onFileChange = (event) => {
  const file = event.target.files && event.target.files[0]
  attachmentForm.value.file = file || null
  uploadError.value = ''
}

const uploadAttachment = async () => {
  if (!attachmentForm.value.file || !isEdit.value) return
  uploading.value = true
  uploadError.value = ''
  try {
    const formData = new FormData()
    formData.append('contract', String(route.params.id))
    formData.append('file', attachmentForm.value.file)
    if (attachmentForm.value.description) {
      formData.append('description', attachmentForm.value.description)
    }
    await api.post('/contract-attachments/', formData)
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

const fetchPayments = async () => {
  if (!isEdit.value) return
  const res = await api.get('/payments/', {
    params: { contract: route.params.id, ordering: '-paid_at', page: 1, page_size: 50 }
  })
  payments.value = Array.isArray(res.data?.results) ? res.data.results : res.data
  paidTotal.value = payments.value.reduce((sum, item) => sum + (Number(item.amount) || 0), 0)
}

const fetchInvoices = async () => {
  if (!isEdit.value) return
  const res = await api.get('/invoices/', {
    params: { contract: route.params.id, ordering: '-issued_at', page: 1, page_size: 50 }
  })
  invoices.value = Array.isArray(res.data?.results) ? res.data.results : res.data
}

const startEditPayment = (item) => {
  editingPaymentId.value = item.id
  paymentForm.value = {
    amount: item.amount != null ? Number(item.amount) : null,
    paid_at: item.paid_at || '',
    note: item.note || '',
    region: item.region != null ? Number(item.region) : (form.value.region != null ? Number(form.value.region) : null),
    owner: item.owner != null ? Number(item.owner) : (form.value.owner != null ? Number(form.value.owner) : null)
  }
  paymentError.value = ''
  paymentSuccess.value = ''
}

const cancelEditPayment = () => {
  editingPaymentId.value = null
  resetPaymentForm()
  paymentError.value = ''
  paymentSuccess.value = ''
}

const startEditInvoice = (item) => {
  editingInvoiceId.value = item.id
  invoiceModalMode.value = 'edit'
  invoiceForm.value = {
    invoice_no: item.invoice_no || '',
    billing_name: item.billing_name || '',
    taxpayer_no: item.taxpayer_no || '',
    billing_address: item.billing_address || '',
    billing_phone: item.billing_phone || '',
    billing_bank_name: item.billing_bank_name || '',
    billing_bank_account: item.billing_bank_account || '',
    amount: item.amount != null ? Number(item.amount) : null,
    issued_at: item.issued_at || '',
    tax_rate: item.tax_rate != null ? Number(item.tax_rate) : null,
    invoice_type: item.invoice_type || 'normal',
    status: item.status || 'draft',
    region: item.region != null ? Number(item.region) : (form.value.region != null ? Number(form.value.region) : null),
    owner: item.owner != null ? Number(item.owner) : (form.value.owner != null ? Number(form.value.owner) : null)
  }
  invoiceError.value = ''
  invoiceSuccess.value = ''
  showInvoiceModal.value = true
}

const savePayment = async () => {
  if (!paymentForm.value.amount) {
    paymentError.value = '回款金额不能为空'
    return
  }
  if (!paymentForm.value.region) {
    paymentError.value = '请选择所属区域'
    return
  }
  if (!paymentForm.value.owner) {
    paymentError.value = '请选择负责人'
    return
  }
  paymentError.value = ''
  paymentSuccess.value = ''
  paymentSaving.value = true
  try {
    if (editingPaymentId.value) {
      const payload = {
        amount: Number(paymentForm.value.amount),
        paid_at: paymentForm.value.paid_at || null,
        note: paymentForm.value.note || '',
        region: Number(paymentForm.value.region),
        owner: Number(paymentForm.value.owner)
      }
      await api.patch(`/payments/${editingPaymentId.value}/`, payload)
      paymentSuccess.value = '回款已更新'
      editingPaymentId.value = null
      resetPaymentForm()
    } else {
      const payload = {
        contract: Number(route.params.id),
        amount: Number(paymentForm.value.amount),
        paid_at: paymentForm.value.paid_at || null,
        note: paymentForm.value.note || '',
        region: Number(paymentForm.value.region),
        owner: Number(paymentForm.value.owner),
        status: 'paid'
      }
      await api.post('/payments/', payload)
      resetPaymentForm()
      paymentSuccess.value = '回款已保存'
    }
    await fetchPayments()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      const messages = Object.entries(detail)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
        .join(' | ')
      paymentError.value = messages || '保存失败，请检查必填项或后端服务'
    } else {
      paymentError.value = '保存失败，请检查必填项或后端服务'
    }
  } finally {
    paymentSaving.value = false
  }
}

const saveInvoice = async () => {
  invoiceError.value = ''
  invoiceSuccess.value = ''
  invoiceSaving.value = true
  try {
    const result = await persistInvoice({ keepFormAfterSave: false })
    if (!result) return
    invoiceSuccess.value = result.edited ? '开票已更新' : '开票已保存'
    showInvoiceModal.value = false
    invoiceModalMode.value = 'create'
  } catch (err) {
    invoiceError.value = extractApiError(err, '保存失败，请检查必填项或后端服务')
  } finally {
    invoiceSaving.value = false
  }
}

const extractApiError = (err, fallback) => {
  const detail = err.response?.data
  if (detail && typeof detail === 'object') {
    if (typeof detail.detail === 'string' && detail.detail) {
      return detail.detail
    }
    const messages = Object.entries(detail)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
      .join(' | ')
    return messages || fallback
  }
  return fallback
}

const validateInvoiceForm = () => {
  if (!invoiceForm.value.amount) {
    invoiceError.value = '开票金额不能为空'
    return false
  }
  if (!invoiceForm.value.region) {
    invoiceError.value = '请选择所属区域'
    return false
  }
  if (!invoiceForm.value.owner) {
    invoiceError.value = '请选择负责人'
    return false
  }
  if (!invoiceForm.value.taxpayer_no?.trim()) {
    invoiceError.value = '纳税人识别号不能为空'
    return false
  }
  if (!invoiceForm.value.billing_address?.trim()) {
    invoiceError.value = '地址不能为空'
    return false
  }
  if (!invoiceForm.value.billing_phone?.trim()) {
    invoiceError.value = '电话不能为空'
    return false
  }
  if (!invoiceForm.value.billing_bank_name?.trim()) {
    invoiceError.value = '开户银行不能为空'
    return false
  }
  if (!invoiceForm.value.billing_bank_account?.trim()) {
    invoiceError.value = '银行账号不能为空'
    return false
  }
  return true
}

const buildInvoicePayload = () => ({
  invoice_no: invoiceForm.value.invoice_no || '',
  billing_name: invoiceForm.value.billing_name || '',
  taxpayer_no: invoiceForm.value.taxpayer_no || '',
  billing_address: invoiceForm.value.billing_address || '',
  billing_phone: invoiceForm.value.billing_phone || '',
  billing_bank_name: invoiceForm.value.billing_bank_name || '',
  billing_bank_account: invoiceForm.value.billing_bank_account || '',
  amount: Number(invoiceForm.value.amount),
  issued_at: invoiceForm.value.issued_at || null,
  tax_rate: invoiceForm.value.tax_rate === '' ? null : invoiceForm.value.tax_rate,
  invoice_type: invoiceForm.value.invoice_type || 'normal',
  status: invoiceForm.value.status || 'draft',
  region: Number(invoiceForm.value.region),
  owner: Number(invoiceForm.value.owner)
})

const persistInvoice = async ({ keepFormAfterSave = false } = {}) => {
  if (!validateInvoiceForm()) return null
  const isEditingInvoice = Boolean(editingInvoiceId.value)
  if (isEditingInvoice) {
    const invoiceId = Number(editingInvoiceId.value)
    await api.patch(`/invoices/${invoiceId}/`, buildInvoicePayload())
    if (!keepFormAfterSave) {
      editingInvoiceId.value = null
      resetInvoiceForm()
    }
    await fetchInvoices()
    return { id: invoiceId, edited: true }
  }
  const payload = {
    ...buildInvoicePayload(),
    contract: Number(route.params.id),
    account: form.value.account ? Number(form.value.account) : null
  }
  const res = await api.post('/invoices/', payload)
  const invoiceId = Number(res.data?.id)
  if (!Number.isFinite(invoiceId)) {
    throw new Error('开票保存成功但未返回有效ID')
  }
  if (keepFormAfterSave) {
    editingInvoiceId.value = invoiceId
    invoiceModalMode.value = 'edit'
  } else {
    resetInvoiceForm()
  }
  await fetchInvoices()
  return { id: invoiceId, edited: false }
}

const submitInvoiceForApproval = async () => {
  if (!invoiceApprovalEnabled.value) return
  invoiceError.value = ''
  invoiceSuccess.value = ''
  invoiceSubmitting.value = true
  let persistedMessage = ''
  try {
    const result = await persistInvoice({ keepFormAfterSave: true })
    if (!result) return
    persistedMessage = result.edited ? '开票已更新' : '开票已保存'
    await api.post(`/invoices/${result.id}/submit_approval/`)
    invoiceSuccess.value = `${persistedMessage}并提交审批`
    showInvoiceModal.value = false
    editingInvoiceId.value = null
    invoiceModalMode.value = 'create'
    resetInvoiceForm()
    await fetchInvoices()
  } catch (err) {
    const failure = extractApiError(err, '提交审批失败，请检查权限或流程配置')
    invoiceError.value = persistedMessage ? `${persistedMessage}，但${failure}` : failure
  } finally {
    invoiceSubmitting.value = false
  }
}

const deletePayment = async (id) => {
  if (!confirm('确认删除该回款记录？')) return
  paymentError.value = ''
  paymentSuccess.value = ''
  try {
    await api.delete(`/payments/${id}/`)
    paymentSuccess.value = '回款已删除'
    if (editingPaymentId.value === id) {
      cancelEditPayment()
    }
    await fetchPayments()
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      paymentError.value = '无删除权限'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        paymentError.value = detail.detail || '删除失败，请检查权限或后端服务'
      } else {
        paymentError.value = '删除失败，请检查权限或后端服务'
      }
    }
  }
}

const deleteInvoice = async (id) => {
  if (!confirm('确认删除该开票记录？')) return
  invoiceError.value = ''
  invoiceSuccess.value = ''
  try {
    await api.delete(`/invoices/${id}/`)
    invoiceSuccess.value = '开票已删除'
    if (editingInvoiceId.value === id) {
      closeInvoiceModal()
    }
    await fetchInvoices()
  } catch (err) {
    const status = err.response?.status
    if (status === 403) {
      invoiceError.value = '无删除权限'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        invoiceError.value = detail.detail || '删除失败，请检查权限或后端服务'
      } else {
        invoiceError.value = '删除失败，请检查权限或后端服务'
      }
    }
  }
}

const normalizePayload = () => {
  if (isEdit.value && approvedReadonly.value) {
    return {
      signed_at: form.value.signed_at || null,
      status: form.value.status
    }
  }
  const payload = {
    name: form.value.name || '',
    account: form.value.account ? Number(form.value.account) : null,
    vendor_company: form.value.vendor_company ? Number(form.value.vendor_company) : null,
    opportunity: form.value.opportunity ? Number(form.value.opportunity) : null,
    ...(form.value.region ? { region: Number(form.value.region) } : {}),
    ...(form.value.owner ? { owner: Number(form.value.owner) } : {}),
    is_framework: Boolean(form.value.is_framework),
    framework_contract: form.value.is_framework
      ? null
      : (form.value.framework_contract ? Number(form.value.framework_contract) : null),
    remark: form.value.remark || '',
    amount: form.value.amount === '' ? null : form.value.amount,
    current_output: form.value.current_output === '' ? null : form.value.current_output,
    final_settlement_amount: form.value.final_settlement_amount === '' ? null : form.value.final_settlement_amount,
    status: form.value.status,
    ...(contractApprovalEnabled.value ? {} : { approval_status: form.value.approval_status }),
    signed_at: form.value.signed_at || null,
    start_date: form.value.start_date || null,
    end_date: form.value.end_date || null
  }
  if (isEdit.value && isAdmin.value) {
    payload.contract_no = form.value.contract_no || ''
  }
  return payload
}

const save = async () => {
  if (pendingApprovalReadonly.value) {
    error.value = ''
    success.value = ''
    saving.value = true
    try {
      await api.patch(`/contracts/${route.params.id}/`, { status: form.value.status })
      success.value = '合同状态已更新'
      await loadContract()
      await fetchApprovalProgress()
    } catch (err) {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        error.value = messages || '保存失败，请检查后端服务'
      } else {
        error.value = '保存失败，请检查后端服务'
      }
    } finally {
      saving.value = false
    }
    return
  }
  if (isEdit.value && approvedReadonly.value) {
    error.value = ''
    success.value = ''
    saving.value = true
    try {
      await api.patch(`/contracts/${route.params.id}/`, {
        signed_at: form.value.signed_at || null,
        status: form.value.status,
      })
      success.value = '签署日期和合同状态已更新'
      await loadContract()
      await fetchApprovalProgress()
    } catch (err) {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        error.value = messages || '保存失败，请检查后端服务'
      } else {
        error.value = '保存失败，请检查后端服务'
      }
    } finally {
      saving.value = false
    }
    return
  }
  if (!form.value.account) {
    error.value = '请选择关联甲方'
    return
  }
  if (!form.value.region) {
    error.value = '请选择所属区域'
    return
  }
  if (!form.value.owner) {
    error.value = '请选择负责人'
    return
  }
  const amount = Number(form.value.amount)
  const isFramework = Boolean(form.value.is_framework)
  if (form.value.amount === '' || form.value.amount === null || form.value.amount === undefined) {
    error.value = '合同金额不能为空'
    return
  }
  if (!isFramework && (!Number.isFinite(amount) || amount <= 0)) {
    error.value = '合同金额必须大于0'
    return
  }
  error.value = ''
  success.value = ''
  saving.value = true
  try {
    const payload = normalizePayload()
    if (isEdit.value) {
      await api.patch(`/contracts/${route.params.id}/`, payload)
      success.value = '合同已更新'
    } else {
      const res = await api.post('/contracts/', payload)
      router.push({ path: `/contracts/${res.data.id}`, query: { saved: '1' } })
    }
  } catch (err) {
    const status = err.response?.status
    if (status === 401) {
      error.value = '登录已过期，请重新登录'
    } else {
      const detail = err.response?.data
      if (detail && typeof detail === 'object') {
        const messages = Object.entries(detail)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
          .join(' | ')
        error.value = messages || '保存失败，请检查必填项或后端服务'
      } else {
        error.value = '保存失败，请检查必填项或后端服务'
      }
    }
  } finally {
    saving.value = false
  }
}

const startRevision = async () => {
  if (!showStartRevision.value) return
  error.value = ''
  success.value = ''
  startingRevision.value = true
  try {
    await api.post(`/contracts/${route.params.id}/start_revision/`)
    success.value = '已进入修订状态，请修改后重新提交审批'
    await loadContract()
    await fetchApprovalProgress()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || '发起修订失败'
    } else {
      error.value = '发起修订失败'
    }
  } finally {
    startingRevision.value = false
  }
}

const submitApproval = async () => {
  if (!showContractSubmitApproval.value) return
  error.value = ''
  success.value = ''
  submittingApproval.value = true
  try {
    await api.post(`/contracts/${route.params.id}/submit_approval/`)
    success.value = '已提交审批'
    await loadContract()
    await fetchApprovalProgress()
  } catch (err) {
    const detail = err.response?.data
    if (detail && typeof detail === 'object') {
      error.value = detail.detail || '提交审批失败，请检查权限或流程配置'
    } else {
      error.value = '提交审批失败，请检查权限或流程配置'
    }
  } finally {
    submittingApproval.value = false
  }
}

const cancel = () => {
  router.push('/contracts')
}

const goBack = () => {
  router.back()
}

onMounted(async () => {
  await auth.ensureMeFresh(60000)
  await fetchLookups()
  await fetchOpportunities()
  await fetchRegions()
  await fetchUsers()
  await fetchFrameworkContracts()
  await loadContract()
  await fetchApprovalProgress()
  await fetchAttachments()
  await fetchPayments()
  await fetchInvoices()
  applyDefaultOwnerRegion()
  applyPaymentDefaults()
  applyInvoiceDefaults()
  if (route.query.saved) {
    success.value = '合同已保存'
  }
})

watch(accountQuery, (value) => {
  const query = value.trim()
  if (!query) {
    accountCreate.value.full_name = ''
    if (searchTimer) clearTimeout(searchTimer)
    accountOptions.value = []
    return
  }
  if (!accountCreate.value.full_name) {
    accountCreate.value.full_name = value
  }
  if (query.length < 2) {
    return
  }
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadAccounts(query)
  }, 300)
})

watch(
  () => form.value.is_framework,
  (value) => {
    if (value) {
      form.value.framework_contract = null
      if (isEdit.value) {
        fetchChildContracts()
      }
    } else {
      childContracts.value = []
    }
  }
)
</script>

<style scoped>
.contract-detail {
  font-size: 13px;
}

.invoice-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-card {
  width: min(1120px, calc(100vw - 40px));
  max-height: calc(100vh - 40px);
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.25);
  padding: 18px;
}

.invoice-modal-card {
  padding-top: 14px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.modal-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
