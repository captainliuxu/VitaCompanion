# Frontend 对接清单

更新时间：2026-04-21  
后端当前阶段：Phase 13 已完成，聊天默认走全局共享知识库 RAG。  
本文目标：指导前端把当前 demo 壳改成可部署内测版。

---

## 1. 先说结论

当前前端仍是旧 demo 形态，和真实后端接口不匹配。必须先完成下面这些基线改造：

1. 停用 `GET /api/chat?msg=...`。
2. 停用记录页写 `localStorage` 的旧逻辑。
3. 增加统一请求层、登录态、token 注入、错误处理。
4. 聊天默认调用后端 RAG，不需要前端额外传 `mode=rag` 或 `knowledge_base_id`。
5. 流式输出由前端做成可选项：用户打开流式时调用 `/chat/send-stream`，否则调用 `/chat/send`。
6. 知识库是全局共享资源，前端普通用户侧不需要选择知识库。

后端已验收文档：

- `backend/BACKEND_DEPLOYMENT_ACCEPTANCE.md`

---

## 2. API 基础约定

### 2.1 基础路径

开发环境建议前端统一请求：

```text
/api/v1
```

生产环境建议用环境变量：

```env
VITE_API_BASE_URL=https://你的域名/api/v1
```

APK 里只能放 API 地址，不能放智谱 key、JWT secret、数据库地址。

### 2.2 统一响应结构

普通 JSON 接口返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

前端请求层需要：

1. `code === 0` 时返回 `data`
2. `code !== 0` 时抛业务错误
3. `401` 或业务码 `40100/40101` 时清 token 并跳转登录
4. `42200` 展示表单字段错误

### 2.3 鉴权

登录以外的业务接口都要带：

```http
Authorization: Bearer <access_token>
```

token 建议先存 `localStorage`，后续再优化。

---

## 3. 必须先改的文件

### 3.1 `frontend/vite.config.js`

确认开发代理不要把 `/api` 重写错。

推荐方向：

```js
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true
    }
  }
}
```

这样前端请求 `/api/v1/...` 会直接转发到后端。

### 3.2 新增 `frontend/src/api/request.js`

职责：

1. 拼接 `baseURL`
2. 注入 token
3. 统一解包 `{ code, message, data }`
4. 统一处理错误
5. 支持普通 JSON 请求

建议暴露：

```js
request(path, options)
get(path)
post(path, body)
put(path, body)
del(path)
getToken()
setToken(token)
clearToken()
```

### 3.3 新增或改造 API 文件

需要补齐：

```text
frontend/src/api/auth.js
frontend/src/api/user.js
frontend/src/api/profile.js
frontend/src/api/record.js
frontend/src/api/conversation.js
frontend/src/api/message.js
frontend/src/api/chat.js
frontend/src/api/rag.js
```

---

## 4. 登录模块

### 4.1 登录接口

接口：

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded
```

请求体：

```text
username=<username>&password=<password>
```

返回：

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

前端动作：

1. 保存 `access_token`
2. 跳转首页或聊天页
3. 后续请求统一带 `Authorization`

### 4.2 注册接口

接口：

```http
POST /api/v1/auth/register
```

JSON：

```json
{
  "username": "demo",
  "email": "demo@example.com",
  "phone": "13900000000",
  "password": "Pass123456",
  "confirm_password": "Pass123456"
}
```

---

## 5. 聊天模块：默认 RAG

### 5.1 重要产品规则

聊天默认就是 RAG。

前端默认不要传：

```json
{
  "mode": "rag",
  "knowledge_base_id": 1
}
```

后端会自动选择全局 active 知识库。

如果新部署环境没有知识库，后端会自动退回普通聊天。

### 5.2 非流式聊天

接口：

```http
POST /api/v1/chat/send
```

最小 JSON：

```json
{
  "conversation_id": 1,
  "content": "老年高血压日常管理要注意什么？"
}
```

返回 `data`：

```json
{
  "conversation_id": 1,
  "user_message_id": 10,
  "assistant_message_id": 11,
  "reply": "回答正文",
  "assistant_status": "completed",
  "prompt_version": "phase13.rag.v1",
  "replied_at": "2026-04-21T...",
  "citations": [
    {
      "source_index": 1,
      "chunk_id": 123,
      "document_id": 1,
      "knowledge_base_id": 1,
      "title": "中国高血压防治指南...",
      "file_name": "xxx.pdf",
      "content_preview": "引用片段预览",
      "score": 1.23,
      "chunk_index": 5
    }
  ]
}
```

前端展示要求：

1. 用户消息立即追加到列表。
2. 后端返回后追加 assistant 消息。
3. `reply` 展示为 AI 内容。
4. `citations` 展示为“引用来源”折叠区。
5. `prompt_version` 可放调试信息，不必给普通用户展示。

### 5.3 普通聊天逃生路径

如果某些场景明确不想用知识库，可以传：

```json
{
  "conversation_id": 1,
  "content": "我们随便聊聊。",
  "mode": "plain"
}
```

此时 `citations` 应为空。

### 5.4 流式聊天，可选

接口：

```http
POST /api/v1/chat/send-stream
```

请求体和 `/chat/send` 一样。默认也走 RAG。

前端如果开启“流式输出”选项，就调用这个接口；否则调用 `/chat/send`。

SSE event 数据格式：

```text
data: {"event":"start", ...}

data: {"event":"token", "token":"..."}

