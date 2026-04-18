# Frontend 待办清单

这份清单是给前端同学的，按当前仓库实际状态整理。

## 一、先说结论

当前前端不是“已经做完”，而是“只有一个演示壳子，和后端真实接口仍然不匹配”。

当前直接需要改的核心点：

- `frontend/vite.config.js` 代理还会把 `/api` 重写掉
- `frontend/src/api/chat.js` 还在调用错误的 `GET /api/chat?msg=...`
- `frontend/src/views/ChatView.vue` 还是旧演示写法
- `frontend/src/views/RecordView.vue` 还在写 `localStorage`
- `frontend/src/views/ProfileView.vue` 还是静态文案
- 当前前端没有统一请求层、统一 token、统一错误处理

后端接口契约的基准文档：

- `backend/前后端对接规范_阶段八.md`

后续进阶版后端能力的基准文档：

- `backend/dev_order_plan2.md`

---

## 二、当前必须完成的基线任务

### P0. 开发规则

- [ ] 以后不要在页面里直接手写临时 `fetch`
- [ ] 统一通过 `frontend/src/api/*` 调后端
- [ ] 后端普通接口统一按 `{ code, message, data }` 解包
- [ ] 登录后统一带 `Authorization: Bearer <token>`
- [ ] 所有开发以 `backend/前后端对接规范_阶段八.md` 为准，不要再沿用旧 demo 逻辑

### P1. 修代理和请求层

- [ ] 修 `frontend/vite.config.js`
  - 方案 A：前端统一请求 `/api/...`
  - Vite 代理改成转发到 `/api/v1/...`
- [ ] 新增 `frontend/src/api/request.js`
  - 统一 `base path`
  - 统一 headers
  - 统一 token 注入
  - 统一错误处理
  - 统一 `payload.data` 解包
- [ ] 新增或补齐这些文件
  - `frontend/src/api/auth.js`
  - `frontend/src/api/user.js`
  - `frontend/src/api/profile.js`
  - `frontend/src/api/record.js`
  - `frontend/src/api/conversation.js`
  - `frontend/src/api/message.js`
  - `frontend/src/api/chat.js`

### P2. 补登录态

- [ ] 增加登录页或最少可用的登录表单
- [ ] 接通 `POST /api/auth/login`
- [ ] 登录成功后把 token 存到 `localStorage`
- [ ] 受保护页面无 token 时跳转登录
- [ ] 401 时统一清 token 并要求重新登录

### P3. 改聊天页 `ChatView.vue`

- [ ] 停止使用 `GET /api/chat?msg=...`
- [ ] 聊天改为先创建或选择 `conversation_id`
- [ ] 页面初始化流程改成：
  - 先拉会话列表
  - 没有会话就创建会话
  - 再拉消息列表
- [ ] 发送消息改成 `POST /api/chat/send`
- [ ] 消息字段统一改成 `content`，不要再用 `text`
- [ ] 去掉本地随机“主动提醒”假数据
- [ ] 支持：
  - 会话列表
  - 当前会话消息列表
  - 发送消息
  - 错误提示

最小依赖接口：

- `listConversations()`
- `createConversation()`
- `listMessages(conversationId)`
- `sendChatMessage(conversationId, content)`

### P4. 改档案页 `ProfileView.vue`

- [ ] 页面进入先调 `GET /api/profiles/me`
- [ ] 如果返回成功，展示档案内容
- [ ] 如果返回 `40411`，展示创建档案表单
- [ ] 首次提交走 `POST /api/profiles/me`
- [ ] 后续编辑走 `PUT /api/profiles/me`
- [ ] 表单字段严格跟后端 `Profile` 契约对齐

### P5. 改记录页 `RecordView.vue`

- [ ] 停止写 `localStorage`
- [ ] 接通 `POST /api/records`
- [ ] 接通 `GET /api/records`
- [ ] 当前页面动作映射成标准 `Record`，不要自创字段
- [ ] “已服药/未服药” 映射成 `record_type = medication`
- [ ] 血压输入映射成：
  - `record_type = blood_pressure`
  - `value = "128/82"`
  - `unit = "mmHg"`
- [ ] 身体状态映射成：
  - `record_type = checkin`
  - `value = symptom`
- [ ] 页面增加“最近记录列表”

### P6. 统一错误处理

- [ ] 至少识别这些业务码：
  - `0`
  - `40100`
  - `40101`
  - `40411`
  - `40421`
  - `40431`
  - `42200`
  - `50000`
- [ ] 表单校验错误按字段展示
- [ ] 普通业务错误给出明确提示，不要只弹浏览器默认报错

### P7. 基线验收

- [ ] `npm run build` 通过
- [ ] 能登录
- [ ] 能查看和编辑 Profile
- [ ] 能创建 Record 并拉到列表
- [ ] 能创建会话、查看消息、发送聊天
- [ ] 页面里不再有旧版 `/api/chat?msg=...`、`localStorage` 记录逻辑

---

## 三、等后端完成后再接的进阶任务

这些不是现在就能完全联通的内容，要等后端对应阶段完成。

### A. 等后端第十阶段完成后

- [ ] 接 `POST /api/v1/chat/send-stream`
- [ ] 做 token 级流式渲染
- [ ] 展示消息状态：
  - `draft`
  - `streaming`
  - `completed`
  - `failed`
  - `cancelled`
- [ ] 接停止生成按钮
- [ ] 接重新生成按钮

### B. 等后端第十一阶段完成后

- [ ] 增加会话摘要查看与刷新
- [ ] 增加用户长期记忆管理页或侧栏
- [ ] 展示 prompt version 等调试字段

### C. 等后端第十二、十三阶段完成后

- [ ] 增加知识库管理页
- [ ] 支持文档上传
- [ ] 展示索引状态
- [ ] 展示引用来源列表
- [ ] 支持引用折叠和来源定位

### D. 等后端第十五阶段完成后

- [ ] 增加主动消息列表页
- [ ] 展示风险等级
- [ ] 补主动消息调试页

### E. 等后端第十六阶段完成后

- [ ] 增加任务状态页
- [ ] 支持轮询任务进度
- [ ] 展示失败重试入口

---

## 四、建议开发顺序

按这个顺序做，不要乱跳：

1. `vite.config.js`
2. `request.js`
3. `auth.js`
4. `profile.js`
5. `record.js`
6. `conversation.js + message.js + chat.js`
7. `ChatView.vue`
8. `ProfileView.vue`
9. `RecordView.vue`
10. 进阶版页面等后端接口稳定后再接

---

## 五、直接点名当前要停用的旧写法

### `frontend/src/api/chat.js`

现在这段旧逻辑要停用：

- `GET /api/chat?msg=...`

正确方向应该是：

- `POST /api/chat/send`
- 传 JSON
- 带 `conversation_id`
- 带 `Authorization`

### `frontend/src/views/ChatView.vue`

这些旧行为要停用：

- `msg.text`
- 本地随机主动提醒
- 没有会话列表就直接发消息
- 不带 token 直接调聊天接口

### `frontend/src/views/RecordView.vue`

这些旧行为要停用：

- `localStorage.setItem('healthRecord', ...)`
- 自己拼一个后端没有的“大对象”

### `frontend/src/views/ProfileView.vue`

这些旧行为要停用：

- 纯静态展示
- 无接口读写

---

## 六、一句话版本

你现在前端要做的不是“继续摸鱼等后端全做完”，而是：

> **先把代理、请求层、登录态、聊天页、档案页、记录页全部按 Phase 8 契约接通；等后端后续完成流式、记忆、RAG、任务系统后，再补进阶页面。**
