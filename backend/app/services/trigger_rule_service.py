# 要同时负责三件事:
#
# 规则的增删改查
# 规则评估
# 手动检查时写主动日志

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.core.timezone import ensure_beijing_datetime, now_beijing
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.record import Record
from app.models.trigger_rule import TriggerRule
from app.schemas.trigger_rule import TriggerRuleCreate, TriggerRuleUpdate
from app.services.active_log_service import active_log_service


class TriggerRuleService:
    @staticmethod
    def _as_beijing_datetime(value: datetime) -> datetime:
        return ensure_beijing_datetime(value)

    def create(
        self,
        db: Session,
        payload: TriggerRuleCreate,
    ) -> TriggerRule:
        rule = TriggerRule(
            name=payload.name.strip(),
            trigger_type=payload.trigger_type.strip(),
            enabled=payload.enabled,
            condition_json=payload.condition_json,
            priority=payload.priority,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    def list_all(self, db: Session) -> list[TriggerRule]:
        stmt = select(TriggerRule).order_by(
            TriggerRule.priority.asc(),
            TriggerRule.id.asc(),
        )
        return list(db.scalars(stmt).all())

    def get_or_raise(self, db: Session, rule_id: int) -> TriggerRule:
        rule = db.get(TriggerRule, rule_id)
        if not rule:
            raise BusinessException(
                code=40462,
                message="trigger rule not found",
                status_code=404,
            )
        return rule

    def update(
        self,
        db: Session,
        rule_id: int,
        payload: TriggerRuleUpdate,
    ) -> TriggerRule:
        rule = self.get_or_raise(db, rule_id)
        update_data = payload.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] is not None:
            update_data["name"] = update_data["name"].strip()

        if (
            "trigger_type" in update_data
            and update_data["trigger_type"] is not None
        ):
            update_data["trigger_type"] = update_data["trigger_type"].strip()

        for field, value in update_data.items():
            setattr(rule, field, value)

        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    def delete(self, db: Session, rule_id: int) -> None:
        rule = self.get_or_raise(db, rule_id)
        db.delete(rule)
        db.commit()

    def evaluate_for_user(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        if not rule.enabled:
            return {
                "triggered": False,
                "reason": "rule is disabled",
                "trigger_type": rule.trigger_type,
            }

        if rule.trigger_type == "days_without_record":
            return self._evaluate_days_without_record(db, user_id, rule)

        if rule.trigger_type == "recent_chat_keyword":
            return self._evaluate_recent_chat_keyword(db, user_id, rule)

        if rule.trigger_type == "blood_pressure_threshold":
            return self._evaluate_blood_pressure_threshold(db, user_id, rule)

        if rule.trigger_type == "blood_glucose_consecutive_high":
            return self._evaluate_blood_glucose_consecutive_high(db, user_id, rule)

        if rule.trigger_type == "medication_time_reminder":
            return self._evaluate_medication_time_reminder(db, user_id, rule)

        if rule.trigger_type == "sleep_duration_low":
            return self._evaluate_sleep_duration_low(db, user_id, rule)

        if rule.trigger_type == "mood_consecutive_low":
            return self._evaluate_mood_consecutive_low(db, user_id, rule)

        raise BusinessException(
            code=40063,
            message=f"unsupported trigger_type: {rule.trigger_type}",
            status_code=400,
        )

    def check_for_user(
        self,
        db: Session,
        rule_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        rule = self.get_or_raise(db, rule_id)
        request_payload = {
            "rule_id": rule.id,
            "trigger_type": rule.trigger_type,
            "condition_json": rule.condition_json,
            "checked_at": now_beijing().isoformat(),
        }

        try:
            result = self.evaluate_for_user(db, user_id, rule)
            status = "triggered" if result["triggered"] else "not_triggered"
            log = active_log_service.create_log(
                db=db,
                user_id=user_id,
                trigger_rule_id=rule.id,
                action_type="rule_check",
                status=status,
                request_payload=request_payload,
                response_payload=result,
            )
            return {
                "log_id": log.id,
                "rule_id": rule.id,
                "user_id": user_id,
                "action_type": "rule_check",
                "status": status,
                "triggered": result["triggered"],
                "reason": result["reason"],
                "response_payload": result,
                "created_at": log.created_at,
            }
        except BusinessException as exc:
            active_log_service.create_log(
                db=db,
                user_id=user_id,
                trigger_rule_id=rule.id,
                action_type="rule_check",
                status="failed",
                request_payload=request_payload,
                response_payload={"error": exc.message},
            )
            raise

    def _evaluate_days_without_record(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        days_without_record = int(condition.get("days_without_record", 0))
        record_type = str(condition.get("record_type", "")).strip()

        if days_without_record <= 0:
            raise BusinessException(
                code=40064,
                message="days_without_record must be greater than 0",
                status_code=400,
            )

        if not record_type:
            raise BusinessException(
                code=40065,
                message="record_type is required for days_without_record",
                status_code=400,
            )

        stmt = (
            select(Record)
            .where(
                Record.user_id == user_id,
                Record.record_type == record_type,
            )
            .order_by(Record.record_time.desc(), Record.id.desc())
            .limit(1)
        )
        last_record = db.scalar(stmt)

        cutoff_time = now_beijing() - timedelta(days=days_without_record)
        last_record_time = None
        if last_record is not None:
            last_record_time = self._as_beijing_datetime(last_record.record_time)

        triggered = last_record_time is None or last_record_time < cutoff_time

        if last_record is None:
            reason = f"user has no {record_type} record yet"
        elif triggered:
            reason = f"last {record_type} record is older than {days_without_record} days"
        else:
            reason = f"user still has recent {record_type} record"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "record_type": record_type,
            "days_without_record": days_without_record,
            "last_record_time": last_record_time.isoformat() if last_record_time else None,
        }

    def _evaluate_recent_chat_keyword(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        raw_keywords = condition.get("keywords", [])
        keywords = [str(item).strip() for item in raw_keywords if str(item).strip()]
        recent_limit = int(condition.get("recent_limit", 10))

        if not keywords:
            raise BusinessException(
                code=40066,
                message="keywords cannot be empty",
                status_code=400,
            )

        if recent_limit <= 0:
            raise BusinessException(
                code=40067,
                message="recent_limit must be greater than 0",
                status_code=400,
            )

        stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(recent_limit)
        )
        recent_messages = list(db.scalars(stmt).all())

        matched_items: list[dict[str, Any]] = []
        for message in recent_messages:
            lowered_content = message.content.lower()
            for keyword in keywords:
                if keyword.lower() in lowered_content:
                    matched_items.append(
                        {
                            "keyword": keyword,
                            "message_id": message.id,
                        }
                    )

        matched_keywords = list(
            dict.fromkeys(item["keyword"] for item in matched_items)
        )
        matched_message_ids = list(
            dict.fromkeys(item["message_id"] for item in matched_items)
        )
        triggered = bool(matched_items)

        if triggered:
            reason = f"recent chat contains keywords: {', '.join(matched_keywords)}"
        else:
            reason = "recent chat does not contain configured keywords"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "recent_limit": recent_limit,
            "matched_keywords": matched_keywords,
            "matched_message_ids": matched_message_ids,
        }

    def _evaluate_blood_pressure_threshold(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        systolic_gte = int(condition.get("systolic_gte", 140))
        diastolic_gte = int(condition.get("diastolic_gte", 90))
        lookback_hours = int(condition.get("lookback_hours", 24))

        if lookback_hours <= 0:
            raise BusinessException(
                code=40068,
                message="lookback_hours must be greater than 0",
                status_code=400,
            )

        records = self._recent_records(
            db=db,
            user_id=user_id,
            record_type="blood_pressure",
            since=now_beijing() - timedelta(hours=lookback_hours),
            limit=20,
        )

        parsed_items: list[dict[str, Any]] = []
        for record in records:
            parsed = self._parse_blood_pressure(record.value)
            if parsed is None:
                continue
            systolic, diastolic = parsed
            item = {
                "record_id": record.id,
                "value": record.value,
                "systolic": systolic,
                "diastolic": diastolic,
                "record_time": self._as_beijing_datetime(record.record_time).isoformat(),
            }
            parsed_items.append(item)

        exceeded_items = [
            item
            for item in parsed_items
            if item["systolic"] >= systolic_gte or item["diastolic"] >= diastolic_gte
        ]
        triggered = bool(exceeded_items)

        if triggered:
            latest = exceeded_items[0]
            reason = (
                f"latest blood pressure {latest['systolic']}/{latest['diastolic']} "
                f"exceeds threshold {systolic_gte}/{diastolic_gte}"
            )
        elif parsed_items:
            reason = "recent blood pressure records are below threshold"
        else:
            reason = "no valid blood pressure record in lookback window"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "record_type": "blood_pressure",
            "systolic_gte": systolic_gte,
            "diastolic_gte": diastolic_gte,
            "lookback_hours": lookback_hours,
            "matched_records": exceeded_items,
        }

    def _evaluate_blood_glucose_consecutive_high(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        glucose_gte = float(
            condition.get("glucose_gte", condition.get("value_gte", 7.0))
        )
        consecutive_count = int(condition.get("consecutive_count", 3))
        lookback_days = int(condition.get("lookback_days", 7))

        if consecutive_count <= 0:
            raise BusinessException(
                code=40069,
                message="consecutive_count must be greater than 0",
                status_code=400,
            )
        if lookback_days <= 0:
            raise BusinessException(
                code=40070,
                message="lookback_days must be greater than 0",
                status_code=400,
            )

        records = self._recent_records(
            db=db,
            user_id=user_id,
            record_type="blood_glucose",
            since=now_beijing() - timedelta(days=lookback_days),
            limit=max(consecutive_count, 10),
        )

        parsed_items: list[dict[str, Any]] = []
        for record in records:
            value = self._parse_float(record.value)
            if value is None:
                continue
            parsed_items.append(
                {
                    "record_id": record.id,
                    "value": value,
                    "raw_value": record.value,
                    "unit": record.unit,
                    "record_time": self._as_beijing_datetime(record.record_time).isoformat(),
                }
            )

        latest_items = parsed_items[:consecutive_count]
        triggered = (
            len(latest_items) == consecutive_count
            and all(item["value"] >= glucose_gte for item in latest_items)
        )

        if triggered:
            reason = f"latest {consecutive_count} blood glucose records are >= {glucose_gte}"
        elif parsed_items:
            reason = "recent blood glucose records do not meet consecutive high condition"
        else:
            reason = "no valid blood glucose record in lookback window"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "record_type": "blood_glucose",
            "glucose_gte": glucose_gte,
            "consecutive_count": consecutive_count,
            "lookback_days": lookback_days,
            "matched_records": latest_items if triggered else [],
        }

    def _evaluate_medication_time_reminder(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        target_time_text = str(condition.get("time", "")).strip()
        medication_name = str(condition.get("medication_name", "用药")).strip() or "用药"
        window_minutes = int(condition.get("window_minutes", 30))

        if window_minutes <= 0:
            raise BusinessException(
                code=40073,
                message="window_minutes must be greater than 0",
                status_code=400,
            )

        try:
            target_time = datetime.strptime(target_time_text, "%H:%M").time()
        except ValueError as exc:
            raise BusinessException(
                code=40074,
                message="time format must be HH:MM",
                status_code=400,
            ) from exc

        now = now_beijing().replace(second=0, microsecond=0)
        today_target = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )
        candidates = [
            today_target - timedelta(days=1),
            today_target,
            today_target + timedelta(days=1),
        ]
        delta_minutes = min(
            abs((now - candidate).total_seconds()) / 60
            for candidate in candidates
        )
        triggered = delta_minutes <= window_minutes

        if triggered:
            reason = f"current time is within {window_minutes} minutes of medication time {target_time_text}"
        else:
            reason = f"current time is outside medication reminder window for {target_time_text}"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "record_type": "medication",
            "time": target_time_text,
            "window_minutes": window_minutes,
            "medication_name": medication_name,
            "delta_minutes": round(delta_minutes, 2),
        }

    def _evaluate_sleep_duration_low(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        hours_lt = float(condition.get("hours_lt", 5))
        lookback_days = int(condition.get("lookback_days", 1))

        if lookback_days <= 0:
            raise BusinessException(
                code=40075,
                message="lookback_days must be greater than 0",
                status_code=400,
            )

        records = self._recent_records(
            db=db,
            user_id=user_id,
            record_type="sleep",
            since=now_beijing() - timedelta(days=lookback_days),
            limit=10,
        )

        latest_valid: dict[str, Any] | None = None
        for record in records:
            value = self._parse_float(record.value)
            if value is None:
                continue
            latest_valid = {
                "record_id": record.id,
                "value": value,
                "raw_value": record.value,
                "unit": record.unit,
                "record_time": self._as_beijing_datetime(record.record_time).isoformat(),
            }
            break

        triggered = latest_valid is not None and latest_valid["value"] < hours_lt

        if triggered:
            reason = f"latest sleep duration {latest_valid['value']} hours is below {hours_lt}"
        elif latest_valid is not None:
            reason = "latest sleep duration is not below threshold"
        else:
            reason = "no valid sleep record in lookback window"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "record_type": "sleep",
            "hours_lt": hours_lt,
            "lookback_days": lookback_days,
            "matched_record": latest_valid if triggered else None,
        }

    def _evaluate_mood_consecutive_low(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
    ) -> dict[str, Any]:
        condition = rule.condition_json or {}
        consecutive_count = int(condition.get("consecutive_count", 2))
        lookback_days = int(condition.get("lookback_days", 7))
        score_lte = condition.get("score_lte")
        low_keywords = [
            str(item).strip().lower()
            for item in condition.get(
                "low_keywords",
                ["低落", "难过", "焦虑", "抑郁", "不好", "差", "low", "sad"],
            )
            if str(item).strip()
        ]

        if consecutive_count <= 0:
            raise BusinessException(
                code=40076,
                message="consecutive_count must be greater than 0",
                status_code=400,
            )
        if lookback_days <= 0:
            raise BusinessException(
                code=40077,
                message="lookback_days must be greater than 0",
                status_code=400,
            )

        records = self._recent_records(
            db=db,
            user_id=user_id,
            record_type="mood",
            since=now_beijing() - timedelta(days=lookback_days),
            limit=max(consecutive_count, 10),
        )

        evaluated_items: list[dict[str, Any]] = []
        for record in records:
            lowered_value = record.value.lower()
            numeric_value = self._parse_float(record.value)
            is_low = any(keyword in lowered_value for keyword in low_keywords)
            if score_lte is not None and numeric_value is not None:
                is_low = is_low or numeric_value <= float(score_lte)
            evaluated_items.append(
                {
                    "record_id": record.id,
                    "value": record.value,
                    "is_low": is_low,
                    "record_time": self._as_beijing_datetime(record.record_time).isoformat(),
                }
            )

        latest_items = evaluated_items[:consecutive_count]
        triggered = (
            len(latest_items) == consecutive_count
            and all(item["is_low"] for item in latest_items)
        )

        if triggered:
            reason = f"latest {consecutive_count} mood records are low"
        elif evaluated_items:
            reason = "recent mood records do not meet consecutive low condition"
        else:
            reason = "no mood record in lookback window"

        return {
            "triggered": triggered,
            "reason": reason,
            "trigger_type": rule.trigger_type,
            "record_type": "mood",
            "consecutive_count": consecutive_count,
            "lookback_days": lookback_days,
            "matched_records": latest_items if triggered else [],
        }

    def _recent_records(
        self,
        db: Session,
        user_id: int,
        record_type: str,
        since: datetime,
        limit: int,
    ) -> list[Record]:
        stmt = (
            select(Record)
            .where(
                Record.user_id == user_id,
                Record.record_type == record_type,
                Record.record_time >= since,
            )
            .order_by(Record.record_time.desc(), Record.id.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    def _parse_blood_pressure(self, value: str) -> tuple[int, int] | None:
        numbers = re.findall(r"\d+", value)
        if len(numbers) < 2:
            return None
        return int(numbers[0]), int(numbers[1])

    def _parse_float(self, value: str) -> float | None:
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match is None:
            return None
        return float(match.group(0))


trigger_rule_service = TriggerRuleService()
