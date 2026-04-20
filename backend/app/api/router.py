from fastapi import APIRouter

from app.api.routes.active_logs import router as active_logs_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.conversation_summaries import router as conversation_summaries_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.messages import router as messages_router
from app.api.routes.proactive import router as proactive_router
from app.api.routes.rag import router as rag_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.realtime import router as realtime_router
from app.api.routes.records import router as records_router
from app.api.routes.trigger_rules import router as trigger_rules_router
from app.api.routes.users import router as users_router
from app.api.routes.user_memories import router as user_memories_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(profiles_router)
api_router.include_router(records_router)
api_router.include_router(conversations_router)
api_router.include_router(conversation_summaries_router)
api_router.include_router(messages_router)
api_router.include_router(chat_router)
api_router.include_router(user_memories_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(rag_router)
api_router.include_router(trigger_rules_router)
api_router.include_router(active_logs_router)
api_router.include_router(proactive_router)
api_router.include_router(realtime_router)
