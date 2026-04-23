from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import ensure_beijing_datetime
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.profile import Profile
from app.models.proactive_window import ProactiveWindow
from app.models.record import Record
from app.models.trigger_rule import TriggerRule
from app.services.user_memory_service import user_memory_service


class ProactiveSignalService:
    RECENT_RECORD_LIMIT = 10
    RECENT_USER_MESSAGE_LIMIT = 5
    ACTIVE_MEMORY_LIMIT = 8

    def build_context_package(
        self,
        db: Session,
        user_id: int,
        trigger_rule: TriggerRule,
        evaluation: dict[str, Any],
        window: ProactiveWindow,
        already_triggered_today: int,
    ) -> dict[str, Any]:
        profile = self._get_profile(db, user_id)

        return {
            "user_profile": self._serialize_profile(profile),
            "trigger": {
                "trigger_rule_id": trigger_rule.id,
                "trigger_type": trigger_rule.trigger_type,
                "reason": evaluation.get("reason"),
                "evaluation": evaluation,
            },
            "recent_records": self._recent_records(db, user_id),
            "recent_user_messages": self._recent_user_messages(db, user_id),
            "active_memories": self._active_memories(db, user_id),
            "proactive_policy": {
                "quiet_hours": f"{window.quiet_hours_start}-{window.quiet_hours_end}",
                "max_trigger_per_day": window.max_trigger_per_day,
                "already_triggered_today": already_triggered_today,
            },
        }

    def _get_profile(self, db: Session, user_id: int) -> Profile | None:
        return db.scalar(select(Profile).where(Profile.user_id == user_id))

    def _serialize_profile(self, profile: Profile | None) -> dict[str, Any]:
        if profile is None:
            return {
                "age": None,
                "gender": None,
                "chronic_history": None,
                "allergy_history": None,
            }

        return {
            "age": profile.age,
            "gender": profile.gender,
            "chronic_history": profile.chronic_history,
            "allergy_history": profile.allergy_history,
        }

    def _recent_records(self, db: Session, user_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(Record)
            .where(Record.user_id == user_id)
            .order_by(Record.record_time.desc(), Record.id.desc())
            .limit(self.RECENT_RECORD_LIMIT)
        )
        records = list(db.scalars(stmt).all())
        return [
            {
                "record_type": record.record_type,
                "value": record.value,
                "unit": record.unit,
                "note": record.note,
                "record_time": ensure_beijing_datetime(record.record_time).isoformat(),
            }
            for record in records
        ]

    def _recent_user_messages(self, db: Session, user_id: int) -> list[str]:
        stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Message.role == "user",
                Message.status == "completed",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(self.RECENT_USER_MESSAGE_LIMIT)
        )
        messages = list(db.scalars(stmt).all())
        messages.reverse()
        return [message.content for message in messages if message.content]

    def _active_memories(self, db: Session, user_id: int) -> list[str]:
        memories = user_memory_service.list_for_user(
            db=db,
            user_id=user_id,
            include_archived=False,
            limit=self.ACTIVE_MEMORY_LIMIT,
        )
        return [memory.content for memory in memories if memory.content]


proactive_signal_service = ProactiveSignalService()
