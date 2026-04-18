from datetime import datetime

from pydantic import BaseModel, Field

class ChatSendRequest(BaseModel):
    conversation_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1, max_length=2000)


class ChatSendData(BaseModel):
    conversation_id: int
    user_message_id: int
    assistant_message_id: int
    reply: str
    assistant_status: str
    prompt_version: str | None = None
    replied_at: datetime


class ChatAssistantActionData(BaseModel):
    conversation_id: int
    assistant_message_id: int
    assistant_status: str
    error_code: int | None = None
    error_message: str | None = None
    updated_at: datetime
