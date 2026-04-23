from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezone import ensure_beijing_datetime, now_beijing
from app.models.proactive_decision import ProactiveDecision


class ProactiveCooldownService:
    def is_in_cooldown(
        self,
        db: Session,
        user_id: int,
        trigger_rule_id: int | None,
        trigger_type: str,
        cooldown_hours: int,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        current = ensure_beijing_datetime(now or now_beijing())

        if trigger_type == "medication_time_reminder":
            day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
            latest = self._latest_created_since(
                db=db,
                user_id=user_id,
                trigger_rule_id=trigger_rule_id,
                trigger_type=trigger_type,
                since=day_start,
            )
            if latest:
                return True, "same medication reminder already created today"
            return False, "allowed"

        cutoff = current - timedelta(hours=cooldown_hours)
        latest = self._latest_created_since(
            db=db,
            user_id=user_id,
            trigger_rule_id=trigger_rule_id,
            trigger_type=trigger_type,
            since=cutoff,
        )
        if latest:
            return True, f"same trigger is in cooldown for {cooldown_hours} hours"
        return False, "allowed"

    def _latest_created_since(
        self,
        db: Session,
        user_id: int,
        trigger_rule_id: int | None,
        trigger_type: str,
        since: datetime,
    ) -> ProactiveDecision | None:
        stmt = select(ProactiveDecision).where(
            ProactiveDecision.user_id == user_id,
            ProactiveDecision.trigger_type == trigger_type,
            ProactiveDecision.status == "created",
            ProactiveDecision.created_at >= since,
        )
        if trigger_rule_id is None:
            stmt = stmt.where(ProactiveDecision.trigger_rule_id.is_(None))
        else:
            stmt = stmt.where(ProactiveDecision.trigger_rule_id == trigger_rule_id)

        stmt = stmt.order_by(
            ProactiveDecision.created_at.desc(),
            ProactiveDecision.id.desc(),
        ).limit(1)
        return db.scalar(stmt)


proactive_cooldown_service = ProactiveCooldownService()
