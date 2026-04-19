import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exception import register_exception_handlers
from app.core.logging_config import configure_logging
from app.core.scheduler import shutdown_scheduler, start_scheduler
from app.ws.manager import realtime_manager

configure_logging()

OPENAPI_TAGS = [
    {"name": "health", "description": "服务与数据库连通性检查"},
    {"name": "auth", "description": "注册与登录"},
    {"name": "users", "description": "当前登录用户信息"},
    {"name": "profiles", "description": "当前用户健康档案"},
    {"name": "records", "description": "健康记录 CRUD 与筛选"},
    {"name": "conversations", "description": "会话管理"},
    {"name": "conversation-summaries", "description": "会话摘要生成与读取"},
    {"name": "messages", "description": "会话消息查询与调试写入"},
    {"name": "chat", "description": "聊天主链路"},
    {"name": "user-memories", "description": "用户长期记忆 CRUD"},
    {"name": "trigger-rules", "description": "触发规则配置与检查"},
    {"name": "active-logs", "description": "主动行为日志"},
    {"name": "proactive", "description": "主动窗口、主动消息与主动执行"},
    {"name": "realtime", "description": "WebSocket 与实时推送测试"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    realtime_manager.bind_loop(asyncio.get_running_loop())
    start_scheduler()

    try:
        yield
    finally:
        shutdown_scheduler()
        realtime_manager.reset()


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
        description="阶段十一版本：聊天流式输出、消息状态机、会话摘要、长期记忆与上下文工程。",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    register_exception_handlers(app)

    return app


app = create_application()
