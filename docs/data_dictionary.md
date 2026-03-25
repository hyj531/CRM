# 数据字典

**模板来源（商机）**：2026年商机盘点表（华东）1.xlsx / 工作表：商机台账

## 商机（Opportunity）字段清单（对齐模板列）

| 模板列名 | 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| 创建时间 | created_at | datetime | 系统 | 系统自动生成 |
| 需求产品 | product_need | enum（可配置） | 否 | 下拉字段，默认值见“枚举与默认值” |
| 用户群体 | user_group | enum（可配置） | 否 | 下拉字段，默认值见“枚举与默认值” |
| 客户名称 | account_id | FK(Account) | 是 | 关联客户 |
| 项目名称（商机名称） | opportunity_name | string | 是 | 商机名称 |
| 客户联系人 | contact_id | FK(Contact) | 否 | 关联联系人 |
| 商机阶段 | stage | enum | 是 | 需求引导/方案阶段/商务谈判/合同审批/成交关闭 |
| 预计成交金额 | expected_amount | decimal | 否 | 预计金额 |
| 预计成交时间 | expected_close_date | date | 否 | 预计成交日期 |
| 实际成交金额 | actual_amount | decimal | 否 | 实际金额 |
| 商机成交时间 | actual_close_date | date | 否 | 实际成交日期 |
| 商机成交是否满足经营指标25% | kpi_25_met | bool | 否 | 是否>=25% |
| 商机主责人 | owner_id | FK(User) | 是 | 关联负责人 |
| 商机分类 | opportunity_category | enum（可配置） | 否 | 下拉字段，默认值见“枚举与默认值” |
| 客户级别 | customer_level | enum（可配置） | 否 | 下拉字段，默认值见“枚举与默认值” |
| 线索来源 | lead_source | enum（可配置） | 否 | 下拉字段，默认值见“枚举与默认值” |
| 商机停留天数 | stage_stay_days | int | 系统 | 自动计算=当前日期-阶段进入时间 |
| 商机挂起时间 | suspended_at | date | 否 | 手工填写，商机暂时不跟进 |
| 企业性质 | enterprise_nature | enum（可配置） | 否 | 解决方案服务商/科技公司/硬件厂商/行业头部企业 |
| 是否有居间 | has_intermediary | bool | 否 | 是/否 |
| 所属区域 | region_id | FK(Region) | 是 | 关联区域 |
| 跟进记录 | latest_followup_note | text | 否 | 最新跟进记录内容 |
| 跟进记录时间 | latest_followup_at | datetime | 否 | 最新跟进记录时间（模板备注新增） |

### 商机业务规则与计算字段

- **成交概率**：`win_probability`（int 0–100，可调），默认随阶段映射：
  - 需求引导：10
  - 方案阶段：30
  - 商务谈判：70
  - 合同审批：90
  - 成交关闭：100
- **阶段进入时间**：`stage_entered_at`（datetime，系统维护）
- **停留天数**：`stage_stay_days`（int）= 当前日期 - `stage_entered_at`

> 注：`win_probability`、`stage_entered_at`、`stage_stay_days` 为系统维护字段，不在模板列中单独呈现，但用于支撑模板“商机阶段/停留天数”的业务含义。

### 商机枚举与默认值（可配置）

以下字段为“可配置枚举”，默认值可按模板与业务实际逐步完善：

- `product_need`（需求产品）
- `user_group`（用户群体）
- `opportunity_category`（商机分类）
- `customer_level`（客户级别）
- `lead_source`（线索来源）
- `enterprise_nature`（企业性质）
  - 默认：解决方案服务商 / 科技公司 / 硬件厂商 / 行业头部企业
- `stage`（商机阶段）
  - 默认：需求引导 / 方案阶段 / 商务谈判 / 合同审批 / 成交关闭

### 商机跟进记录说明

- `latest_followup_note`：描述当前阶段关键推进或解决的关键问题。
- `latest_followup_at`：最新跟进记录时间（模板备注要求新增列）。

---

