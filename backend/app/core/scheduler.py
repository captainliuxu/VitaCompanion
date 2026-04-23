from __future__ import annotations

from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.trigger_rule import TriggerRule
from app.models.user import User
from app.services.proactive_service import proactive_service

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=settings.SCHEDULER_TIMEZONE)


def _build_next_run_time() -> datetime | None:
    if not settings.SCHEDULER_RUN_ON_STARTUP:
        return None

    return datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE))


def proactive_scan_job() -> None:
    logger.info("proactive scan job started")

    db = SessionLocal()
    try:
        users = list(
            db.scalars(
                select(User)
                .where(User.is_active.is_(True))
                .order_by(User.id.asc())
            ).all()
        )
        rules = list(
            db.scalars(
                select(TriggerRule)
                .where(TriggerRule.enabled.is_(True))
                .order_by(
                    TriggerRule.priority.asc(),
                    TriggerRule.id.asc(),
                )
            ).all()
        )

        if not users:
            logger.info("proactive scan skipped: no active users")
            return

        if not rules:
            logger.info("proactive scan skipped: no enabled trigger rules")
            return

        for user in users:
            for rule in rules:
                try:
                    result = proactive_service.execute_rule_for_user(
                        db=db,
                        user_id=user.id,
                        rule_id=rule.id,
                    )

                    if result["status"] in {
                        "created",
                        "blocked_by_window",
                        "blocked_by_rate_limit",
                        "blocked_by_cooldown",
                        "blocked_by_safety",
                    }:
                        break
                except Exception:
                    logger.exception(
                        "proactive scan failed for user_id=%s rule_id=%s",
                        user.id,
                        rule.id,
                    )
                    continue
    finally:
        db.close()

    logger.info("proactive scan job finished")


def start_scheduler() -> None:
    if not settings.SCHEDULER_ENABLED:
        logger.info("scheduler is disabled by config")
        return

    if scheduler.get_job("proactive_scan_job") is None:
        scheduler.add_job(
            proactive_scan_job,
            trigger="interval",
            minutes=settings.SCHEDULER_SCAN_INTERVAL_MINUTES,
            id="proactive_scan_job",
            next_run_time=_build_next_run_time(),
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    if not scheduler.running:
        scheduler.start()
        logger.info(
            "scheduler started, proactive_scan_job interval=%s minutes",
            settings.SCHEDULER_SCAN_INTERVAL_MINUTES,
        )


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
