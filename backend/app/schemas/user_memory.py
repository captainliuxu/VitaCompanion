from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UserMemoryType(str, Enum):
    profile = "profile"
    preference = "preference"
    health = "health"
    routine = "routine"
    caution = "caution"
    custom = "custom"


class UserMemoryStatus(str, Enum):
    active = "active"
    archived = "archived"


class UserMemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    memory_type: UserMemoryType = UserMemoryType.profile
    source: str | None = Field(default=None, max_length=50)
    importance: int = Field(default=3, ge=1, le=5)


class UserMemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    memory_type: UserMemoryType | None = None
    source: str | None = Field(default=None, max_length=50)
    importance: int | None = Field(default=None, ge=1, le=5)
    status: UserMemoryStatus | None = None


class UserMemoryRead(BaseModel):
    id: int
    user_id: int
    content: str
    memory_type: UserMemoryType
    source: str | None = None
    importance: int
    status: UserMemoryStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserMemoryListData(BaseModel):
    items: list[UserMemoryRead]
