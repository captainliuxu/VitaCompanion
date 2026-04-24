from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timezone import BeijingDateTime, now_beijing
from app.db.session import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="text",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="completed",
        index=True,
    )
    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        BeijingDateTime(),
        default=now_beijing,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        BeijingDateTime(),
        default=now_beijing,
        onupdate=now_beijing,
        nullable=False,
    )
