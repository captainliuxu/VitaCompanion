# Frontend API Spec

更新时间：2026-04-27  
适用状态：当前线上后端已经切到 `HTTPS + 正式域名`

---

## 1. 当前联调入口

前端现在统一按下面这组地址联调：

```text
API Base URL: https://jibao.tech/api/v1
Swagger UI:   https://jibao.tech/docs
OpenAPI JSON: https://jibao.tech/openapi.json
WebSocket:    wss://jibao.tech/api/v1/realtime/ws?token=<access_token>
```

说明：

1. 字段级 schema 以 `Swagger UI` 和 `OpenAPI JSON` 为权威源。
2. 浏览器环境、移动端环境、前端构建产物都应优先使用 `https://jibao.tech/api/v1`。
3. 如果只是本地开发，前端页面建议跑在 `http://localhost:5173`，接口走 `/api/v1` + Vite 代理。

---

## 2. 开发环境与 CORS 约束

### 2.1 本地开发建议

本地开发推荐：

```text
前端页面: http://localhost:5173
API 请求: /api/v1/...
代理目标: http://127.0.0.1:8000
```

对应 Vite 代理：

```js
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

### 2.2 当前 CORS 约束

后端当前默认放行的跨域来源是：

```text
http://localhost:5173
http://127.0.0.1:5173
```

所以如果前端静态页要部署到其他域名或 IP：

1. 要么做同源反向代理
2. 要么让后端补 CORS 白名单

---

## 3. 通用接口规则

### 3.1 统一前缀

除 `Swagger` 和 `openapi.json` 之外，所有业务接口都以这个前缀开头：

```text
https://jibao.tech/api/v1
```

前端代码里尽量只维护相对路径，例如：

```text
/auth/login
/chat/send
/profiles/me
```

### 3.2 鉴权规则

公开接口只有：

```text
GET  /health
GET  /health/db
POST /auth/register
POST /auth/login
```

其余接口都要带：

```http
Authorization: Bearer <access_token>
```

### 3.3 统一 JSON 响应壳

除登录、SSE、WebSocket 外，其余普通 JSON 接口统一返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

前端请求层规则：

1. `code === 0` 时返回 `data`
2. `code !== 0` 时按业务错误处理
3. `401`、`40100`、`40101` 时清 token 并跳登录
4. `42200` 时展示字段校验错误

### 3.4 三个特例

特例 1：登录接口不是统一响应壳

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded
```

返回：

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

特例 2：流式聊天接口返回 `text/event-stream`

```text
POST /chat/send-stream
POST /chat/messages/{assistant_message_id}/regenerate-stream
```

特例 3：实时通道走 WebSocket

```text
wss://jibao.tech/api/v1/realtime/ws?token=<access_token>
```

---

## 4. 前端最关键的几个请求示例

### 4.1 注册

```http
POST /auth/register
Content-Type: application/json
```

```json
{
  "username": "demo",
  "email": "demo@example.com",
  "phone": "13900000000",
  "password": "Pass123456",
  "confirm_password": "Pass123456"
}
```

### 4.2 登录

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded
```

```text
username=demo&password=Pass123456
```

### 4.3 读取当前用户

```http
GET /users/me
Authorization: Bearer <access_token>
```

### 4.4 创建会话

```http
POST /conversations
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "title": "复试演示会话"
}
```

### 4.5 非流式聊天

```http
POST /chat/send
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "conversation_id": 1,
  "content": "老年高血压日常管理要注意什么？"
}
```

默认聊天就是 RAG，前端不要默认传：

```json
{
  "mode": "rag",
  "knowledge_base_id": 1
}
```

如果明确要关闭知识库回答，再显式传：

```json
{
  "conversation_id": 1,
  "content": "我们随便聊聊。",
  "mode": "plain"
}
```

### 4.6 流式聊天

```http
POST /chat/send-stream
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: text/event-stream
```

SSE 事件格式示例：

```text
data: {"event":"start", ...}
data: {"event":"token","token":"..."}
data: {"event":"finish","reply":"完整回答","citations":[...]}
```

### 4.7 读取当前用户档案

```http
GET /profiles/me
Authorization: Bearer <access_token>
```

### 4.8 新增健康记录

```http
POST /records
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "record_type": "blood_pressure",
  "value": "128/82",
  "unit": "mmHg",
  "note": "早晨测量"
}
```

---

## 5. 当前普通前端真正要用到的接口

下面的路径均是相对于 `https://jibao.tech/api/v1` 的相对路径。

