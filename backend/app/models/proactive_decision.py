from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timezone import BeijingDateTime, now_beijing
from app.db.session import Base


class ProactiveDecision(Base):
    __tablename__ = "proactive_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("trigger_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_should_remind: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created", index=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    input_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ai_response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        BeijingDateTime(),
        default=now_beijing,
        nullable=False,
        index=True,
    )
