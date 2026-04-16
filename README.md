# 商机管理系统（Django + DRF）

## 运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 依赖说明

- 本地开发（sqlite）：`requirements.dev.txt`
- 生产部署（Docker/Postgres）：`requirements.txt`

## 环境变量

- `DATABASE_URL`：PostgreSQL 连接串，如 `postgres://user:pass@host:5432/db`
- `DJANGO_SECRET_KEY`：生产环境必须设置
- `DJANGO_DEBUG`：`1`/`0`
- `DJANGO_ALLOWED_HOSTS`：逗号分隔

### 钉钉（可选）

- `DINGTALK_WEBHOOK`：待办通知 webhook
- `DINGTALK_CLIENT_ID` / `DINGTALK_CLIENT_SECRET`
- `DINGTALK_TOKEN_URL` / `DINGTALK_USERINFO_URL`：SSO 交换地址
- `DINGTALK_ACCESS_TOKEN`：组织同步用 access token
- `DINGTALK_DEPT_LIST_URL` / `DINGTALK_USER_LIST_URL`
- `DINGTALK_SYNC_FILE`：本地 JSON 同步文件路径（用于离线导入）
- `DINGTALK_TODO_ENABLED`：审批待办开关（`1/0`）
- `DINGTALK_TODO_RETRY_ENABLED`：待办失败后是否重试（默认 `0`=不重试，直接入死信）
- `DINGTALK_TODO_CREATE_URL` / `DINGTALK_TODO_COMPLETE_URL`
- `DINGTALK_TODO_OPERATOR_UNION_ID`
- `DINGTALK_OWN_OA_PROCESS_CODE` / `DINGTALK_OWN_OA_CREATE_URL`
- `DINGTALK_OWN_OA_FORM_LABEL`
- `FRONTEND_BASE_URL`：审批详情页面基地址

Todo v1.0（企业内部应用）token 获取说明：

- OpenAPI token 使用 `POST https://api.dingtalk.com/v1.0/oauth2/accessToken`
- 请求体为 `{"appKey":"<DINGTALK_CLIENT_ID>","appSecret":"<DINGTALK_CLIENT_SECRET>"}`
- 该 Todo token 获取路径不依赖 `DINGTALK_CORP_ID`（`CORP_ID` 可保留给其他能力）
- 钉钉待办点击免登录（authCode）依赖：`DINGTALK_CLIENT_ID`、`DINGTALK_CLIENT_SECRET`、`DINGTALK_CORP_ID`、`DINGTALK_TOKEN_URL`、`DINGTALK_USERINFO_URL`
- 仅带 `sso=1` 的待办链接触发自动免登录；若不在钉钉容器内会自动回退账号密码登录

## 钉钉组织同步

```bash
python manage.py sync_dingtalk
```

## 审批待办队列处理

```bash
python manage.py process_approval_todo_outbox --batch-size 100 --max-rounds 3
```

### 离线 JSON 示例

```json
{
  "departments": [
    {"id": 1, "name": "总部", "parent_id": null}
  ],
  "users": [
    {"userid": "u001", "name": "张三", "dept_id": 1, "email": "zs@example.com"}
  ]
}
```

## 需求与设计文档

- PRD：`docs/prd.md`
- 业务流程：`docs/business_process.md`
- 数据字典：`docs/data_dictionary.md`

## 字典初始化

```bash
python manage.py seed_lookups
```

## 前端（Vue SPA）

开发：

```bash
cd frontend
npm install
npm run dev
```

生产构建（输出到 `core/static/spa`）：

```bash
cd frontend
npm run build
```

构建后访问：`/app/`
