# Healthy System 后端进阶开发计划

## 一、文档用途

这份 `dev_order_plan2.md` 只保留你作为后端负责人应该推进的内容。

- 不再把前端页面开发写进这份文档。
- 前端交付清单单独放在 `frontend/FRONTEND_TODO.md`。
- 本文以当前工作区实际代码为准，不以过期记忆或口头状态为准。

---

## 二、当前项目的真实起点

结合当前仓库代码、README 和 `.codex_memory`，可以明确这几个事实：

### 1. 当前稳定主线已推进到 Phase 11 后端

已经有的后端模块主要是：

- `auth`
- `users`
- `profiles`
- `records`
- `conversations`
- `messages`
- `chat` 同步发送、SSE 流式发送、取消与重生成
- `conversation_summaries`
- `user_memories`
- `chat_context_service`
- `core/prompts.py` prompt 版本化
- `trigger_rules`
- `active_logs`
- `proactive`
- `realtime`

### 2. 第十、十一阶段已经完成后端闭环

当前工作区已经补齐第十、十一阶段的源码、迁移和测试：

- 第十阶段：聊天流式输出、消息状态机、取消、同步/流式重生成、状态落库。
- 第十一阶段：会话摘要、长期记忆 CRUD、上下文预算裁剪、prompt 版本化、聊天主链路上下文注入。
- 当前 Alembic head 为 `b8f3c2d4e6a7`。
- 当前后端测试为 `11 passed`。

### 3. 后端进阶开发的下一步

下一步从第十二阶段开始：知识库导入、切片与向量库。不要把 RAG、工具调用或异步任务提前混进聊天主链路。

---

## 三、本文的边界

这份文档只讨论后端工作，不再包含这些内容：

- 前端流式渲染
- 前端引用来源展示
- 前端知识库管理页
- 前端索引任务状态页
- 前端主动消息调试页

这些任务已经拆到：

- `frontend/FRONTEND_TODO.md`

---

## 四、后端总开发顺序

建议按下面顺序推进：

1. `P0`：恢复可运行基线，清理未完成的 10/11 残留
2. 第十阶段：聊天流式输出与消息状态机
3. 第十一阶段：上下文工程与长期记忆
4. 第十二阶段：知识库导入、切片与向量库
5. 第十三阶段：RAG 检索问答与引用
6. 第十四阶段：工具调用与结构化健康分析
7. 第十五阶段：主动服务 2.0
8. 第十六阶段：异步任务、缓存与性能治理
9. 第十七阶段：评测、观测、安全与成本治理
10. 第十八阶段：部署、存储升级与产品化

---

## 五、后端开发总原则

### 1. 先把主链路做稳，再叠加增强能力

顺序必须是：

> 聊天主链路稳定化 -> 上下文工程 -> 知识库入库 -> RAG -> 工具调用 -> 主动服务升级 -> 异步化与治理

不要跳过前面的基础设施，直接去做花哨能力。

### 2. 所有进阶能力都必须挂在现有业务边界上

无论你后面做什么，都不能绕过这些既有底线：

- 用户鉴权
- 资源归属校验
- 数据落库
- 错误码和状态可追踪
- 时间统一按 `Asia/Shanghai`

### 3. 先完成数据模型和迁移，再写接口

阶段 10 以后，很多能力都不只是“多一个路由”：

- 会新增字段
- 会新增表
- 会新增状态机
- 会新增失败路径

所以每一阶段都按这个顺序：

1. model
2. alembic migration
3. schema
4. service
5. route
6. tests

### 4. 没有自动化验证，不算真正完成

每个阶段至少补：

- 路由层测试
- 关键 service 行为测试
- 权限测试
- 失败路径测试

---

## 六、P0：恢复可运行基线

> 当前状态：已完成。`import app.main`、`alembic upgrade head`、`pytest tests -q` 均已通过。

### 阶段目标

把“混入了一半阶段 10/11 字段，但源码没闭环”的状态收敛成一个能正常启动、能正常迁移、能正常测试的后端基线。

### 必须完成的内容

#### 1. 处理阶段 10/11 的残留引用

曾经需要先统一这几类不一致：

- `db/base.py` 引用了缺失模型
- `models/__init__.py` 引用了缺失模型
- `schemas/chat.py` 已经加入了 `assistant_status`、`prompt_version`
- `schemas/message.py` 已经加入了 `status`、`reply_to_message_id`、`error_code` 等字段
- 但 `models/message.py` 还没有这些字段
- 也没有对应 Alembic 迁移

处理方式已选定为补完阶段 10/11，而不是回退：

