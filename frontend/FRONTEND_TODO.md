# Frontend 对接清单

更新时间：2026-04-27  
后端当前阶段：Phase 13 已完成，线上 HTTPS 已完成。  
本文目标：指导前端同学把当前 Vue demo 壳改成可联调、可演示的真实前端。

---

## 1. 先说结论

当前前端代码还是旧 demo，和真实后端差距很大。现在要做的不是“小修小补”，而是把请求层、登录态、聊天页、记录页、档案页接到真实接口。

当前必须完成的基线项：

1. 停用 `GET /api/chat?msg=...` 旧接口。
2. 停用 `RecordView.vue` 写 `localStorage` 的旧逻辑。
3. 增加统一请求层、token 存取、401 处理、业务错误处理。
4. 新增登录流程，否则现有受保护接口都不能正常接。
5. 聊天页改成真实会话 + 真实消息 + 真实 RAG 返回结构。
6. 档案页和记录页改成真实 CRUD，不再写死静态内容。

完整接口说明见：

- `frontend/FRONTEND_API_SPEC.md`

---

## 2. 当前联调入口

线上真实入口：

```text
API Base URL: https://jibao.tech/api/v1
Swagger UI:   https://jibao.tech/docs
OpenAPI JSON: https://jibao.tech/openapi.json
WebSocket:    wss://jibao.tech/api/v1/realtime/ws?token=<access_token>
```

本地开发建议：

```text
前端页面: http://localhost:5173
前端请求: /api/v1/...
Vite 代理: http://127.0.0.1:8000
```

环境变量建议：

```env
VITE_API_BASE_URL=https://jibao.tech/api/v1
```

如果本地开发走 Vite 代理，也可以让请求层支持：

```env
VITE_API_BASE_URL=/api/v1
```

注意：

1. 当前后端默认 CORS 只放行本地开发源：`http://localhost:5173` 和 `http://127.0.0.1:5173`。
2. 如果前端静态页要部署到别的域名，必须额外做同源反代，或者让后端补 CORS。
3. APK 或原生客户端只能放 API 地址，不能放模型 key、JWT secret、数据库地址。

---

## 3. 当前代码现状

现状不是“部分接好”，而是绝大多数核心页面仍是假数据：

1. `frontend/src/api/chat.js`
   还在调 `GET /api/chat?msg=...`
2. `frontend/src/views/ChatView.vue`
   仍在使用本地消息数组、`msg.text`、本地随机主动提醒、无登录态聊天
3. `frontend/src/views/RecordView.vue`
   仍在写 `localStorage`
4. `frontend/src/views/ProfileView.vue`
   完全静态
5. `frontend/src/views/HomeView.vue`
   完全静态
6. `frontend/src/router/index.js`
   还没有登录页、路由守卫、受保护页面控制

---

## 4. 第一优先级：先把基础设施补齐

### 4.1 `frontend/vite.config.js`

当前代理配置方向是对的，保留即可：

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

不要额外加 `rewrite`，否则会把 `/api/v1/...` 改坏。

### 4.2 新增 `frontend/src/api/request.js`

职责：

1. 拼接 `baseURL`
2. 注入 `Authorization: Bearer <token>`
3. 统一解包 `{ code, message, data }`
4. 统一处理 `401`、`422`、普通业务错误
5. 暴露 token 工具函数

建议导出：

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

### 4.3 新增 API 文件

建议至少补齐：

```text
frontend/src/api/request.js
frontend/src/api/auth.js
frontend/src/api/user.js
frontend/src/api/profile.js
frontend/src/api/record.js
frontend/src/api/conversation.js
frontend/src/api/message.js
frontend/src/api/chat.js
frontend/src/api/realtime.js
```

---

## 5. 第二优先级：先把登录态跑通

### 5.1 新增登录页

建议新增：

```text
frontend/src/views/LoginView.vue
```

路由补到：

```text
/login
```

### 5.2 登录接口

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
2. 立即请求 `GET /api/v1/users/me`
3. 保存当前用户状态
4. 登录成功后跳转到 `/chat` 或 `/`

### 5.3 路由守卫

除登录和注册外，其余页面都应该是受保护页面。

建议保护：

```text
/
/chat
/record
/profile
```

规则：

1. 无 token 进入受保护页时跳 `/login`
2. 遇到 `401` 时自动清 token 并跳 `/login`

---

## 6. 第三优先级：重做聊天页

### 6.1 需要改的文件

```text
frontend/src/api/chat.js
frontend/src/api/conversation.js
frontend/src/api/message.js
frontend/src/views/ChatView.vue
```

### 6.2 必须删除的旧逻辑

删除：

1. `GET /api/chat?msg=...`
2. `msg.text`
3. 本地随机主动提醒按钮
4. 未登录直接发消息
5. 没有会话也直接发消息

### 6.3 正确接法

先调：

```http
GET /api/v1/conversations
POST /api/v1/conversations
GET /api/v1/conversations/{conversation_id}/messages
POST /api/v1/chat/send
POST /api/v1/chat/send-stream
POST /api/v1/chat/messages/{assistant_message_id}/cancel
POST /api/v1/chat/messages/{assistant_message_id}/regenerate
POST /api/v1/chat/messages/{assistant_message_id}/regenerate-stream
```

### 6.4 重要产品规则

