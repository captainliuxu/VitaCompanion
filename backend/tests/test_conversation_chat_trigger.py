from __future__ import annotations

from app.services.llm_service import llm_service
from tests.conftest import assert_beijing_datetime


def test_conversation_chat_trigger_and_permissions(client, create_user, monkeypatch):
    owner = create_user("conversation_owner")
    other = create_user("conversation_other")

    conversation_response = client.post(
        "/api/v1/conversations",
        headers=owner["headers"],
        json={"title": "健康咨询"},
    )
    assert conversation_response.status_code == 201, conversation_response.text
    conversation = conversation_response.json()["data"]
    conversation_id = conversation["id"]
    assert_beijing_datetime(conversation["created_at"])
    assert_beijing_datetime(conversation["updated_at"])

    other_detail_response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=other["headers"],
    )
    assert other_detail_response.status_code == 404, other_detail_response.text
    assert other_detail_response.json()["code"] == 40431

    monkeypatch.setattr(
        llm_service,
        "chat",
        lambda messages: "先别着急，我在这里陪你，我们可以一步一步来。",
    )

    chat_response = client.post(
        "/api/v1/chat/send",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "我最近有点焦虑，晚上睡不好。",
        },
    )
    assert chat_response.status_code == 200, chat_response.text
    chat_data = chat_response.json()["data"]
    assert chat_data["reply"] == "先别着急，我在这里陪你，我们可以一步一步来。"
    assert chat_data["assistant_status"] == "completed"
    assert chat_data["prompt_version"] == "phase11.v1"
    assert_beijing_datetime(chat_data["replied_at"])

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=owner["headers"],
    )
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()["data"]["items"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["status"] == "completed"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["status"] == "completed"
    assert messages[1]["reply_to_message_id"] == messages[0]["id"]
    assert_beijing_datetime(messages[0]["created_at"])
    assert_beijing_datetime(messages[1]["created_at"])

    forbidden_messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=other["headers"],
    )
    assert forbidden_messages_response.status_code == 404, forbidden_messages_response.text
    assert forbidden_messages_response.json()["code"] == 40431

    rule_response = client.post(
        "/api/v1/trigger-rules",
        headers=owner["headers"],
        json={
            "name": "焦虑关键词检测",
            "trigger_type": "recent_chat_keyword",
            "enabled": True,
            "condition_json": {"keywords": ["焦虑"], "recent_limit": 10},
            "priority": 10,
        },
    )
    assert rule_response.status_code == 201, rule_response.text
    rule = rule_response.json()["data"]
    rule_id = rule["id"]
    assert_beijing_datetime(rule["created_at"])
    assert_beijing_datetime(rule["updated_at"])

    check_response = client.post(
        f"/api/v1/trigger-rules/{rule_id}/check/me",
        headers=owner["headers"],
    )
    assert check_response.status_code == 200, check_response.text
    check_data = check_response.json()["data"]
    assert check_data["triggered"] is True
    assert "焦虑" in check_data["reason"]
    assert_beijing_datetime(check_data["created_at"])

    active_logs_response = client.get(
        "/api/v1/active-logs",
        headers=owner["headers"],
    )
    assert active_logs_response.status_code == 200, active_logs_response.text
    active_logs = active_logs_response.json()["data"]["items"]
    assert len(active_logs) == 1
    assert active_logs[0]["status"] == "triggered"
    assert_beijing_datetime(active_logs[0]["created_at"])
