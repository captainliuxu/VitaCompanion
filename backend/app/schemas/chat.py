from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.rag import RagCitation


class ChatMode(str, Enum):
    plain = "plain"
    rag = "rag"


class ChatSendRequest(BaseModel):
    conversation_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1, max_length=2000)
    mode: ChatMode = ChatMode.rag
    knowledge_base_id: int | None = Field(default=None, ge=1)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatSendData(BaseModel):
    conversation_id: int
    user_message_id: int
    assistant_message_id: int
    reply: str
    assistant_status: str
    prompt_version: str | None = None
    replied_at: datetime
    citations: list[RagCitation] = Field(default_factory=list)


class ChatAssistantActionData(BaseModel):
    conversation_id: int
    assistant_message_id: int
    assistant_status: str
    error_code: int | None = None
    error_message: str | None = None
    updated_at: datetime