1. 阶段 10 已补完：流式聊天、消息状态机、取消和重生成。
2. 阶段 11 已补完：摘要、长期记忆、上下文工程和 prompt 版本化。

#### 2. 修复导入和启动链路

至少保证下面这些动作能成功：

- `import app.main`
- `uvicorn app.main:app --reload`
- `alembic upgrade head`
- `pytest tests -q`

#### 3. 校准文档与代码现状

保证下面几份文档描述和实际代码一致：

- `README.md`
- `.codex_memory/project_snapshot.md`
- 本文档

### 阶段验收标准

- 后端可正常导入和启动
- Alembic 迁移可执行
- 测试可运行
- 文档不再错误声称“10/11 已完成”

---

## 七、第十阶段：聊天流式输出与消息状态机

### 阶段目标

把当前只有同步聊天返回的链路，升级成真正可维护的后端流式聊天基础设施。

注意：这一阶段只做后端，不负责前端渲染。

### 必须完成的内容

#### 1. 扩展 `messages` 表结构

建议为 assistant 消息增加至少这些字段：

- `status`
- `reply_to_message_id`
- `prompt_version`
- `error_code`
- `error_message`
- `updated_at`

建议状态机至少支持：

- `draft`
- `streaming`
- `completed`
- `failed`
- `cancelled`

#### 2. 增加 Alembic 迁移

把阶段 10 新字段正式落到数据库里，不要只改 Pydantic schema。

#### 3. 升级 `llm_service`

至少形成两套稳定能力：

- `chat()`：保留同步调用
- `stream_chat()`：新增 token 流式生成

两者要共用：

- 模型配置
- provider 适配
- 超时处理
- 异常处理

#### 4. 增加流式聊天接口

后端建议优先采用 `SSE`：

- `POST /api/v1/chat/send-stream`

不要把现有主动消息 `WebSocket` 和聊天 token 流硬塞成一套协议。

#### 5. 增加取消与重生成能力

后端至少补这几个接口：

- `POST /api/v1/chat/messages/{assistant_message_id}/cancel`
- `POST /api/v1/chat/messages/{assistant_message_id}/regenerate`
- `POST /api/v1/chat/messages/{assistant_message_id}/regenerate-stream`

#### 6. 重构 `chat_service` 和 `message_service`

要支持这些后端语义：

- 先创建 assistant `draft`
- 流式过程中转成 `streaming`
- 完成后转成 `completed`
- 取消后转成 `cancelled`
- 失败后转成 `failed`

#### 7. 补自动化测试

至少覆盖：

- stream 成功
- stream 失败
- cancel
- regenerate
- 同步接口仍然可用

### 这一阶段不要做的事

- 不要把 RAG 混进来
- 不要同时重写主动消息 WebSocket
- 不要要求前端先完成再写后端

### 阶段验收标准

- 同步聊天仍可正常工作
- SSE 能持续推送 token 事件
- assistant 消息状态可正确流转
- 取消和重生成有清晰状态结果
- 数据库里能正确保留最终消息状态

---

## 八、第十一阶段：上下文工程与长期记忆

> 当前状态：已完成后端最小闭环。已新增 `conversation_summaries`、`user_memories`、`chat_context_service.py`、`core/prompts.py` 和对应路由/测试。

### 阶段目标

让聊天从“只带最近若干条消息”升级成“有预算控制、有摘要、有长期记忆”的后端上下文系统。

### 必须完成的内容

#### 1. 新增 `conversation_summaries`

建议增加：

- `conversation_summary` 模型
- `conversation_summary_service.py`
- 会话摘要生成与读取接口

#### 2. 新增 `user_memories`

建议增加：

- `user_memory` 模型
- `user_memory_service.py`
- 用户长期记忆 CRUD 路由

#### 3. 新增上下文构建服务

建议拆出：

- `chat_context_service.py`

职责包括：

- token 预算
- 最近消息裁剪
- 摘要拼接
- 长期记忆拼接
- prompt version 管理

#### 4. 增加 prompt 模板版本化

不要继续把系统提示词硬写死在 `chat_service.py` 的大字符串里。

建议拆成：

- `core/prompts.py` 或
- `prompt_service.py`

至少做到：

- 有默认 prompt version
- 可在消息结果里记录本次使用的版本

#### 5. 视情况补自动标题

如果要做，建议放在会话服务侧：

- 首轮消息后生成 conversation title

#### 6. 补测试

至少覆盖：

- 长对话预算截断
- 摘要生成
- 长期记忆 CRUD
- context 拼装结果

### 阶段验收标准

