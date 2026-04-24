from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

TIME_PATTERN = r"^\d{2}:\d{2}$"


class ProactiveWindowUpdate(BaseModel):
    enabled: bool = True
    quiet_hours_start: str = Field(default="22:00", pattern=TIME_PATTERN)
    quiet_hours_end: str = Field(default="08:00", pattern=TIME_PATTERN)
    max_trigger_per_day: int = Field(default=1, ge=1, le=20)


class ProactiveWindowRead(ProactiveWindowUpdate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProactiveMessageRead(BaseModel):
    id: int
    user_id: int
    trigger_rule_id: int | None = None
    trigger_type: str
    title: str
    content: str
    status: str
    created_at: datetime
    displayed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProactiveMessageListData(BaseModel):
    items: list[ProactiveMessageRead]


class ProactiveDecisionRead(BaseModel):
    id: int
    user_id: int
    trigger_rule_id: int | None = None
    trigger_type: str
    triggered: bool
    ai_should_remind: bool | None = None
    severity: str | None = None
    reason: str | None = None
    title: str | None = None
    message: str | None = None
    cooldown_hours: int | None = None
    safety_label: str | None = None
    status: str
    blocked_reason: str | None = None
    input_snapshot_json: dict[str, Any] | None = None
    ai_response_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProactiveDecisionListData(BaseModel):
    items: list[ProactiveDecisionRead]


class ProactiveExecuteData(BaseModel):
    log_id: int
    decision_id: int | None = None
    rule_id: int
    triggered: bool
    message_created: bool
    status: str
    reason: str
    proactive_message: ProactiveMessageRead | None = None
