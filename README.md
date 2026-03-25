# 商机管理系统（Django + DRF）

## 运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

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

## 钉钉组织同步

```bash
python manage.py sync_dingtalk
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
