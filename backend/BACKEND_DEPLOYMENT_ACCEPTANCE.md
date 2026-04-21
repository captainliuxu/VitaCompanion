# 后端部署前全功能验收通过文档

更新时间：2026-04-21  
验收范围：`backend/` FastAPI 后端、数据库迁移、核心业务模块、知识库与 RAG 链路。  
当前结论：后端主功能链路已达到可部署内测状态，当前稳定里程碑为 **Phase 13**，已超过原 Phase 12 知识库最小闭环。

---

## 1. 当前后端阶段结论

当前后端已经完成：

1. 基础 FastAPI 应用、统一配置、统一异常、统一响应。
2. 用户注册、登录、JWT 鉴权。
3. 当前用户信息、健康档案、健康记录。
4. 会话、消息、同步聊天、SSE 流式聊天、取消、重生成。
5. 会话摘要、长期记忆、上下文裁剪、prompt 版本记录。
6. 触发规则、主动行为日志、主动服务窗口、主动消息、WebSocket 实时推送。
7. 全局共享知识库、文档导入、PDF 抽取质量校验、切片。
8. 智谱 `embedding-3` 向量化、SQLite 本地向量存储。
9. RAG 检索调试接口、聊天默认 RAG、引用来源返回。

当前未进入正式生产级增强阶段：

1. PostgreSQL / pgvector 替代 SQLite。
2. PDF/embedding 异步任务队列。
3. 管理员权限体系。
4. 日志、监控、备份、限流、成本治理。
5. CI/CD 自动部署。

---

## 2. 本次验收命令与结果

### 2.1 应用导入

命令：

```powershell
cd backend
.\.venv\Scripts\python.exe -c "import app.main; print('import app.main ok')"
```

结果：

```text
import app.main ok
```

结论：FastAPI 应用可正常导入，启动链路无 import 错误。

### 2.2 Alembic 迁移状态

命令：

```powershell
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe heads
```

结果：

```text
d4b9e8a7c3f2 (head)
d4b9e8a7c3f2 (head)
```

结论：当前数据库迁移已到最新 head，无多 head 分叉。

### 2.3 自动化测试

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

结果：

```text
19 passed
```

结论：现有后端自动化测试全部通过。

### 2.4 API 路由覆盖

验收结果：

```text
api_routes=58
```

主要路由组：

1. `/api/v1/health`
2. `/api/v1/auth`
3. `/api/v1/users`
4. `/api/v1/profiles`
5. `/api/v1/records`
6. `/api/v1/conversations`
7. `/api/v1/conversations/{conversation_id}/messages`
8. `/api/v1/conversations/{conversation_id}/summary`
9. `/api/v1/chat`
10. `/api/v1/user-memories`
11. `/api/v1/knowledge-bases`
12. `/api/v1/rag`
13. `/api/v1/trigger-rules`
14. `/api/v1/active-logs`
15. `/api/v1/proactive`
16. `/api/v1/realtime`

结论：当前后端正式模块均已挂载到 `api_router`。

### 2.5 智谱聊天连通性

验证模型：

```text
glm-4.5-air
```

结果：

```text
测试通过
```

结论：当前 `.env` 中的聊天模型密钥可用，LLM 主调用链路可连通。

### 2.6 智谱 embedding 与 RAG 检索

当前知识库数据：

```text
knowledge_bases = 1
knowledge_documents = 3
knowledge_chunks = 3043
embedding_model = embedding-3
```

文档状态：

```text
completed = 3
```

RAG 检索验证问题：

```text
老年高血压日常管理
```

返回结果：

```text
items=3
结果包含《中国高血压防治指南（2024年修订版）》与《老年医学与老年学》相关片段。
```

结论：智谱 `embedding-3` 已完成当前知识库索引重建，RAG 检索链路可用。

默认聊天 RAG 验证：

```text
请求 /api/v1/chat/send 时不传 mode、不传 knowledge_base_id。
返回 prompt_version = phase13.rag.v1
返回 citations = 5
```

