# 智语康伴 / vita-company

一个基于 `Vue 3 + Vite + FastAPI + SQLAlchemy + Alembic` 的健康陪伴系统仓库。当前代码重心在后端，已经覆盖从账号体系、健康档案、健康记录，到 AI 对话、长期记忆、知识库 RAG、主动关心决策和 WebSocket 实时推送的主链路。

当前仓库状态可以概括为：

- 后端能力和自动化测试已经推进到 `Phase 15` 附近，明显超出旧 `README` 中的 Phase 9 描述
- 前端提供登录、注册、聊天、档案、记录等基础页面，但并未完整覆盖后端全部高级能力
- 根目录 `docker-compose.yml` 目前只编排后端服务

## 当前能力

### 后端

- 用户注册、登录、JWT 鉴权、当前用户信息
- 健康档案 CRUD
- 健康记录 CRUD 与筛选
- 会话管理、消息历史、同步聊天
- SSE 流式聊天、取消生成、重新生成
- 会话摘要、长期记忆、上下文裁剪
- 知识库创建、文档导入、切片、检索调试
- RAG 聊天回答与引用来源返回
- 触发规则、主动消息、主动窗口、主动行为日志
- AI 主动关心决策与安全标签记录
- WebSocket 实时推送与待展示事件回放
- `Asia/Shanghai` 时区统一处理

### 前端

- 路由页面：`/`、`/chat`、`/record`、`/profile`、`/login`、`/register`
- 聊天页已接入后端流式聊天接口
- 个人资料页支持查看和修改当前用户基础信息
- 记录页目前仍偏演示态，未完全对齐后端记录模型

## 技术栈

- 前端：Vue 3、Vue Router、Vite、Axios
- 后端：FastAPI、SQLAlchemy 2.x、Pydantic 2.x、Alembic
- 定时任务：APScheduler
- 数据库：SQLite（当前默认）
- 向量检索：本地向量存储 + 远程 embedding 接口
- 大模型接入：OpenAI 兼容的 `chat/completions` / `embeddings` HTTP 接口

## 目录结构

```text
.
├─ backend/
│  ├─ alembic/                    # 数据库迁移
│  ├─ app/
│  │  ├─ api/routes/             # REST / WebSocket 路由
│  │  ├─ core/                   # 配置、异常、日志、时区、调度
│  │  ├─ db/                     # 数据库会话与 Base
│  │  ├─ models/                 # ORM 模型
│  │  ├─ schemas/                # Pydantic 模型
│  │  ├─ services/               # 业务服务（聊天、RAG、主动关心等）
│  │  └─ ws/                     # WebSocket 管理
│  ├─ scripts/                   # 启动、演示、部署辅助脚本
│  ├─ storage/                   # 文档导入与知识库存储目录
│  └─ tests/                     # 后端自动化测试
├─ frontend/
│  ├─ src/
│  │  ├─ api/                    # 前端 API 封装
│  │  ├─ router/                 # 前端路由
│  │  ├─ views/                  # 页面
│  │  └─ components/             # 组件
│  └─ vite.config.js             # 本地 /api 代理到 8000
├─ docker-compose.yml            # 后端容器编排
├─ .env.example                  # 根目录环境变量示例
└─ ALIYUN_ECS_BACKEND_DEPLOYMENT_TUTORIAL.md
```

## 快速开始

### 1. 环境要求

- Python：建议与 `backend/Dockerfile` 对齐，使用 `3.13`
- Node.js：`^20.19.0` 或 `>=22.12.0`
- npm：随 Node 安装

### 2. 配置环境变量

在仓库根目录准备 `.env`：

```powershell
Copy-Item .env.example .env
```

至少需要确认这些配置：

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_NAME`
- `EMBEDDING_API_KEY`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL_NAME`
- `BACKEND_CORS_ORIGINS`

`.env.example` 目前给的是智谱接口示例值；后端代码本身按 OpenAI 兼容协议发送请求。

### 3. 启动后端

主入口是 `backend/app/main.py`，不是仓库里那个较早期的 `backend/main.py` 示例文件。

```powershell
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

启动后可访问：

- Swagger：`http://127.0.0.1:8000/docs`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

默认访问地址：

- 前端：`http://127.0.0.1:5173`

## 测试

后端测试位于 `backend/tests/`，当前已覆盖：

- 认证与档案
- 健康记录
- 会话与消息
- SSE 流式聊天
- 会话摘要与长期记忆
- 知识库导入与检索
- RAG 调试与聊天引用
- AI 主动关心决策

执行方式：

```powershell
cd backend
pytest tests -q
```

测试环境会自动关闭调度器和 WebSocket，并使用临时 SQLite 数据库。

## 数据与运行时目录

- SQLite 数据库默认在 [healthy_system.db](backend/healthy_system.db)
- 知识库导入和存储目录在 `backend/storage/`
- 根目录 `docker-compose.yml` 会把上面两个目录挂载进后端容器

## 相关文档

- [后端功能说明（客户/评审版）](backend/BACKEND_CUSTOMER_FUNCTION_DOC.md)
- [后端部署前验收文档](backend/BACKEND_DEPLOYMENT_ACCEPTANCE.md)
- [Phase 9 历史验收文档](backend/PHASE9_ACCEPTANCE.md)
- [阿里云 ECS 后端部署教程](ALIYUN_ECS_BACKEND_DEPLOYMENT_TUTORIAL.md)
- [前端 API 规格说明](frontend/FRONTEND_API_SPEC.md)

## 当前已知事项

- `backend/Dockerfile` 依赖 `backend/requirements.txt`，但当前仓库没有提交该文件；如果要在全新环境直接构建镜像或用 `pip install -r requirements.txt`，需要先补齐依赖清单
- `frontend/README.md` 仍是 Vite 默认模板，当前以根 `README.md` 为准
- 前端尚未完整覆盖知识库、RAG 调试、主动关心配置等后端高级能力，调试这些功能建议优先使用 Swagger
