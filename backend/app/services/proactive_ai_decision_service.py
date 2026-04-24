from __future__ import annotations

import json
from typing import Any

from app.core.exception import BusinessException
from app.services.llm_service import llm_service


class ProactiveAIDecisionService:
    PROMPT_VERSION = "phase15.proactive_decision.v1"

    SYSTEM_PROMPT = """你是“智语康伴”的主动关心决策器。

你只负责根据结构化用户近况判断本次是否值得提醒，并生成一条温和、安全、简短的中文提醒。

要求：
1. 只输出一个合法 JSON 对象，不要输出 Markdown、解释、代码块或多余文本。
2. 不做诊断，不承诺疗效，不替代医生，不指导用户自行停药、换药或改剂量。
3. 如信息不足但规则命中，可以选择 should_remind=false，并说明原因。
4. 如需要提醒，message 要自然、温和，默认 120 字以内。
5. 高风险线索只给及时联系家人、医生或急救服务的安全建议。

JSON 字段必须包含：
{
  "should_remind": true,
  "severity": "low|medium|high",
  "reason": "为什么提醒或不提醒",
  "title": "提醒标题",
  "message": "最终给用户看的提醒文案",
  "cooldown_hours": 24,
  "safety_label": "general_health_advice"
}"""

    def request_decision(self, context_package: dict[str, Any]) -> str:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(context_package, ensure_ascii=False),
            },
        ]
        return llm_service.chat(messages)

    def parse_decision(self, raw_content: str) -> dict[str, Any]:
        text = raw_content.strip()
        json_text = self._extract_json_object(text)

        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise BusinessException(
                code=50251,
                message="llm proactive decision is not valid JSON",
                status_code=502,
            ) from exc

        if not isinstance(payload, dict):
            raise BusinessException(
                code=50252,
                message="llm proactive decision must be a JSON object",
                status_code=502,
            )

        return payload

    def decide(
        self,
        context_package: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raw_content = self.request_decision(context_package)
        parsed = self.parse_decision(raw_content)
        return parsed, {
            "prompt_version": self.PROMPT_VERSION,
            "raw_content": raw_content,
            "parsed": parsed,
        }

    def _extract_json_object(self, text: str) -> str:
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return text
        return text[start : end + 1]


proactive_ai_decision_service = ProactiveAIDecisionService()