- 会话上下文不再只靠最近 10 条消息
- 可以生成和读取会话摘要
- 可以创建和使用用户长期记忆
- prompt 版本能被记录

---

## 九、第十二阶段：知识库导入、切片与向量库

### 阶段目标

先把知识库“入库”和“可检索”这件事做扎实，但暂时不把它硬接到聊天主链路里。

### 必须完成的内容

#### 1. 建立知识库数据模型

建议新增：

- `knowledge_base`
- `knowledge_document`
- `knowledge_chunk`

#### 2. 支持最小文档导入

第一版建议只支持：

- `md`
- `txt`
- `json`

#### 3. 建立切片策略

至少明确：

- `chunk_size`
- `overlap`
- 清洗规则
- chunk metadata

#### 4. 建立 embedding 服务

建议新增：

- `embedding_service.py`

#### 5. 建立向量存储适配层

建议新增：

- `vector_store_service.py`

学习版可以先选：

- `Chroma`
- 或 `FAISS`

#### 6. 增加索引状态管理

至少支持：

- `pending`
- `processing`
- `completed`
- `failed`

### 阶段验收标准

- 能创建知识库
- 能导入文档
- 能切片并生成 embedding
- 能写入向量索引
- 能查询最相近的 chunk

---

## 十、第十三阶段：RAG 检索问答与引用

### 阶段目标

把知识库检索能力正式接入聊天主链路。

### 必须完成的内容

#### 1. 新增 `rag_service`

建议职责包括：

- 查询改写
- 检索召回
- 可选重排
- 上下文组装
- 回答生成
- 引用信息整理

#### 2. 升级聊天主链路

不要重写一套平行聊天系统。

建议改法：

- 保留 `chat_service`
- 增加 `plain` / `rag` 模式
- 或新增 `chat_orchestrator_service`

#### 3. 返回引用元数据

RAG 响应至少带：

- 文档标题
- chunk id 或序号
- 命中文本摘要

#### 4. 增加调试接口

例如：

- `POST /api/v1/rag/retrieve-debug`

### 阶段验收标准

- 用户可以基于知识库提问
- 返回结果包含来源引用
- 检索结果可以单独调试
- 检索失败时有明确回退策略

---

## 十一、第十四阶段：工具调用与结构化健康分析

### 阶段目标

让模型不仅会生成自然语言，还能在受控边界内读取真实业务数据做分析。

### 必须完成的内容

#### 1. 定义受控工具集

第一批建议工具：

- `get_user_profile`
- `get_recent_records`
- `get_record_stats`
- `get_recent_conversation_summary`
- `get_pending_proactive_messages`

#### 2. 新增工具编排层

建议新增：

- `tool_call_service.py`

职责包括：

- 工具定义
- 参数校验
- 权限校验
- 调用日志
- 结构化结果规整

#### 3. 增加结构化输出能力

例如：

- 血压趋势分析
- 周报摘要
- 风险卡片
- 作息建议卡片

### 阶段验收标准

- 可以基于真实用户数据做分析问答
- 工具调用全程可追踪
- 结果可结构化返回
- 无权限数据不能被工具层读取

---

## 十二、第十五阶段：主动服务 2.0

### 阶段目标

把现有“规则命中 -> 生成主动消息”升级成基于上下文和频控策略的后端主动服务链路。

### 必须完成的内容

#### 1. 升级主动决策链路

建议主链路变成：

1. 规则命中
2. 主动窗口校验
3. 频控与去重
4. 查询最近记录
5. 查询会话摘要
6. 查询长期记忆
7. 必要时接知识库检索
8. 生成主动消息
9. 落库、留痕、推送

#### 2. 支持风险等级

建议至少：

- `info`
- `warn`
- `urgent`

#### 3. 模板化与 LLM 混合生成

建议：

- 低风险场景优先模板化
- 复杂场景再走 LLM 润色

### 阶段验收标准

- 主动消息能结合近期记录和上下文生成
- 不会高频重复轰炸
- 风险等级清晰可追踪
- 主动消息仍然可落库、可日志追踪、可实时推送

---

## 十三、第十六阶段：异步任务、缓存与性能治理

### 阶段目标

把重任务从同步请求里拆出去，让知识库、摘要、报告、批量任务具备正式后端执行链路。

### 必须完成的内容

#### 1. 引入任务队列

建议选定正式方案，例如：

- `Redis + Celery`
- 或 `Redis + RQ`

#### 2. 把这些任务异步化

优先级最高：

- 文档 embedding
- 文档重建索引
- 会话摘要生成
- 长期记忆提取
- 批量主动扫描
- 报告生成

#### 3. 增加任务状态查询

至少支持：