结论：前端默认聊天请求无需额外设置 RAG 参数；后端会自动选择全局 active 知识库。如果新部署环境尚无可用知识库，后端会自动退回普通聊天，避免空库时聊天不可用。

---

## 3. 模块验收明细

| 模块 | 状态 | 验收结论 |
|---|---:|---|
| FastAPI 应用启动 | 通过 | `import app.main` 成功 |
| 配置读取 | 通过 | 支持根目录 `.env` 与后端 `.env` |
| 统一响应 | 通过 | `success_response` / `error_response` 可用 |
| 统一异常 | 通过 | 业务异常、HTTP 异常、参数异常统一 JSON 返回 |
| 数据库会话 | 通过 | SQLAlchemy Session 与 FastAPI 依赖链路可用 |
| Alembic 迁移 | 通过 | 当前 head 为 `d4b9e8a7c3f2` |
| 用户注册 | 通过 | 自动化测试覆盖 |
| 用户登录 | 通过 | 自动化测试覆盖 |
| JWT 鉴权 | 通过 | 受保护接口测试覆盖 |
| 当前用户信息 | 通过 | `/users/me` 可用 |
| 健康档案 | 通过 | Profile CRUD 测试覆盖 |
| 健康记录 | 通过 | Record CRUD 与筛选测试覆盖 |
| 会话管理 | 通过 | Conversation CRUD 测试覆盖 |
| 消息管理 | 通过 | 消息列表与 debug 写入可用 |
| 同步聊天 | 通过 | `/chat/send` 测试覆盖，默认走全局共享知识库 RAG |
| SSE 流式聊天 | 通过 | `/chat/send-stream` 测试覆盖，前端可选调用 |
| 聊天取消 | 通过 | assistant message cancel 测试覆盖 |
| 聊天重生成 | 通过 | regenerate 与 regenerate-stream 测试覆盖 |
| 会话摘要 | 通过 | 生成与读取测试覆盖 |
| 长期记忆 | 通过 | UserMemory CRUD 测试覆盖 |
| 上下文工程 | 通过 | 摘要、记忆、预算裁剪测试覆盖 |
| Prompt 版本记录 | 通过 | `phase11.v1` / `phase13.rag.v1` 可记录 |
| 触发规则 | 通过 | 创建、检查、权限测试覆盖 |
| 主动行为日志 | 通过 | 列表与详情接口可用 |
| 主动服务窗口 | 通过 | 获取与更新接口可用 |
| 主动消息 | 通过 | 生成、列表、已展示标记接口可用 |
| WebSocket 实时推送 | 通过 | 路由挂载，测试推送接口存在 |
| 全局共享知识库 | 通过 | `knowledge_bases` 已去用户归属，所有用户共用 |
| 文档导入 | 通过 | `md/txt/json/pdf` 导入测试覆盖 |
| PDF 抽取质量校验 | 通过 | 低质量扫描 PDF 会被拒绝 |
| 文档切片 | 通过 | chunk_size / overlap 生效 |
| 智谱 embedding | 通过 | `embedding-3` 真实索引已生成 |
| 向量检索 | 通过 | 只检索当前 embedding 模型的 chunk |
| RAG 调试检索 | 通过 | `/rag/retrieve-debug` 可用 |
| RAG 聊天引用 | 通过 | `/chat/send` 默认使用 RAG 并返回 citations；必要时可显式传 `mode=plain` |

---

## 4. 当前数据库与知识库状态

当前数据库文件：

```text
backend/healthy_system.db
```

当前 Alembic 版本：

```text
d4b9e8a7c3f2
```

当前全局知识库：

```text
id = 1
name = 公共医学知识库
status = active
```

当前已导入 PDF：

1. `中国高血压防治指南（2024年修订版）`
2. `老年医学与老年学（原书第八版）（上册）`
3. `老年医学与老年学（原书第八版）（下册）`