## 线索（Lead）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| name | string | 是 | 线索名称 |
| source | string | 否 | 线索来源 |
| status | string | 是 | 状态（如 new/qualified） |
| description | text | 否 | 线索描述 |
| estimated_value | decimal | 否 | 预估价值 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 客户（Account）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| name | string | 是 | 客户名称 |
| customer_level | enum | 否 | 客户级别（可配置） |
| industry | string | 否 | 行业 |
| enterprise_nature | enum | 否 | 企业性质（可配置） |
| scale | string | 否 | 企业规模 |
| credit_code | string | 否 | 统一社会信用代码 |
| address | string | 否 | 地址 |
| phone | string | 否 | 电话 |
| website | url | 否 | 官网 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| status | enum | 否 | active/archived |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 联系人（Contact）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| account_id | FK(Account) | 是 | 关联客户 |
| name | string | 是 | 姓名 |
| email | email | 否 | 邮箱 |
| phone | string | 否 | 电话 |
| title | string | 否 | 职位 |
| is_key_person | bool | 否 | 是否关键人 |
| preference | string | 否 | 偏好/标签 |
| remark | text | 否 | 备注 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 报价（Quote）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| account_id | FK(Account) | 是 | 关联客户 |
| opportunity_id | FK(Opportunity) | 否 | 关联商机 |
| amount | decimal | 是 | 报价金额 |
| status | enum | 是 | draft/submitted/approved/rejected |
| issued_at | date | 否 | 报价日期 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 合同（Contract）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| contract_no | string | 否 | 合同编号 |
| name | string | 否 | 合同名称 |
| account_id | FK(Account) | 是 | 关联客户 |
| opportunity_id | FK(Opportunity) | 否 | 关联商机 |
| amount | decimal | 是 | 合同金额 |
| final_settlement_amount | decimal | 否 | 最终结算金额（新增） |
| status | enum | 是 | draft/signed/active/closed |
| approval_status | enum | 否 | pending/approved/rejected |
| signed_at | date | 否 | 签署日期 |
| start_date | date | 否 | 生效日期 |
| end_date | date | 否 | 到期日期 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 开票（Invoice）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| invoice_no | string | 否 | 开票编号 |
| contract_id | FK(Contract) | 是 | 关联合同 |
| account_id | FK(Account) | 否 | 关联客户 |
| amount | decimal | 是 | 开票金额 |
| tax_rate | decimal | 否 | 税率 |
| invoice_type | enum | 否 | 增值税专票/普票 |
| status | enum | 是 | draft/issued/paid/void |
| approval_status | enum | 否 | pending/approved/rejected |
| issued_at | date | 否 | 开票日期 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 回款（Payment）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| contract_id | FK(Contract) | 是 | 关联合同 |
| invoice_id | FK(Invoice) | 否 | 关联开票 |
| period_no | int | 否 | 回款期次 |
| receivable_amount | decimal | 否 | 应收金额 |
| amount | decimal | 是 | 回款金额 |
| paid_at | date | 否 | 回款日期 |
| status | enum | 否 | planned/partial/paid |
| reference | string | 否 | 回款编号/备注 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 活动（Activity）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| activity_type | enum | 是 | call/meeting/email/visit |
| subject | string | 是 | 标题 |
| description | text | 否 | 备注 |
| lead_id | FK(Lead) | 否 | 关联线索 |
| opportunity_id | FK(Opportunity) | 否 | 关联商机 |
| account_id | FK(Account) | 否 | 关联客户 |
| due_at | datetime | 否 | 预计时间 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 任务（Task）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| subject | string | 是 | 标题 |
| status | enum | 是 | open/done/canceled |
| due_at | datetime | 否 | 截止时间 |
| lead_id | FK(Lead) | 否 | 关联线索 |
| opportunity_id | FK(Opportunity) | 否 | 关联商机 |
| account_id | FK(Account) | 否 | 关联客户 |
| contract_id | FK(Contract) | 否 | 关联合同 |
| owner_id | FK(User) | 是 | 负责人 |
| region_id | FK(Region) | 是 | 所属区域 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

## 组织与权限

### 区域（Region）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| name | string | 是 | 区域名称 |
| code | string | 是 | 区域编码 |
| dingtalk_dept_id | string | 否 | 钉钉部门ID |
| parent_id | FK(Region) | 否 | 上级区域 |
| is_active | bool | 是 | 是否启用 |
| created_at | datetime | 系统 | 创建时间 |

### 角色（Role）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| name | string | 是 | 角色名称 |
| code | string | 是 | 角色编码 |
| data_scope | enum | 是 | self/region/region_and_children/all |

### 用户（User）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| username | string | 是 | 用户名 |
| email | email | 否 | 邮箱 |
| phone | string | 否 | 手机 |
| region_id | FK(Region) | 否 | 归属区域 |
| role_id | FK(Role) | 否 | 角色 |
| dingtalk_user_id | string | 否 | 钉钉用户ID |
| dingtalk_union_id | string | 否 | 钉钉unionId |
| is_active | bool | 是 | 是否启用 |
| is_staff | bool | 是 | 是否后台管理员 |

## 审批与流程

### 审批流程（ApprovalFlow）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| name | string | 是 | 流程名称 |
| target_type | enum | 是 | quote/contract/invoice |
| region_id | FK(Region) | 否 | 适用区域，空=全局 |
| is_active | bool | 是 | 是否启用 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

### 审批节点（ApprovalStep）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| flow_id | FK(ApprovalFlow) | 是 | 所属流程 |
| order | int | 是 | 顺序 |
| name | string | 是 | 节点名称 |
| approver_role_id | FK(Role) | 否 | 审批角色 |
| approver_user_id | FK(User) | 否 | 审批人 |

### 审批实例（ApprovalInstance）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| target_type | enum | 是 | quote/contract/invoice |
| object_id | int | 是 | 目标对象ID |
| region_id | FK(Region) | 是 | 归属区域 |
| status | enum | 是 | pending/approved/rejected |
| started_by | FK(User) | 是 | 发起人 |
| current_step | int | 是 | 当前节点序号 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |

### 审批任务（ApprovalTask）

| 字段标识 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | int | 系统 | 主键 |
| instance_id | FK(ApprovalInstance) | 是 | 所属实例 |
| step_id | FK(ApprovalStep) | 是 | 对应节点 |
| assignee_id | FK(User) | 是 | 审批人 |
| status | enum | 是 | pending/approved/rejected/blocked |
| decided_at | datetime | 否 | 审批时间 |
| comment | text | 否 | 审批意见 |
| created_at | datetime | 系统 | 创建时间 |
| updated_at | datetime | 系统 | 更新时间 |
