from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummaryGenerateRequest(BaseModel):
    max_messages: int = Field(default=30, ge=1, le=100)


class ConversationSummaryRead(BaseModel):
    id: int
    user_id: int
    conversation_id: int
    summary: str
    prompt_version: str
    source_message_count: int
    last_message_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