data: {"event":"finish", "reply":"完整回答", "citations":[...]}
```

前端处理：

1. `start`：创建 assistant 占位消息，状态设为 `streaming`
2. `token`：把 token 追加到 assistant 内容
3. `finish`：状态设为 `completed`，保存最终 `reply` 和 `citations`
4. `error`：状态设为 `failed`，展示错误提示

### 5.5 停止生成与重生成

取消：

```http
POST /api/v1/chat/messages/{assistant_message_id}/cancel
```

重生成：

```http
POST /api/v1/chat/messages/{assistant_message_id}/regenerate
```

流式重生成：

```http
POST /api/v1/chat/messages/{assistant_message_id}/regenerate-stream
```

前端按钮建议：

1. assistant 正在 streaming 时显示“停止”
2. assistant completed/failed 时显示“重新生成”

---

## 6. 会话和消息模块

### 6.1 会话列表

```http
GET /api/v1/conversations
```

### 6.2 创建会话

```http
POST /api/v1/conversations
```

JSON：

```json
{
  "title": "新会话"
}
```

### 6.3 消息列表

```http
GET /api/v1/conversations/{conversation_id}/messages
```

消息字段使用：

```json
{
  "id": 1,
  "conversation_id": 1,
  "role": "user",
  "content": "消息内容",
  "status": "completed",
  "reply_to_message_id": null,
  "prompt_version": null,
  "created_at": "...",
  "updated_at": "..."
}
```

前端不要再使用旧字段 `text`，统一使用 `content`。

---

## 7. 健康档案模块

### 7.1 读取档案

```http
GET /api/v1/profiles/me
```

如果返回 `40411`，说明还没有档案，前端展示创建表单。

### 7.2 创建档案

```http
POST /api/v1/profiles/me
```

### 7.3 更新档案

```http
PUT /api/v1/profiles/me
```

前端字段必须和后端 schema 对齐，不要自创字段。

---

## 8. 健康记录模块

### 8.1 创建记录

```http
POST /api/v1/records
```

示例：血压

```json
{
  "record_type": "blood_pressure",
  "value": "128/82",
  "unit": "mmHg",
  "note": "早晨测量"
}
```

示例：服药

```json
{
  "record_type": "medication",
  "value": "已服药",
  "unit": null,
  "note": "降压药"
}
```

示例：身体状态

```json
{
  "record_type": "checkin",
  "value": "今天有点头晕",
  "unit": null,
  "note": null
}
```

### 8.2 记录列表

```http
GET /api/v1/records
```

前端当前 `RecordView.vue` 里的 `localStorage` 逻辑必须删除。

---

## 9. 知识库和 RAG 调试页

普通用户端可以不做知识库管理页。

如果要做调试页，优先接：

```http
POST /api/v1/rag/retrieve-debug
```

JSON：

```json
{
  "knowledge_base_id": 1,
  "query": "老年高血压日常管理",
  "top_k": 5
}
```

说明：

1. 当前知识库是全局共享的。
2. 普通聊天不需要传 `knowledge_base_id`。
3. 管理端后续再做文档导入、索引状态、失败重试。

---

## 10. 主动消息和实时能力

可以后置，不阻塞第一版部署。

已有接口：

```text
GET /api/v1/proactive/messages
PATCH /api/v1/proactive/messages/{message_id}/displayed
GET /api/v1/proactive/window
PUT /api/v1/proactive/window
POST /api/v1/realtime/test-push/me
WebSocket /api/v1/realtime/ws
```

第一版前端可以先不做复杂 WebSocket，只保留页面入口或后续迭代。

---

## 11. 页面改造顺序

建议按下面顺序做：

1. `vite.config.js`
2. `src/api/request.js`
3. `src/api/auth.js`
4. 登录页或登录弹窗
5. `src/api/conversation.js`
6. `src/api/message.js`
7. `src/api/chat.js`
8. `ChatView.vue`
9. `src/api/profile.js`
10. `ProfileView.vue`
11. `src/api/record.js`
12. `RecordView.vue`
13. 引用来源组件
14. 可选流式输出开关
15. 主动消息 / WebSocket 后续再接

---

## 12. 当前必须删除的旧逻辑

### `frontend/src/api/chat.js`

删除旧接口：

```js
GET /api/chat?msg=...
```

改成：

```js
POST /api/v1/chat/send
POST /api/v1/chat/send-stream
```

### `frontend/src/views/ChatView.vue`

删除：

1. `msg.text`
2. 本地随机主动提醒
3. 无会话直接发消息
4. 不带 token 调聊天接口
5. 手动选择 RAG 的强依赖

改成：

1. 先创建或选择会话
2. 消息字段用 `content`
3. 默认发送走 RAG
4. 引用来源来自 `citations`
5. 流式输出由用户选项控制

### `frontend/src/views/RecordView.vue`

删除：

```js
localStorage.setItem('healthRecord', ...)
```

改成调用：

```http
POST /api/v1/records
GET /api/v1/records
```

### `frontend/src/views/ProfileView.vue`

删除纯静态展示，改成：

```http
GET /api/v1/profiles/me
POST /api/v1/profiles/me
PUT /api/v1/profiles/me
```

---

## 13. 前端验收标准

第一版内测前端至少满足：

1. `npm run build` 通过。
2. 能注册或登录。
3. 登录后能拿到 `/users/me`。
4. 能创建或读取 Profile。
5. 能创建 Record 并看到列表。
6. 能创建会话并拉取消息。
7. 默认聊天能拿到 AI 回复。
8. 默认聊天响应里能展示 citations。
9. 可选开启流式输出。
10. 无 token 时不允许进入受保护页面。
11. 401 时自动清 token 并回登录。
12. 页面里不再出现 `/api/chat?msg=...`。
13. 页面里不再用 `localStorage` 保存健康记录。

---

## 14. 一句话版本

前端现在要做的是：

> **按真实后端 Phase 13 接口重写请求层和核心页面；聊天默认就是全局共享知识库 RAG，流式输出只是前端可选的发送方式。**
