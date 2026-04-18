# 第十阶段验收文档（后端 dev_order_plan2）

本文用于验收 `dev_order_plan2` 第十阶段是否完成：

- 聊天流式输出（SSE）
- 消息状态机（draft/streaming/completed/failed/cancelled）
- 取消与重生成能力
- 数据库迁移落库
- 自动化测试覆盖

---

## 1. 验收前准备

在项目根目录打开 PowerShell：

```powershell
cd D:\vita-company\backend
.\.venv\Scripts\python -V
.\.venv\Scripts\alembic upgrade head
```

通过标准：

- 迁移执行成功，无报错
- 当前数据库版本升级到最新（包含第十阶段 `messages` 新字段）

---

## 2. 自动化验收（优先执行）

```powershell
cd D:\vita-company\backend
.\.venv\Scripts\python -m pytest tests -q
```

通过标准：

- 所有测试通过（当前应为 `7 passed`）
- 至少覆盖以下场景：
  - `stream` 成功
  - `stream` 失败
  - `cancel`
  - `regenerate`
  - 同步接口可用

---

## 3. 启动后端服务

```powershell
cd D:\vita-company\backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

打开 Swagger：

- `http://127.0.0.1:8000/docs`

---

## 4. 手工接口验收

先完成注册/登录并在 Swagger 右上角 `Authorize` 填入：

```text
Bearer <access_token>
```

### 4.1 创建会话

接口：`POST /api/v1/conversations`

示例请求：

```json
{
  "title": "第十阶段验收会话"
}
```

预期：

- 返回 `id`
- 会话创建成功

### 4.2 同步聊天验收

接口：`POST /api/v1/chat/send`

示例请求：

```json
{
  "conversation_id": 1,
  "content": "我最近有点焦虑，睡得不好。"
}
```

预期响应 `data` 至少包含：

- `assistant_status = "completed"`
- `prompt_version` 有值（当前实现为 `phase10.v1`）
- `assistant_message_id`
- `user_message_id`

### 4.3 消息列表验收

接口：`GET /api/v1/conversations/{conversation_id}/messages`

预期：

- user 消息 `status = completed`
- assistant 消息 `status = completed`
- assistant 的 `reply_to_message_id = user_message_id`
- 消息包含 `updated_at`

---

## 5. SSE 流式验收

建议在 PowerShell 用 `curl` 观察事件流：

```powershell
curl.exe -N -X POST "http://127.0.0.1:8000/api/v1/chat/send-stream" `
  -H "Authorization: Bearer <TOKEN>" `
  -H "Content-Type: application/json" `
  -d "{\"conversation_id\":1,\"content\":\"请一步步告诉我怎么调整作息\"}"
```

通过标准：

- 先收到 `start` 事件（`assistant_status = draft`）
- 过程中持续收到 `token` 事件
- 最后收到 `finish` 事件（`assistant_status = completed`）

---

## 6. cancel / regenerate 验收

### 6.1 取消 assistant 消息

接口：`POST /api/v1/chat/messages/{assistant_message_id}/cancel`

通过标准：

- 返回 `assistant_status = cancelled`
- 消息列表中该消息状态也为 `cancelled`

### 6.2 同步重生成

接口：`POST /api/v1/chat/messages/{assistant_message_id}/regenerate`

通过标准：

- 生成新的 assistant 消息
- 新消息 `assistant_message_id` 与旧消息不同
- 状态为 `completed`

### 6.3 流式重生成

接口：`POST /api/v1/chat/messages/{assistant_message_id}/regenerate-stream`

通过标准：

- 有 `start/token/finish` 事件流
- 最终消息状态正确落库

---

## 7. 数据库落库验收（可选但建议）

在后端目录执行：

```powershell
@'
import sqlite3
conn = sqlite3.connect("healthy_system.db")
cur = conn.cursor()
cur.execute(
    "SELECT id, role, status, reply_to_message_id, prompt_version, error_code, error_message, updated_at "
    "FROM messages ORDER BY id DESC LIMIT 20"
)
for row in cur.fetchall():
    print(row)
conn.close()
'@ | .\.venv\Scripts\python
```

通过标准：

- `messages` 中可看到第十阶段字段值
- 各场景状态与错误信息写入合理

---

## 8. 最终验收判定

全部满足以下条件即判定“第十阶段完成”：

1. `alembic upgrade head` 成功
2. `pytest` 全量通过
3. 同步聊天接口可用
4. SSE 流式输出可持续推送并正常结束
5. `cancel / regenerate / regenerate-stream` 全部可用
6. 消息状态机最终结果正确落库