1. 默认聊天就是 RAG
2. 普通用户前端不要默认传 `knowledge_base_id`
3. 前端也不要默认手写 `mode=rag`
4. 如果明确想走普通聊天，再显式传 `mode: "plain"`

### 6.5 非流式发送最小请求

```json
{
  "conversation_id": 1,
  "content": "老年高血压日常管理要注意什么？"
}
```

### 6.6 聊天页展示要求

1. 消息字段统一使用 `content`
2. 用户发送后立即本地插入一条 user 消息
3. 后端成功返回后追加 assistant 消息
4. `reply` 作为 AI 主体内容展示
5. `citations` 作为“引用来源”折叠区展示
6. `assistant_status` 为 `streaming` 时显示生成中
7. 完成后可显示“重新生成”

### 6.7 流式聊天

SSE 事件格式：

```text
data: {"event":"start", ...}
data: {"event":"token","token":"..."}
data: {"event":"finish","reply":"完整回答","citations":[...]}
```

前端处理：

1. `start` 时创建 assistant 占位消息
2. `token` 时逐段拼接内容
3. `finish` 时写入最终 `reply`、`citations`
4. `error` 时标记失败

---

## 7. 第四优先级：重做记录页

### 7.1 需要改的文件

```text
frontend/src/api/record.js
frontend/src/views/RecordView.vue
```

### 7.2 必须删除的旧逻辑

删除：

```js
localStorage.setItem('healthRecord', ...)
```

### 7.3 当前页面建议接法

当前页面其实是三个记录入口，保存时可以拆成最多三条真实记录：

1. 服药情况
   - `record_type: "medication"`
   - `value: "已服用"` 或 `value: "未服用"`
2. 血压记录
   - `record_type: "blood_pressure"`
   - `value: "128/82"`
   - `unit: "mmHg"`
3. 身体状态
   - `record_type: "checkin"`
   - `value: "头晕"` / `value: "乏力"` / `value: "正常"`

对应接口：

```http
POST /api/v1/records
GET /api/v1/records
```

建议保存成功后：

1. 给出成功提示
2. 清空表单
3. 重新拉取当天记录列表

---

## 8. 第五优先级：重做档案页

### 8.1 需要改的文件

```text
frontend/src/api/profile.js
frontend/src/views/ProfileView.vue
```

### 8.2 当前问题

`ProfileView.vue` 现在完全是静态文案，没有真实用户数据。

### 8.3 正确接法

```http
GET /api/v1/profiles/me
POST /api/v1/profiles/me
PUT /api/v1/profiles/me
```

建议页面行为：

1. 进入页面先请求 `GET /profiles/me`
2. 如果返回 `40411`，展示创建档案表单
3. 如果已有档案，展示档案内容和编辑表单
4. 字段必须严格对齐后端 schema，不要自创字段

---

## 9. 第六优先级：首页怎么处理

### 9.1 `frontend/src/views/HomeView.vue`

首页当前完全静态。

第一版有两个可接受方案：

方案 A：先保留静态首页，只把文案改成“演示用占位首页”  
方案 B：接一点真实数据，例如：

```http
GET /api/v1/proactive/messages
GET /api/v1/records
GET /api/v1/profiles/me
```

如果时间紧，首页不是第一阻塞项，优先级低于登录 / 聊天 / 记录 / 档案。

---

## 10. 第七优先级：可后置能力

以下能力可以放到第一版之后：

1. WebSocket 实时推送
2. 主动消息完整链路
3. RAG 调试页
4. 知识库管理页
5. 会话摘要页
6. 用户长期记忆管理页

其中最值得保留接口入口的是：

```text
POST /api/v1/realtime/test-push/me
GET  /api/v1/proactive/messages
PATCH /api/v1/proactive/messages/{message_id}/displayed
WS   /api/v1/realtime/ws?token=<access_token>
```

---

## 11. 推荐开发顺序

建议按下面顺序推进：

1. `src/api/request.js`
2. `src/api/auth.js`
3. `LoginView.vue`
4. `router/index.js` 路由守卫
5. `src/api/conversation.js`
6. `src/api/message.js`
7. `src/api/chat.js`
8. `ChatView.vue`
9. `src/api/profile.js`
10. `ProfileView.vue`
11. `src/api/record.js`
12. `RecordView.vue`
13. 首页轻量调整
14. 流式输出开关
15. citations 展示优化

---

## 12. 前端验收标准

第一版至少满足：

1. `npm run build` 通过
2. 能注册或登录
3. 登录后能请求 `/users/me`
4. 无 token 不能进入受保护页面
5. 401 时自动清 token 并跳登录
6. 能创建或读取 Profile
7. 能提交真实 Record 并重新拉取列表
8. 能创建会话并拉消息
9. 默认聊天能拿到 AI 回复
10. 聊天结果里能展示 `citations`
11. 可选开启流式输出
12. 页面里不再出现 `/api/chat?msg=...`
13. 页面里不再用 `localStorage` 保存健康记录

---

## 13. 可直接转发给前端同学的一句话

> 前端现在要按真实后端 Phase 13 接口重写请求层、登录态、聊天页、记录页和档案页；线上接口统一改成 `https://jibao.tech/api/v1`，聊天默认就是 RAG，不需要前端默认传 `mode=rag` 或 `knowledge_base_id`。
