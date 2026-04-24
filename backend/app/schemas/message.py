from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class MessageStatus(str, Enum):
    draft = "draft"
    streaming = "streaming"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)
    message_type: str = Field(default="text", min_length=1, max_length=30)


class MessageRead(BaseModel):
    id: int
    conversation_id: int
    role: MessageRole
    content: str
    message_type: str
    status: MessageStatus
    reply_to_message_id: int | None = None
    prompt_version: str | None = None
    error_code: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageListData(BaseModel):
    items: list[MessageRead]