### 5.1 Health

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/health` | No | 服务健康检查 |
| GET | `/health/db` | No | 数据库连通性检查 |

### 5.2 Auth

| Method | Path | Auth | 说明 |
|---|---|---|---|
| POST | `/auth/register` | No | 注册 |
| POST | `/auth/login` | No | 登录，`form-urlencoded` |

### 5.3 Users

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/users/me` | Yes | 读取当前用户 |
| PUT | `/users/me` | Yes | 更新当前用户 |

### 5.4 Profiles

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/profiles/me` | Yes | 读取档案 |
| POST | `/profiles/me` | Yes | 创建档案 |
| PUT | `/profiles/me` | Yes | 更新档案 |

### 5.5 Records

| Method | Path | Auth | 说明 |
|---|---|---|---|
| POST | `/records` | Yes | 创建健康记录 |
| GET | `/records` | Yes | 记录列表 |
| GET | `/records/{record_id}` | Yes | 记录详情 |
| PUT | `/records/{record_id}` | Yes | 更新记录 |
| DELETE | `/records/{record_id}` | Yes | 删除记录 |

### 5.6 Conversations

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/conversations` | Yes | 会话列表 |
| POST | `/conversations` | Yes | 创建会话 |
| GET | `/conversations/{conversation_id}` | Yes | 会话详情 |
| PUT | `/conversations/{conversation_id}/title` | Yes | 修改标题 |
| DELETE | `/conversations/{conversation_id}` | Yes | 删除会话 |

### 5.7 Messages

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/conversations/{conversation_id}/messages` | Yes | 消息列表 |

### 5.8 Chat

| Method | Path | Auth | 说明 |
|---|---|---|---|
| POST | `/chat/send` | Yes | 非流式聊天，默认走 RAG |
| POST | `/chat/send-stream` | Yes | 流式聊天，SSE |
| POST | `/chat/messages/{assistant_message_id}/cancel` | Yes | 取消生成 |
| POST | `/chat/messages/{assistant_message_id}/regenerate` | Yes | 非流式重生成 |
| POST | `/chat/messages/{assistant_message_id}/regenerate-stream` | Yes | 流式重生成，SSE |

### 5.9 RAG Debug

| Method | Path | Auth | 说明 |
|---|---|---|---|
| POST | `/rag/retrieve-debug` | Yes | 检索调试，可后置 |

### 5.10 Proactive / Realtime

| Method | Path | Auth | 说明 |
|---|---|---|---|
| GET | `/proactive/messages` | Yes | 主动消息列表 |
| PATCH | `/proactive/messages/{message_id}/displayed` | Yes | 标记消息已展示 |
| GET | `/proactive/window` | Yes | 主动服务时间窗 |
| PUT | `/proactive/window` | Yes | 更新主动服务时间窗 |
| POST | `/realtime/test-push/me` | Yes | 给当前用户发测试推送 |
| WS | `/realtime/ws?token=<access_token>` | Yes | WebSocket 实时通道 |

---

## 6. 当前必须避免的旧接口和旧字段

不要再调用旧 demo 接口：

```text
GET /api/chat?msg=...
```

不要再在消息列表里使用旧字段：

```text
msg.text
```

当前真实聊天消息和消息列表统一使用：

```text
content
```

---

## 7. 可直接转发给前端同学的一句话

> 现在统一按 `https://jibao.tech/api/v1` 联调，完整 schema 看 `https://jibao.tech/docs` 和 `https://jibao.tech/openapi.json`；除注册和登录外其余接口都带 `Bearer token`，聊天默认就是 RAG，不要再调用旧的 `GET /api/chat?msg=...`。
