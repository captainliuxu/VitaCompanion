from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezone import now_beijing
from app.models.active_log import ActiveLog
from app.models.proactive_decision import ProactiveDecision
from app.models.proactive_message import ProactiveMessage
from app.models.trigger_rule import TriggerRule
from app.services.active_log_service import active_log_service
from app.services.proactive_ai_decision_service import proactive_ai_decision_service
from app.services.proactive_cooldown_service import proactive_cooldown_service
from app.services.proactive_message_service import proactive_message_service
from app.services.proactive_safety_service import proactive_safety_service
from app.services.proactive_signal_service import proactive_signal_service
from app.services.proactive_window_service import proactive_window_service
from app.services.trigger_rule_service import trigger_rule_service
from app.ws.manager import realtime_manager


class ProactiveService:
    def execute_rule_for_user(
        self,
        db: Session,
        user_id: int,
        rule_id: int,
    ) -> dict[str, Any]:
        rule = trigger_rule_service.get_or_raise(db, rule_id)
        request_payload = {
            "rule_id": rule.id,
            "trigger_type": rule.trigger_type,
            "condition_json": rule.condition_json,
            "executed_at": now_beijing().isoformat(),
        }
        decision: ProactiveDecision | None = None

        try:
            evaluation = trigger_rule_service.evaluate_for_user(db, user_id, rule)

            if not evaluation["triggered"]:
                log = active_log_service.create_log(
                    db=db,
                    user_id=user_id,
                    trigger_rule_id=rule.id,
                    action_type="generate_proactive_message",
                    status="skipped",
                    request_payload=request_payload,
                    response_payload=evaluation,
                )
                return {
                    "log_id": log.id,
                    "decision_id": None,
                    "rule_id": rule.id,
                    "triggered": False,
                    "message_created": False,
                    "status": "skipped",
                    "reason": evaluation["reason"],
                    "proactive_message": None,
                }

            window = proactive_window_service.get_or_create_for_user(db, user_id)
            today_count = self.count_today_created(db, user_id)
            context_package = proactive_signal_service.build_context_package(
                db=db,
                user_id=user_id,
                trigger_rule=rule,
                evaluation=evaluation,
                window=window,
                already_triggered_today=today_count,
            )

            ai_response_payload: dict[str, Any] = {
                "prompt_version": proactive_ai_decision_service.PROMPT_VERSION,
            }
            try:
                raw_ai_content = proactive_ai_decision_service.request_decision(
                    context_package
                )
                ai_response_payload["raw_content"] = raw_ai_content
                ai_decision = proactive_ai_decision_service.parse_decision(raw_ai_content)
                ai_response_payload["parsed"] = ai_decision
            except Exception as exc:
                error_message = self._exception_message(exc)
                ai_response_payload["error"] = error_message
                decision = self._create_decision(
                    db=db,
                    user_id=user_id,
                    rule=rule,
                    evaluation=evaluation,
                    context_package=context_package,
                    ai_response_json=ai_response_payload,
                    status="failed",
                    blocked_reason=error_message[:200],
                )
                raise

            safety_result = proactive_safety_service.review(
                ai_decision=ai_decision,
                context_package=context_package,
            )

            if not safety_result["allowed"]:
                decision = self._create_decision(
                    db=db,
                    user_id=user_id,
                    rule=rule,
                    evaluation=evaluation,
                    context_package=context_package,
                    ai_response_json=ai_response_payload,
                    status=safety_result["status"],
                    blocked_reason=safety_result["blocked_reason"],
                    safety_result=safety_result,
                )
                log = active_log_service.create_log(
                    db=db,
                    user_id=user_id,
                    trigger_rule_id=rule.id,
                    action_type="generate_proactive_message",
                    status=safety_result["status"],
                    request_payload=request_payload,
                    response_payload=self._build_log_payload(
                        evaluation=evaluation,
                        decision=decision,
                        safety_result=safety_result,
                    ),
                )
                return {
                    "log_id": log.id,
                    "decision_id": decision.id,
                    "rule_id": rule.id,
                    "triggered": True,
                    "message_created": False,
                    "status": safety_result["status"],
                    "reason": safety_result["blocked_reason"],
                    "proactive_message": None,
                }

            allowed, window_reason = proactive_window_service.allow_trigger_now(window)

            if not allowed:
                decision = self._create_decision(
                    db=db,
                    user_id=user_id,
                    rule=rule,
                    evaluation=evaluation,
                    context_package=context_package,
                    ai_response_json=ai_response_payload,
                    status="blocked_by_window",
                    blocked_reason=window_reason,
                    safety_result=safety_result,
                )
                log = active_log_service.create_log(
                    db=db,
                    user_id=user_id,
                    trigger_rule_id=rule.id,
                    action_type="generate_proactive_message",
                    status="blocked_by_window",
                    request_payload=request_payload,
                    response_payload=self._build_log_payload(
                        evaluation=evaluation,
                        decision=decision,
                        safety_result=safety_result,
                        extra={
                            "window_reason": window_reason,
                            "quiet_hours_start": window.quiet_hours_start,
                            "quiet_hours_end": window.quiet_hours_end,
                        },
                    ),
                )
                return {
                    "log_id": log.id,
                    "decision_id": decision.id,
                    "rule_id": rule.id,
                    "triggered": True,
                    "message_created": False,
                    "status": "blocked_by_window",
                    "reason": window_reason,
                    "proactive_message": None,
                }

            if today_count >= window.max_trigger_per_day:
                decision = self._create_decision(
                    db=db,
                    user_id=user_id,
                    rule=rule,
                    evaluation=evaluation,
                    context_package=context_package,
                    ai_response_json=ai_response_payload,
                    status="blocked_by_rate_limit",
                    blocked_reason="max trigger per day exceeded",
                    safety_result=safety_result,
                )
                log = active_log_service.create_log(
                    db=db,
                    user_id=user_id,
                    trigger_rule_id=rule.id,
                    action_type="generate_proactive_message",
                    status="blocked_by_rate_limit",
                    request_payload=request_payload,
                    response_payload=self._build_log_payload(
                        evaluation=evaluation,
                        decision=decision,
                        safety_result=safety_result,
                        extra={
                            "today_count": today_count,
                            "max_trigger_per_day": window.max_trigger_per_day,
                        },
                    ),
                )
                return {
                    "log_id": log.id,
                    "decision_id": decision.id,
                    "rule_id": rule.id,
                    "triggered": True,
                    "message_created": False,
                    "status": "blocked_by_rate_limit",
                    "reason": "max trigger per day exceeded",
                    "proactive_message": None,
                }

            in_cooldown, cooldown_reason = proactive_cooldown_service.is_in_cooldown(
                db=db,
                user_id=user_id,
                trigger_rule_id=rule.id,
                trigger_type=rule.trigger_type,
                cooldown_hours=int(safety_result["cooldown_hours"] or 24),
            )
            if in_cooldown:
                decision = self._create_decision(
                    db=db,
                    user_id=user_id,
                    rule=rule,
                    evaluation=evaluation,
                    context_package=context_package,
                    ai_response_json=ai_response_payload,
                    status="blocked_by_cooldown",
                    blocked_reason=cooldown_reason,
                    safety_result=safety_result,
                )
                log = active_log_service.create_log(
                    db=db,
                    user_id=user_id,
                    trigger_rule_id=rule.id,
                    action_type="generate_proactive_message",
                    status="blocked_by_cooldown",
                    request_payload=request_payload,
                    response_payload=self._build_log_payload(
                        evaluation=evaluation,
                        decision=decision,
                        safety_result=safety_result,
                    ),
                )
                return {
                    "log_id": log.id,
                    "decision_id": decision.id,
                    "rule_id": rule.id,
                    "triggered": True,
                    "message_created": False,
                    "status": "blocked_by_cooldown",
                    "reason": cooldown_reason,
                    "proactive_message": None,
                }

            proactive_message = proactive_message_service.create_message(
                db=db,
                user_id=user_id,
                trigger_rule=rule,
                title=safety_result["title"],
                content=safety_result["message"],
            )

            delivered_connection_count = self._push_created_message(
                user_id=user_id,
                proactive_message=proactive_message,
            )

            decision = self._create_decision(
                db=db,
                user_id=user_id,
                rule=rule,
                evaluation=evaluation,
                context_package=context_package,
                ai_response_json={
                    **ai_response_payload,
                    "proactive_message_id": proactive_message.id,
                },
                status="created",
                blocked_reason=None,
                safety_result=safety_result,
            )
            log = active_log_service.create_log(
                db=db,
                user_id=user_id,
                trigger_rule_id=rule.id,
                action_type="generate_proactive_message",
                status="created",
                request_payload=request_payload,
                response_payload=self._build_log_payload(
                    evaluation=evaluation,
                    decision=decision,
                    safety_result=safety_result,
                    extra={
                        "proactive_message_id": proactive_message.id,
                        "title": proactive_message.title,
                        "status": proactive_message.status,
                        "realtime_delivered_connection_count": delivered_connection_count,
                    },
                ),
            )
            return {
                "log_id": log.id,
                "decision_id": decision.id,
                "rule_id": rule.id,
                "triggered": True,
                "message_created": True,
                "status": "created",
                "reason": safety_result["reason"] or evaluation["reason"],
                "proactive_message": proactive_message,
            }
        except Exception as exc:
            active_log_service.create_log(
                db=db,
                user_id=user_id,
                trigger_rule_id=rule.id,
                action_type="generate_proactive_message",
                status="failed",
                request_payload=request_payload,
                response_payload={
                    "error": self._exception_message(exc),
                    "decision_id": decision.id if decision else None,
                },
            )
            raise

    def count_today_created(
        self,
        db: Session,
        user_id: int,
    ) -> int:
        day_start = now_beijing().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        stmt = (
            select(func.count())
            .select_from(ActiveLog)
            .where(
                ActiveLog.user_id == user_id,
                ActiveLog.action_type == "generate_proactive_message",
                ActiveLog.status == "created",
                ActiveLog.created_at >= day_start,
            )
        )
        return db.scalar(stmt) or 0

    def list_decisions_for_user(
        self,
        db: Session,
        user_id: int,
    ) -> list[ProactiveDecision]:
        stmt = (
            select(ProactiveDecision)
            .where(ProactiveDecision.user_id == user_id)
            .order_by(
                ProactiveDecision.created_at.desc(),
                ProactiveDecision.id.desc(),
            )
        )
        return list(db.scalars(stmt).all())

    def _create_decision(
        self,
        db: Session,
        user_id: int,
        rule: TriggerRule,
        evaluation: dict[str, Any],
        context_package: dict[str, Any],
        ai_response_json: dict[str, Any] | None,
        status: str,
        blocked_reason: str | None,
        safety_result: dict[str, Any] | None = None,
    ) -> ProactiveDecision:
        safety_result = safety_result or {}
        decision = ProactiveDecision(
            user_id=user_id,
            trigger_rule_id=rule.id,
            trigger_type=rule.trigger_type,
            triggered=bool(evaluation.get("triggered")),
            ai_should_remind=safety_result.get("ai_should_remind"),
            severity=safety_result.get("severity"),
            reason=safety_result.get("reason") or evaluation.get("reason"),
            title=safety_result.get("title"),
            message=safety_result.get("message"),
            cooldown_hours=safety_result.get("cooldown_hours"),
            safety_label=safety_result.get("safety_label"),
            status=status,
            blocked_reason=blocked_reason,
            input_snapshot_json=context_package,
            ai_response_json=ai_response_json,
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision

    def _build_log_payload(
        self,
        evaluation: dict[str, Any],
        decision: ProactiveDecision,
        safety_result: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            **evaluation,
            "decision_id": decision.id,
            "decision_status": decision.status,
            "ai_should_remind": decision.ai_should_remind,
            "severity": decision.severity,
            "safety_label": decision.safety_label,
            "blocked_reason": decision.blocked_reason,
            "title": decision.title,
            "cooldown_hours": decision.cooldown_hours,
        }
        if safety_result.get("message"):
            payload["message"] = safety_result["message"]
        if extra:
            payload.update(extra)
        return payload

    def _exception_message(self, exc: Exception) -> str:
        return str(getattr(exc, "message", None) or str(exc) or exc.__class__.__name__)

    def build_message_content(
        self,
        rule: TriggerRule,
        evaluation: dict[str, Any],
    ) -> tuple[str, str]:
        if rule.trigger_type == "days_without_record":
            return self._build_days_without_record_message(evaluation)

        if rule.trigger_type == "recent_chat_keyword":
            return self._build_recent_chat_keyword_message(evaluation)

        return (
            "主动关怀提醒",
            "系统检测到你可能需要一次健康关注，你可以打开应用查看建议。",
        )

    def _build_days_without_record_message(
        self,
        evaluation: dict[str, Any],
    ) -> tuple[str, str]:
        record_type = str(evaluation.get("record_type", "健康数据"))
        days_without_record = int(evaluation.get("days_without_record", 1))
        record_label = self._record_type_label(record_type)

        title = "健康记录提醒"
        content = (
            f"我注意到你已经 {days_without_record} 天没有记录{record_label}了。"
            "如果今天方便，可以补记一条；如果最近状态有波动，也建议尽快测一次。"
        )
        return title, content

    def _build_recent_chat_keyword_message(
        self,
        evaluation: dict[str, Any],
    ) -> tuple[str, str]:
        keywords = evaluation.get("matched_keywords") or []
        keyword_text = "、".join(str(item) for item in keywords) or "当前困扰"

        title = "健康关怀提示"
        content = (
            f"我注意到你最近的表达里出现了“{keyword_text}”相关内容。"
            "如果你愿意，可以继续说说现在最困扰你的点，我会先帮你整理成几个可执行的小建议。"
        )
        return title, content

    def _record_type_label(self, record_type: str) -> str:
        mapping = {
            "blood_pressure": "血压",
            "blood_glucose": "血糖",
            "sleep": "睡眠",
            "medication": "用药",
            "mood": "情绪",
            "checkin": "健康打卡",
        }
        return mapping.get(record_type, record_type)

    def _push_created_message(
        self,
        user_id: int,
        proactive_message: ProactiveMessage,
    ) -> int:
        payload = self.build_created_event_payload(proactive_message)
        return realtime_manager.send_json_to_user_sync(user_id, payload)

    def build_created_event_payload(
        self,
        proactive_message: ProactiveMessage,
    ) -> dict[str, Any]:
        return {
            "event": "proactive_message_created",
            "data": {
                "id": proactive_message.id,
                "user_id": proactive_message.user_id,
                "trigger_rule_id": proactive_message.trigger_rule_id,
                "trigger_type": proactive_message.trigger_type,
                "title": proactive_message.title,
                "content": proactive_message.content,
                "status": proactive_message.status,
                "created_at": proactive_message.created_at.isoformat(),
                "displayed_at": (
                    proactive_message.displayed_at.isoformat()
                    if proactive_message.displayed_at
                    else None
                ),
            },
        }

    def list_pending_created_event_payloads(
        self,
        db: Session,
        user_id: int,
    ) -> list[dict[str, Any]]:
        pending_messages = proactive_message_service.list_pending_for_user(db, user_id)
        return [
            self.build_created_event_payload(message)
            for message in pending_messages
        ]


proactive_service = ProactiveService()