- `pending`
- `running`
- `success`
- `failed`

#### 4. 增加缓存层

优先缓存：

- 热门检索结果
- 用户画像摘要
- 最近记录统计结果

#### 5. 增加幂等与重试

必须考虑：

- 重复上传文档
- 重复触发建索引
- embedding 供应商临时失败

### 阶段验收标准

- 长任务不再阻塞同步请求
- 可以查询任务状态
- 失败任务可重试
- Scheduler 只负责触发，不直接执行长任务

---

## 十四、第十七阶段：评测、观测、安全与成本治理

### 阶段目标

把项目推进到“可衡量、可定位、可控制”的可持续迭代状态。

### 必须完成的内容

#### 1. 建立 LLM 调用指标

至少记录：

- 延迟
- token 用量
- 成本估算
- 失败率
- 超时率

#### 2. 建立 RAG 指标

至少记录：

- 召回 chunk 数
- 来源分布
- 无结果率
- 引用覆盖率

#### 3. 建立回归评测集

至少覆盖：

- 普通聊天
- 知识库问答
- 主动服务触发

#### 4. 做安全控制

至少包括：

- 日志脱敏
- 上传文件校验
- 外部知识库权限隔离
- 接口限流

### 阶段验收标准

- 能定位一次失败的模型调用
- 能对比不同 prompt 或检索参数效果
- 能监控高成本接口
- 敏感字段不会直接裸写进日志

---

## 十五、第十八阶段：部署、存储升级与产品化

### 阶段目标

把后端从本地工程升级成可部署、可迁移、可扩展的正式原型。

### 必须完成的内容

#### 1. 升级数据库和向量存储

建议从：

- `SQLite`

升级到：

- `PostgreSQL`
- `pgvector` 或独立向量库

#### 2. 独立文件存储

当知识库开始支持较大文件后，建议接入：

- 对象存储

#### 3. 拆分运行角色

至少拆成：

- API
- Worker
- Scheduler
- DB
- Vector Store

#### 4. 建立 CI/CD 和部署检查

至少包含：

- 自动化测试
- 迁移校验
- 环境配置检查

### 阶段验收标准

- 后端可重复部署
- 数据库迁移路径清晰
- API / Worker / Scheduler 边界明确
- 知识库、RAG、异步任务可以稳定运行

---

## 十六、最小后端进阶闭环

如果你不打算一次做完全部后端进阶版，最推荐先完成这条主线：

1. `P0` 恢复可运行基线
2. 第十阶段：流式聊天与消息状态机
3. 第十一阶段：上下文工程与长期记忆
4. 第十二阶段：知识库导入与向量库
5. 第十三阶段：RAG 检索问答
6. 第十六阶段：索引与 embedding 异步化
7. 第十七阶段：日志、评测与观测

这条线做完后，你的后端才算真正从比赛版进入可扩展的 AI 后端原型。

---

## 十七、建议新增的后端核心文件

建议优先按下面骨架扩展：

```text
backend/
├─ alembic/versions/
├─ app/
│  ├─ api/routes/
│  │  ├─ chat.py
│  │  ├─ conversation_summaries.py
│  │  ├─ user_memories.py
│  │  ├─ knowledge_bases.py
│  │  ├─ rag.py
│  │  └─ tools.py
│  ├─ models/
│  │  ├─ conversation_summary.py
│  │  ├─ user_memory.py
│  │  ├─ knowledge_base.py
│  │  ├─ knowledge_document.py
│  │  └─ knowledge_chunk.py
│  ├─ schemas/
│  │  ├─ chat.py
│  │  ├─ conversation_summary.py
│  │  ├─ user_memory.py
│  │  ├─ knowledge_base.py
│  │  ├─ rag.py
│  │  └─ tool_call.py
│  ├─ services/
│  │  ├─ chat_context_service.py
│  │  ├─ conversation_summary_service.py
│  │  ├─ user_memory_service.py
│  │  ├─ embedding_service.py
│  │  ├─ vector_store_service.py
│  │  ├─ knowledge_ingestion_service.py
│  │  ├─ rag_service.py
│  │  ├─ prompt_service.py
│  │  └─ tool_call_service.py
│  └─ tasks/
│     ├─ embeddings.py
│     ├─ memory.py
│     ├─ reports.py
│     └─ proactive_jobs.py
```

---

## 十八、一句话版本

你现在最合理的后端推进顺序不是“继续催前端再等等”，而是：

> **先把当前 broken 的 10/11 残留收拢成可运行基线，再完成流式聊天和消息状态机，再补上下文工程、知识库、RAG、工具调用、主动服务异步化和治理。**
