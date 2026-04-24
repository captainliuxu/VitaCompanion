from __future__ import annotations

import json

from app.services.proactive_ai_decision_service import proactive_ai_decision_service
from app.services import proactive_service as proactive_service_module
from tests.conftest import assert_beijing_datetime


def _create_rule(client, headers, trigger_type: str, condition_json: dict, priority: int = 10) -> int:
    response = client.post(
        "/api/v1/trigger-rules",
        headers=headers,
        json={
            "name": f"test-{trigger_type}",
            "trigger_type": trigger_type,
            "enabled": True,
            "condition_json": condition_json,
            "priority": priority,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _allow_proactive_window(monkeypatch):
    monkeypatch.setattr(
        proactive_service_module.proactive_window_service,
        "allow_trigger_now",
        lambda window: (True, "allowed"),
    )


def test_blood_pressure_rule_uses_ai_decision_and_records_context(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("proactive_bp")
    _allow_proactive_window(monkeypatch)

    record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "blood_pressure",
            "value": "148/92",
            "unit": "mmHg",
        },
    )
    assert record_response.status_code == 201, record_response.text

    rule_id = _create_rule(
        client,
        owner["headers"],
        "blood_pressure_threshold",
        {"systolic_gte": 140, "diastolic_gte": 90, "lookback_hours": 24},
    )

    captured_contexts: list[dict] = []

    def fake_request(context_package):
        captured_contexts.append(context_package)
        return json.dumps(
            {
                "should_remind": True,
                "severity": "medium",
                "reason": "血压偏高，适合温和提醒复测。",
                "title": "血压记录提醒",
                "message": "我注意到你最近一次血压偏高。如果方便，建议今晚再测一次并记录；如果不舒服明显加重，请及时联系家人或医生。",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(proactive_ai_decision_service, "request_decision", fake_request)

    execute_response = client.post(
        f"/api/v1/proactive/rules/{rule_id}/execute",
        headers=owner["headers"],
    )
    assert execute_response.status_code == 200, execute_response.text
    execute_data = execute_response.json()["data"]
    assert execute_data["triggered"] is True
    assert execute_data["message_created"] is True
    assert execute_data["status"] == "created"
    assert execute_data["decision_id"] is not None
    assert execute_data["proactive_message"]["title"] == "血压记录提醒"
    assert "血压偏高" in execute_data["proactive_message"]["content"]

    assert captured_contexts[0]["trigger"]["trigger_type"] == "blood_pressure_threshold"
    assert captured_contexts[0]["recent_records"][0]["record_type"] == "blood_pressure"

    decisions_response = client.get(
        "/api/v1/proactive/decisions",
        headers=owner["headers"],
    )
    assert decisions_response.status_code == 200, decisions_response.text
    decision = decisions_response.json()["data"]["items"][0]
    assert decision["status"] == "created"
    assert decision["ai_should_remind"] is True
    assert decision["severity"] == "medium"
    assert decision["safety_label"] == "general_health_advice"
    assert_beijing_datetime(decision["created_at"])


def test_ai_can_block_sleep_reminder_without_creating_message(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("proactive_sleep")
    _allow_proactive_window(monkeypatch)

    record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "sleep",
            "value": "4.5",
            "unit": "hour",
        },
    )
    assert record_response.status_code == 201, record_response.text

    rule_id = _create_rule(
        client,
        owner["headers"],
        "sleep_duration_low",
        {"hours_lt": 5, "lookback_days": 1},
    )

    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": False,
                "severity": "low",
                "reason": "只有一次睡眠偏少，暂时不打扰。",
                "title": "",
                "message": "",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )

    execute_response = client.post(
        f"/api/v1/proactive/rules/{rule_id}/execute",
        headers=owner["headers"],
    )
    assert execute_response.status_code == 200, execute_response.text
    execute_data = execute_response.json()["data"]
    assert execute_data["status"] == "blocked_by_ai"
    assert execute_data["message_created"] is False
    assert execute_data["proactive_message"] is None

    messages_response = client.get("/api/v1/proactive/messages", headers=owner["headers"])
    assert messages_response.status_code == 200, messages_response.text
    assert messages_response.json()["data"]["items"] == []


def test_same_rule_is_blocked_by_cooldown_after_created_decision(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("proactive_cooldown")
    _allow_proactive_window(monkeypatch)

    window_response = client.put(
        "/api/v1/proactive/window",
        headers=owner["headers"],
        json={
            "enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "max_trigger_per_day": 5,
        },
    )
    assert window_response.status_code == 200, window_response.text

    record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "blood_pressure",
            "value": "150/95",
            "unit": "mmHg",
        },
    )
    assert record_response.status_code == 201, record_response.text

    rule_id = _create_rule(
        client,
        owner["headers"],
        "blood_pressure_threshold",
        {"systolic_gte": 140, "diastolic_gte": 90, "lookback_hours": 24},
    )

    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": True,
                "severity": "medium",
                "reason": "血压偏高。",
                "title": "血压提醒",
                "message": "我注意到你最近血压偏高，建议方便时复测并记录。",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )

    first_response = client.post(
        f"/api/v1/proactive/rules/{rule_id}/execute",
        headers=owner["headers"],
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["data"]["status"] == "created"

    second_response = client.post(
        f"/api/v1/proactive/rules/{rule_id}/execute",
        headers=owner["headers"],
    )
    assert second_response.status_code == 200, second_response.text
    second_data = second_response.json()["data"]
    assert second_data["status"] == "blocked_by_cooldown"
    assert second_data["message_created"] is False


def test_high_risk_signal_uses_backend_safety_template(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("proactive_high_risk")
    _allow_proactive_window(monkeypatch)

    conversation_response = client.post(
        "/api/v1/conversations",
        headers=owner["headers"],
        json={"title": "高风险线索"},
    )
    assert conversation_response.status_code == 201, conversation_response.text
    conversation_id = conversation_response.json()["data"]["id"]

    message_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/debug",
        headers=owner["headers"],
        json={"role": "user", "content": "我现在胸痛，还有点呼吸困难。"},
    )
    assert message_response.status_code == 201, message_response.text

    rule_id = _create_rule(
        client,
        owner["headers"],
        "recent_chat_keyword",
        {"keywords": ["胸痛"], "recent_limit": 10},
    )

    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": True,
                "severity": "medium",
                "reason": "用户提到胸痛。",
                "title": "普通提醒",
                "message": "建议你先休息一下。",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )

    execute_response = client.post(
        f"/api/v1/proactive/rules/{rule_id}/execute",
        headers=owner["headers"],
    )
    assert execute_response.status_code == 200, execute_response.text
    message = execute_response.json()["data"]["proactive_message"]
    assert message["title"] == "及时关注提醒"
    assert "当地急救服务" in message["content"]

    decisions_response = client.get(
        "/api/v1/proactive/decisions",
        headers=owner["headers"],
    )
    assert decisions_response.status_code == 200, decisions_response.text
    decision = decisions_response.json()["data"]["items"][0]
    assert decision["severity"] == "high"
    assert decision["safety_label"] == "high_risk_template"


def test_invalid_ai_json_records_failed_decision(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("proactive_invalid_json")
    _allow_proactive_window(monkeypatch)

    record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "blood_pressure",
            "value": "145/91",
            "unit": "mmHg",
        },
    )
    assert record_response.status_code == 201, record_response.text

    rule_id = _create_rule(
        client,
        owner["headers"],
        "blood_pressure_threshold",
        {"systolic_gte": 140, "diastolic_gte": 90, "lookback_hours": 24},
    )

    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: "这不是 JSON",
    )

    execute_response = client.post(
        f"/api/v1/proactive/rules/{rule_id}/execute",
        headers=owner["headers"],
    )
    assert execute_response.status_code == 502, execute_response.text

    decisions_response = client.get(
        "/api/v1/proactive/decisions",
        headers=owner["headers"],
    )
    assert decisions_response.status_code == 200, decisions_response.text
    decision = decisions_response.json()["data"]["items"][0]
    assert decision["status"] == "failed"
    assert decision["blocked_reason"] == "llm proactive decision is not valid JSON"
    assert decision["ai_response_json"]["raw_content"] == "这不是 JSON"