当前索引：

```text
documents = 3
chunks = 3043
embedding_model = embedding-3
```

结论：当前知识库已可用于 RAG 检索与引用回答。

---

## 5. 部署前必须注意的问题

### 5.1 `.env` 不建议提交

当前 `.env` 是 Git 已跟踪文件，并且包含真实聊天 key 和 embedding key。即使仓库是私有仓库，也建议部署前处理：

```powershell
git rm --cached .env
```

推荐 `.gitignore`：

```gitignore
.env
.env.*
!.env.example
```

`.env.example` 只保留占位符，不写真实密钥。

### 5.2 `healthy_system.db` 是否提交需要明确决策

当前 `backend/healthy_system.db` 约 89MB，包含真实知识库 embedding 数据。

如果目标是快速演示：

1. 可以把该数据库作为演示种子库迁移到服务器。
2. 但不建议长期在 Git 中维护二进制数据库。

如果目标是长期部署：

1. 建议迁移到 PostgreSQL。
2. RAG 向量建议使用 pgvector、FAISS 或 Chroma。
3. 数据库备份应独立于代码仓库。

### 5.3 全局知识库目前缺少管理员权限

当前知识库是全局共享资源，但知识库创建、更新、删除、导入接口只要求登录用户，不区分管理员。

内测阶段可以接受；正式部署前建议补：

1. 管理员角色。
2. 知识库写操作权限控制。
3. 普通用户只允许读取和 RAG 检索。

### 5.4 大量文档导入仍是同步任务

当前文档导入、PDF 抽取、embedding 计算仍在同步请求中执行。

内测少量文档可用；正式部署前建议改成异步任务：

1. Celery / RQ / APScheduler worker。
2. 任务状态表。
3. 失败重试。
4. 批量导入限流与成本控制。

### 5.5 SQLite 可用于内测，不建议长期多用户生产

当前 SQLite 适合本地开发和小规模内测。多人长期使用建议升级：

1. PostgreSQL。
2. pgvector。
3. 连接池配置。
4. 定期备份。

---

## 6. 推荐部署策略

### 6.1 内测部署

可以采用：

```text
Nginx
  -> Uvicorn / FastAPI
  -> SQLite healthy_system.db
  -> 智谱 GLM + embedding-3
```

适合：

1. 个人演示。
2. 小范围内测。
3. APK 联调。

### 6.2 后续正式部署

建议升级为：

```text
Nginx
  -> FastAPI API 服务
  -> Worker 异步任务
  -> PostgreSQL
  -> pgvector / 向量库
  -> 对象存储或服务器文件存储
```

---

## 7. 部署验收清单

部署到服务器后，至少重新执行：

```bash
cd backend
python -c "import app.main; print('import app.main ok')"
alembic upgrade head
pytest tests -q
```

再验证：

1. `GET /api/v1/health`
2. `GET /api/v1/health/db`
3. 注册 / 登录
4. `GET /api/v1/users/me`
5. 创建健康记录
6. 创建会话
7. `/api/v1/chat/send`，不传 `mode` 时应默认返回 RAG citations
8. `/api/v1/chat/send-stream`，流式输出由前端作为可选调用
9. `/api/v1/rag/retrieve-debug`
10. `/api/v1/chat/send` with `mode=plain`，用于验证普通聊天逃生路径

---

## 8. 最终验收结论

当前后端功能主链路验收通过，具备部署内测条件。

可部署内容：

1. 用户体系。
2. 健康数据管理。
3. 聊天与流式聊天。
4. 上下文与长期记忆。
5. 主动服务基础能力。
6. 全局共享知识库。
7. 智谱 embedding 与默认 RAG 引用回答。

部署前强烈建议先处理：

1. `.env` 从 Git 跟踪中移除。
2. 明确 `healthy_system.db` 是否作为演示库迁移，不建议长期提交到 Git。
3. 若对外开放，补知识库管理员权限。
