from __future__ import annotations

from typing import Any


class ProactiveSafetyService:
    MAX_TITLE_LENGTH = 50
    MAX_MESSAGE_LENGTH = 260
    DEFAULT_COOLDOWN_HOURS = 24
    HIGH_RISK_COOLDOWN_HOURS = 6
    HIGH_RISK_TITLE = "及时关注提醒"
    HIGH_RISK_MESSAGE = (
        "你提到的情况可能需要及时关注。"
        "建议尽快联系家人、医生或当地急救服务，避免独自等待。"
    )

    HIGH_RISK_KEYWORDS = [
        "胸痛",
        "胸口痛",
        "呼吸困难",
        "喘不上气",
        "意识异常",
        "意识不清",
        "严重头晕",
        "头晕明显加重",
        "摔倒无法起身",
        "跌倒无法起身",
        "自伤",
        "想死",
        "轻生",
        "自杀",
    ]
    UNSAFE_MEDICAL_PHRASES = [
        "保证",
        "治愈",
        "一定会好",
        "无需就医",
        "不用就医",
        "不用看医生",
        "不用联系医生",
        "替代医生",
        "建议停药",
        "可以停药",
        "直接停药",
        "自行停药",
        "建议加量",
        "可以加量",
        "直接加量",
        "建议减量",
        "可以减量",
        "直接减量",
        "你确诊",
        "已经确诊",
    ]
    VALID_SEVERITIES = {"low", "medium", "high"}

    def review(
        self,
        ai_decision: dict[str, Any],
        context_package: dict[str, Any],
    ) -> dict[str, Any]:
        high_risk = self._contains_high_risk_signal(ai_decision, context_package)
        if high_risk:
            return {
                "allowed": True,
                "status": "created",
                "blocked_reason": None,
                "ai_should_remind": bool(ai_decision.get("should_remind", True)),
                "severity": "high",
                "reason": str(ai_decision.get("reason") or "high risk signal detected"),
                "title": self.HIGH_RISK_TITLE,
                "message": self.HIGH_RISK_MESSAGE,
                "cooldown_hours": self.HIGH_RISK_COOLDOWN_HOURS,
                "safety_label": "high_risk_template",
            }

        should_remind = ai_decision.get("should_remind")
        if not isinstance(should_remind, bool):
            return self._blocked("blocked_by_safety", "invalid should_remind")

        reason = str(ai_decision.get("reason") or "").strip()
        if not should_remind:
            return {
                "allowed": False,
                "status": "blocked_by_ai",
                "blocked_reason": reason or "ai decided not to remind",
                "ai_should_remind": False,
                "severity": self._normalize_severity(ai_decision.get("severity")),
                "reason": reason,
                "title": self._clean_text(ai_decision.get("title")),
                "message": self._clean_text(ai_decision.get("message")),
                "cooldown_hours": self._normalize_cooldown(ai_decision, context_package),
                "safety_label": self._clean_text(ai_decision.get("safety_label")) or "general_health_advice",
            }

        title = self._clean_text(ai_decision.get("title"))
        message = self._clean_text(ai_decision.get("message"))
        if not title or not message:
            return self._blocked("blocked_by_safety", "title or message is empty")
        if len(title) > self.MAX_TITLE_LENGTH:
            return self._blocked("blocked_by_safety", "title is too long")
        if len(message) > self.MAX_MESSAGE_LENGTH:
            return self._blocked("blocked_by_safety", "message is too long")

        unsafe_phrase = self._find_unsafe_phrase(message)
        if unsafe_phrase:
            return self._blocked(
                "blocked_by_safety",
                f"message contains unsafe phrase: {unsafe_phrase}",
            )

        return {
            "allowed": True,
            "status": "created",
            "blocked_reason": None,
            "ai_should_remind": True,
            "severity": self._normalize_severity(ai_decision.get("severity")),
            "reason": reason,
            "title": title,
            "message": message,
            "cooldown_hours": self._normalize_cooldown(ai_decision, context_package),
            "safety_label": self._clean_text(ai_decision.get("safety_label")) or "general_health_advice",
        }

    def _blocked(self, status: str, blocked_reason: str) -> dict[str, Any]:
        return {
            "allowed": False,
            "status": status,
            "blocked_reason": blocked_reason,
            "ai_should_remind": None,
            "severity": None,
            "reason": None,
            "title": None,
            "message": None,
            "cooldown_hours": self.DEFAULT_COOLDOWN_HOURS,
            "safety_label": "blocked",
        }

    def _contains_high_risk_signal(
        self,
        ai_decision: dict[str, Any],
        context_package: dict[str, Any],
    ) -> bool:
        trigger = context_package.get("trigger") or {}
        recent_records = context_package.get("recent_records") or []
        recent_user_messages = context_package.get("recent_user_messages") or []
        pieces = [
            str(trigger.get("reason") or ""),
            str(trigger.get("evaluation") or ""),
            str(ai_decision.get("reason") or ""),
            str(ai_decision.get("message") or ""),
            " ".join(str(item) for item in recent_user_messages),
            " ".join(str(item) for item in recent_records),
        ]
        combined = " ".join(pieces).lower()
        return any(keyword.lower() in combined for keyword in self.HIGH_RISK_KEYWORDS)

    def _find_unsafe_phrase(self, message: str) -> str | None:
        lowered = message.lower()
        for phrase in self.UNSAFE_MEDICAL_PHRASES:
            if phrase.lower() in lowered:
                return phrase
        return None

    def _normalize_severity(self, value: object) -> str:
        severity = str(value or "medium").strip().lower()
        if severity not in self.VALID_SEVERITIES:
            return "medium"
        return severity

    def _normalize_cooldown(
        self,
        ai_decision: dict[str, Any],
        context_package: dict[str, Any],
    ) -> int:
        trigger = context_package.get("trigger") or {}
        trigger_type = str(trigger.get("trigger_type") or "")
        default = self.DEFAULT_COOLDOWN_HOURS
        if trigger_type == "medication_time_reminder":
            default = 24

        try:
            cooldown_hours = int(ai_decision.get("cooldown_hours", default))
        except (TypeError, ValueError):
            cooldown_hours = default

        return min(max(cooldown_hours, 1), 168)

    def _clean_text(self, value: object) -> str:
        return str(value or "").strip()


proactive_safety_service = ProactiveSafetyService()
