from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from app.core.config import BASE_DIR, settings
from app.db.session import SessionLocal
from app.services import proactive_service as proactive_service_module
from app.services.llm_service import llm_service
from app.services.message_service import message_service
from app.services.proactive_ai_decision_service import proactive_ai_decision_service
from tests.conftest import assert_beijing_datetime


def _create_conversation(client, headers, title: str) -> int:
    response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_rule(
    client,
    headers,
    trigger_type: str,
    condition_json: dict,
    priority: int = 10,
) -> int:
    response = client.post(
        "/api/v1/trigger-rules",
        headers=headers,
        json={
            "name": f"acceptance-{trigger_type}-{uuid.uuid4().hex[:6]}",
            "trigger_type": trigger_type,
            "enabled": True,
            "condition_json": condition_json,
            "priority": priority,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _collect_sse_events(response) -> list[dict]:
    events: list[dict] = []
    for line in response.iter_lines():
        if not line:
            continue

        text = line.decode("utf-8") if isinstance(line, bytes) else line
        if not text.startswith("data:"):
            continue

        payload_text = text[len("data:") :].strip()
        if not payload_text:
            continue

        events.append(json.loads(payload_text))
    return events


def _make_storage_dir(prefix: str) -> Path:
    directory = BASE_DIR / "storage" / f"{prefix}_{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _allow_proactive_window(monkeypatch):
    monkeypatch.setattr(
        proactive_service_module.proactive_window_service,
        "allow_trigger_now",
        lambda window: (True, "allowed"),
    )


def test_acceptance_core_flow_covers_auth_profile_record_chat_rag_summary_and_memory(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("acceptance_core")

    me_response = client.get("/api/v1/users/me", headers=owner["headers"])
    assert me_response.status_code == 200, me_response.text
    me_data = me_response.json()["data"]
    assert me_data["username"] == owner["username"]
    assert_beijing_datetime(me_data["created_at"])
    assert_beijing_datetime(me_data["updated_at"])

    profile_create_response = client.post(
        "/api/v1/profiles/me",
        headers=owner["headers"],
        json={
            "name": "验收用户",
            "age": 62,
            "gender": "female",
            "height": 163.0,
            "weight": 57.5,
            "chronic_history": "高血压",
            "remark": "验收档案",
        },
    )
    assert profile_create_response.status_code == 201, profile_create_response.text
    profile = profile_create_response.json()["data"]
    assert profile["name"] == "验收用户"
    assert_beijing_datetime(profile["created_at"])

    profile_update_response = client.put(
        "/api/v1/profiles/me",
        headers=owner["headers"],
        json={"weight": 56.8, "remark": "验收档案已更新"},
    )
    assert profile_update_response.status_code == 200, profile_update_response.text
    assert profile_update_response.json()["data"]["weight"] == 56.8

    bp_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "blood_pressure",
            "value": "126/82",
            "unit": "mmHg",
            "record_time": "2026-04-20T08:00:00+08:00",
            "note": "晨起测量",
        },
    )
    assert bp_record_response.status_code == 201, bp_record_response.text
    bp_record = bp_record_response.json()["data"]

    sleep_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "sleep",
            "value": "5.5",
            "unit": "hour",
            "record_time": "2026-04-21T07:00:00+08:00",
            "note": "入睡偏晚",
        },
    )
    assert sleep_record_response.status_code == 201, sleep_record_response.text
    sleep_record = sleep_record_response.json()["data"]

    filter_response = client.get(
        "/api/v1/records",
        headers=owner["headers"],
        params={
            "record_type": "blood_pressure",
            "start_time": "2026-04-20T00:00:00+08:00",
            "end_time": "2026-04-20T23:59:59+08:00",
        },
    )
    assert filter_response.status_code == 200, filter_response.text
    filtered = filter_response.json()["data"]
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == bp_record["id"]

    update_record_response = client.put(
        f"/api/v1/records/{bp_record['id']}",
        headers=owner["headers"],
        json={"value": "124/80", "note": "复测回落"},
    )
    assert update_record_response.status_code == 200, update_record_response.text
    assert update_record_response.json()["data"]["value"] == "124/80"

    delete_record_response = client.delete(
        f"/api/v1/records/{sleep_record['id']}",
        headers=owner["headers"],
    )
    assert delete_record_response.status_code == 200, delete_record_response.text

    conversation_id = _create_conversation(client, owner["headers"], "验收普通聊天")

    chat_replies = iter(
        [
            "先从今晚固定一个上床时间开始。",
            "可以把睡前一小时留给放松活动。",
        ]
    )
    monkeypatch.setattr(llm_service, "chat", lambda messages: next(chat_replies))

    plain_chat_response = client.post(
        "/api/v1/chat/send",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "最近睡得浅，想先试试简单调整。",
            "mode": "plain",
        },
    )
    assert plain_chat_response.status_code == 200, plain_chat_response.text
    plain_chat = plain_chat_response.json()["data"]
    assert plain_chat["assistant_status"] == "completed"
    assert plain_chat["reply"] == "先从今晚固定一个上床时间开始。"
    assert plain_chat["citations"] == []
    assert_beijing_datetime(plain_chat["replied_at"])

    monkeypatch.setattr(
        llm_service,
        "stream_chat",
        lambda messages: iter(["流式", "回复", "完成"]),
    )
    with client.stream(
        "POST",
        "/api/v1/chat/send-stream",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "再给我一个更短的建议。",
            "mode": "plain",
        },
    ) as stream_response:
        assert stream_response.status_code == 200, stream_response.text
        stream_events = _collect_sse_events(stream_response)

    assert stream_events[0]["event"] == "start"
    assert stream_events[-1]["event"] == "finish"
    assert stream_events[-1]["assistant_status"] == "completed"
    assert stream_events[-1]["reply"] == "流式回复完成"

    with SessionLocal() as db:
        user_message = message_service.create_for_conversation(
            db=db,
            user_id=owner["user"]["id"],
            conversation_id=conversation_id,
            role="user",
            content="请继续",
            status="completed",
        )
        assistant_draft = message_service.create_assistant_draft(
            db=db,
            user_id=owner["user"]["id"],
            conversation_id=conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version="phase15.acceptance",
        )
        draft_id = assistant_draft.id

    cancel_response = client.post(
        f"/api/v1/chat/messages/{draft_id}/cancel",
        headers=owner["headers"],
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["data"]["assistant_status"] == "cancelled"

    regenerate_response = client.post(
        f"/api/v1/chat/messages/{plain_chat['assistant_message_id']}/regenerate",
        headers=owner["headers"],
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerate_data = regenerate_response.json()["data"]
    assert regenerate_data["assistant_status"] == "completed"
    assert regenerate_data["reply"] == "可以把睡前一小时留给放松活动。"

    source_dir = _make_storage_dir("acceptance_kb")
    try:
        (source_dir / "sleep.md").write_text(
            "# 睡眠建议\n固定作息、晚间减少浓茶咖啡，必要时记录睡眠时长。",
            encoding="utf-8",
        )

        kb_create_response = client.post(
            "/api/v1/knowledge-bases",
            headers=owner["headers"],
            json={"name": "验收知识库", "description": "用于 RAG 验收"},
        )
        assert kb_create_response.status_code == 201, kb_create_response.text
        knowledge_base_id = kb_create_response.json()["data"]["id"]

        import_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/import-local",
            headers=owner["headers"],
            json={
                "source_path": str(source_dir),
                "recursive": False,
                "chunk_size": 200,
                "chunk_overlap": 20,
            },
        )
        assert import_response.status_code == 200, import_response.text
        imported = import_response.json()["data"]
        assert imported["imported_count"] == 1
        assert imported["documents"][0]["status"] == "completed"
        document_id = imported["documents"][0]["id"]

        chunks_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/chunks",
            headers=owner["headers"],
        )
        assert chunks_response.status_code == 200, chunks_response.text
        chunks = chunks_response.json()["data"]["items"]
        assert len(chunks) >= 1
        assert "固定作息" in chunks[0]["content"]

        retrieve_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/retrieve",
            headers=owner["headers"],
            json={"query": "睡前应该注意什么", "top_k": 2},
        )
        assert retrieve_response.status_code == 200, retrieve_response.text
        retrieved_items = retrieve_response.json()["data"]["items"]
        assert retrieved_items
        assert retrieved_items[0]["file_name"] == "sleep.md"

        rag_debug_response = client.post(
            "/api/v1/rag/retrieve-debug",
            headers=owner["headers"],
            json={
                "knowledge_base_id": knowledge_base_id,
                "query": "如何改善睡眠",
                "top_k": 2,
            },
        )
        assert rag_debug_response.status_code == 200, rag_debug_response.text
        rag_debug_items = rag_debug_response.json()["data"]["items"]
        assert rag_debug_items
        assert rag_debug_items[0]["source_index"] == 1

        monkeypatch.setattr(
            llm_service,
            "chat",
            lambda messages: "可以先固定作息并减少晚间刺激饮品。[1]",
        )
        rag_chat_response = client.post(
            "/api/v1/chat/send",
            headers=owner["headers"],
            json={
                "conversation_id": conversation_id,
                "content": "结合知识库给我一个睡眠建议。",
                "knowledge_base_id": knowledge_base_id,
                "top_k": 2,
            },
        )
        assert rag_chat_response.status_code == 200, rag_chat_response.text
        rag_chat = rag_chat_response.json()["data"]
        assert rag_chat["assistant_status"] == "completed"
        assert rag_chat["reply"].endswith("[1]")
        assert rag_chat["citations"]
        assert rag_chat["citations"][0]["file_name"] == "sleep.md"
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)

    monkeypatch.setattr(
        llm_service,
        "chat",
        lambda messages: "- 用户最近睡眠偏浅\n- 建议固定上床时间并减少晚间刺激饮品",
    )
    summary_generate_response = client.post(
        f"/api/v1/conversations/{conversation_id}/summary/generate",
        headers=owner["headers"],
        json={"max_messages": 20},
    )
    assert summary_generate_response.status_code == 200, summary_generate_response.text
    summary = summary_generate_response.json()["data"]
    assert summary["summary"].startswith("- 用户最近睡眠偏浅")

    summary_read_response = client.get(
        f"/api/v1/conversations/{conversation_id}/summary",
        headers=owner["headers"],
    )
    assert summary_read_response.status_code == 200, summary_read_response.text
    assert summary_read_response.json()["data"]["id"] == summary["id"]

    memory_create_response = client.post(
        "/api/v1/user-memories",
        headers=owner["headers"],
        json={
            "content": "用户希望晚间十点半前入睡。",
            "memory_type": "routine",
            "source": "manual",
            "importance": 5,
        },
    )
    assert memory_create_response.status_code == 201, memory_create_response.text

    memory_conversation_id = _create_conversation(client, owner["headers"], "验收长期记忆")
    captured_contexts: list[list[dict[str, str]]] = []

    def fake_chat_with_memory(messages):
        captured_contexts.append(messages)
        return "记得沿用你想在十点半前入睡的目标，今晚先把睡前节奏慢下来。"

    monkeypatch.setattr(llm_service, "chat", fake_chat_with_memory)
    memory_chat_response = client.post(
        "/api/v1/chat/send",
        headers=owner["headers"],
        json={
            "conversation_id": memory_conversation_id,
            "content": "今晚我应该怎么安排作息？",
            "mode": "plain",
        },
    )
    assert memory_chat_response.status_code == 200, memory_chat_response.text
    memory_context = "\n".join(item["content"] for item in captured_contexts[0])
    assert "长期记忆" in memory_context
    assert "十点半前入睡" in memory_context


def test_acceptance_proactive_rules_decisions_and_logs_cover_window_limits_and_safety(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("acceptance_proactive")

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
    window = window_response.json()["data"]
    assert window["quiet_hours_start"] == "22:00"
    assert window["max_trigger_per_day"] == 5
    assert_beijing_datetime(window["updated_at"])

    conversation_id = _create_conversation(client, owner["headers"], "验收规则命中")
    debug_message_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/debug",
        headers=owner["headers"],
        json={"role": "user", "content": "这两天有点焦虑，睡得也不好。"},
    )
    assert debug_message_response.status_code == 201, debug_message_response.text

    keyword_rule_id = _create_rule(
        client,
        owner["headers"],
        "recent_chat_keyword",
        {"keywords": ["焦虑"], "recent_limit": 10},
    )

    check_response = client.post(
        f"/api/v1/trigger-rules/{keyword_rule_id}/check/me",
        headers=owner["headers"],
    )
    assert check_response.status_code == 200, check_response.text
    check_data = check_response.json()["data"]
    assert check_data["triggered"] is True
    assert "焦虑" in check_data["reason"]

    bp_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={
            "record_type": "blood_pressure",
            "value": "148/92",
            "unit": "mmHg",
        },
    )
    assert bp_record_response.status_code == 201, bp_record_response.text

    bp_rule_id = _create_rule(
        client,
        owner["headers"],
        "blood_pressure_threshold",
        {"systolic_gte": 140, "diastolic_gte": 90, "lookback_hours": 24},
    )

    _allow_proactive_window(monkeypatch)
    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": True,
                "severity": "medium",
                "reason": "血压偏高，建议今晚复测。",
                "title": "血压提醒",
                "message": "我注意到你最近一次血压偏高，方便时建议今晚复测并记录。",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )
    execute_response = client.post(
        f"/api/v1/proactive/rules/{bp_rule_id}/execute",
        headers=owner["headers"],
    )
    assert execute_response.status_code == 200, execute_response.text
    execute_data = execute_response.json()["data"]
    assert execute_data["triggered"] is True
    assert execute_data["message_created"] is True
    assert execute_data["status"] == "created"
    assert execute_data["proactive_message"]["title"] == "血压提醒"

    decisions_response = client.get(
        "/api/v1/proactive/decisions",
        headers=owner["headers"],
    )
    assert decisions_response.status_code == 200, decisions_response.text
    created_decision = decisions_response.json()["data"]["items"][0]
    assert created_decision["ai_should_remind"] is True
    assert created_decision["reason"] == "血压偏高，建议今晚复测。"
    assert created_decision["severity"] == "medium"
    assert created_decision["safety_label"] == "general_health_advice"
    assert created_decision["status"] == "created"

    sleep_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={"record_type": "sleep", "value": "4.5", "unit": "hour"},
    )
    assert sleep_record_response.status_code == 201, sleep_record_response.text

    sleep_rule_id = _create_rule(
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
                "reason": "只有一次睡眠不足，暂时不提醒。",
                "title": "",
                "message": "",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )
    block_by_ai_response = client.post(
        f"/api/v1/proactive/rules/{sleep_rule_id}/execute",
        headers=owner["headers"],
    )
    assert block_by_ai_response.status_code == 200, block_by_ai_response.text
    block_by_ai_data = block_by_ai_response.json()["data"]
    assert block_by_ai_data["status"] == "blocked_by_ai"
    assert block_by_ai_data["message_created"] is False
    assert block_by_ai_data["proactive_message"] is None

    quiet_rule_id = _create_rule(
        client,
        owner["headers"],
        "mood_consecutive_low",
        {"consecutive_count": 1, "lookback_days": 1, "low_keywords": ["低落"]},
    )
    mood_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={"record_type": "mood", "value": "低落", "unit": "label"},
    )
    assert mood_record_response.status_code == 201, mood_record_response.text
    monkeypatch.setattr(
        proactive_service_module.proactive_window_service,
        "allow_trigger_now",
        lambda window: (False, "current time is inside quiet hours"),
    )
    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": True,
                "severity": "low",
                "reason": "情绪连续偏低。",
                "title": "情绪提醒",
                "message": "今晚如果方便，可以先做一次简单放松。",
                "cooldown_hours": 12,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )
    quiet_response = client.post(
        f"/api/v1/proactive/rules/{quiet_rule_id}/execute",
        headers=owner["headers"],
    )
    assert quiet_response.status_code == 200, quiet_response.text
    assert quiet_response.json()["data"]["status"] == "blocked_by_window"

    rate_window_response = client.put(
        "/api/v1/proactive/window",
        headers=owner["headers"],
        json={
            "enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "max_trigger_per_day": 1,
        },
    )
    assert rate_window_response.status_code == 200, rate_window_response.text
    _allow_proactive_window(monkeypatch)
    rate_limit_response = client.post(
        f"/api/v1/proactive/rules/{keyword_rule_id}/execute",
        headers=owner["headers"],
    )
    assert rate_limit_response.status_code == 200, rate_limit_response.text
    assert rate_limit_response.json()["data"]["status"] == "blocked_by_rate_limit"

    cooldown_window_response = client.put(
        "/api/v1/proactive/window",
        headers=owner["headers"],
        json={
            "enabled": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "max_trigger_per_day": 5,
        },
    )
    assert cooldown_window_response.status_code == 200, cooldown_window_response.text
    _allow_proactive_window(monkeypatch)
    glucose_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={"record_type": "blood_glucose", "value": "8.8", "unit": "mmol/L"},
    )
    assert glucose_record_response.status_code == 201, glucose_record_response.text
    cooldown_rule_id = _create_rule(
        client,
        owner["headers"],
        "blood_glucose_consecutive_high",
        {"glucose_gte": 7.0, "consecutive_count": 1, "lookback_days": 1},
    )
    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": True,
                "severity": "medium",
                "reason": "血糖偏高，建议继续观察。",
                "title": "血糖提醒",
                "message": "我注意到你最近血糖偏高，建议按计划复测并记录。",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )
    first_cooldown_response = client.post(
        f"/api/v1/proactive/rules/{cooldown_rule_id}/execute",
        headers=owner["headers"],
    )
    assert first_cooldown_response.status_code == 200, first_cooldown_response.text
    assert first_cooldown_response.json()["data"]["status"] == "created"

    second_cooldown_response = client.post(
        f"/api/v1/proactive/rules/{cooldown_rule_id}/execute",
        headers=owner["headers"],
    )
    assert second_cooldown_response.status_code == 200, second_cooldown_response.text
    assert second_cooldown_response.json()["data"]["status"] == "blocked_by_cooldown"

    high_risk_conversation_id = _create_conversation(client, owner["headers"], "验收高风险")
    high_risk_message_response = client.post(
        f"/api/v1/conversations/{high_risk_conversation_id}/messages/debug",
        headers=owner["headers"],
        json={"role": "user", "content": "我现在胸痛，还觉得呼吸困难。"},
    )
    assert high_risk_message_response.status_code == 201, high_risk_message_response.text
    high_risk_rule_id = _create_rule(
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
                "message": "先休息一下。",
                "cooldown_hours": 12,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )
    high_risk_response = client.post(
        f"/api/v1/proactive/rules/{high_risk_rule_id}/execute",
        headers=owner["headers"],
    )
    assert high_risk_response.status_code == 200, high_risk_response.text
    high_risk_message = high_risk_response.json()["data"]["proactive_message"]
    assert high_risk_message["title"] == "及时关注提醒"
    assert "当地急救服务" in high_risk_message["content"]

    skipped_rule_id = _create_rule(
        client,
        owner["headers"],
        "days_without_record",
        {"record_type": "blood_pressure", "days_without_record": 30},
    )
    skipped_response = client.post(
        f"/api/v1/proactive/rules/{skipped_rule_id}/execute",
        headers=owner["headers"],
    )
    assert skipped_response.status_code == 200, skipped_response.text
    assert skipped_response.json()["data"]["status"] == "skipped"

    invalid_json_rule_id = _create_rule(
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
    failed_response = client.post(
        f"/api/v1/proactive/rules/{invalid_json_rule_id}/execute",
        headers=owner["headers"],
    )
    assert failed_response.status_code == 502, failed_response.text

    active_logs_response = client.get(
        "/api/v1/active-logs",
        headers=owner["headers"],
    )
    assert active_logs_response.status_code == 200, active_logs_response.text
    logs = active_logs_response.json()["data"]["items"]
    proactive_logs = [item for item in logs if item["action_type"] == "generate_proactive_message"]
    log_by_status = {item["status"]: item for item in proactive_logs}
    assert "created" in log_by_status
    assert "skipped" in log_by_status
    assert "blocked_by_window" in log_by_status
    assert "blocked_by_rate_limit" in log_by_status
    assert "blocked_by_cooldown" in log_by_status
    assert "failed" in log_by_status
    assert log_by_status["skipped"]["response_payload"]["reason"]
    assert log_by_status["blocked_by_window"]["response_payload"]["blocked_reason"]
    assert log_by_status["blocked_by_rate_limit"]["response_payload"]["blocked_reason"] == "max trigger per day exceeded"
    assert log_by_status["blocked_by_cooldown"]["response_payload"]["blocked_reason"]
    assert log_by_status["failed"]["response_payload"]["error"]

    detail_response = client.get(
        f"/api/v1/active-logs/{log_by_status['failed']['id']}",
        headers=owner["headers"],
    )
    assert detail_response.status_code == 200, detail_response.text
    assert "not valid JSON" in detail_response.json()["data"]["response_payload"]["error"]


def test_acceptance_realtime_replay_and_health_checks(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("acceptance_realtime")
    token = owner["headers"]["Authorization"].split()[1]

    monkeypatch.setattr(settings, "WS_ENABLED", True)
    _allow_proactive_window(monkeypatch)
    monkeypatch.setattr(
        proactive_ai_decision_service,
        "request_decision",
        lambda context_package: json.dumps(
            {
                "should_remind": True,
                "severity": "medium",
                "reason": "满足提醒条件。",
                "title": "主动关心",
                "message": "我注意到你最近的数据有波动，方便时可以再看一下。",
                "cooldown_hours": 24,
                "safety_label": "general_health_advice",
            },
            ensure_ascii=False,
        ),
    )

    health_response = client.get("/api/v1/health")
    assert health_response.status_code == 200, health_response.text
    assert health_response.json()["data"]["service"] == "ok"

    db_health_response = client.get("/api/v1/health/db")
    assert db_health_response.status_code == 200, db_health_response.text
    assert db_health_response.json()["data"]["database"] == "connected"

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

    online_rule_id = _create_rule(
        client,
        owner["headers"],
        "blood_pressure_threshold",
        {"systolic_gte": 140, "diastolic_gte": 90, "lookback_hours": 24},
    )

    with client.websocket_connect(f"/api/v1/realtime/ws?token={token}") as websocket:
        connected_payload = websocket.receive_json()
        assert connected_payload["event"] == "connected"
        assert connected_payload["user_id"] == owner["user"]["id"]
        assert_beijing_datetime(connected_payload["connected_at"])

        test_push_response = client.post(
            "/api/v1/realtime/test-push/me",
            headers=owner["headers"],
            json={"content": "验收实时测试"},
        )
        assert test_push_response.status_code == 200, test_push_response.text
        assert test_push_response.json()["data"]["delivered_connection_count"] >= 1

        test_push_event = websocket.receive_json()
        assert test_push_event["event"] == "manual_test_push"
        assert test_push_event["data"]["content"] == "验收实时测试"

        online_record_response = client.post(
            "/api/v1/records",
            headers=owner["headers"],
            json={"record_type": "blood_pressure", "value": "150/96", "unit": "mmHg"},
        )
        assert online_record_response.status_code == 201, online_record_response.text

        online_execute_response = client.post(
            f"/api/v1/proactive/rules/{online_rule_id}/execute",
            headers=owner["headers"],
        )
        assert online_execute_response.status_code == 200, online_execute_response.text
        online_execute_data = online_execute_response.json()["data"]
        assert online_execute_data["status"] == "created"

        proactive_event = websocket.receive_json()
        assert proactive_event["event"] == "proactive_message_created"
        assert proactive_event["data"]["id"] == online_execute_data["proactive_message"]["id"]
        assert proactive_event["data"]["status"] == "pending"

        displayed_response = client.patch(
            f"/api/v1/proactive/messages/{online_execute_data['proactive_message']['id']}/displayed",
            headers=owner["headers"],
        )
        assert displayed_response.status_code == 200, displayed_response.text
        assert displayed_response.json()["data"]["status"] == "displayed"

    offline_rule_id = _create_rule(
        client,
        owner["headers"],
        "sleep_duration_low",
        {"hours_lt": 5, "lookback_days": 1},
    )
    offline_record_response = client.post(
        "/api/v1/records",
        headers=owner["headers"],
        json={"record_type": "sleep", "value": "4.0", "unit": "hour"},
    )
    assert offline_record_response.status_code == 201, offline_record_response.text

    offline_execute_response = client.post(
        f"/api/v1/proactive/rules/{offline_rule_id}/execute",
        headers=owner["headers"],
    )
    assert offline_execute_response.status_code == 200, offline_execute_response.text
    offline_execute_data = offline_execute_response.json()["data"]
    assert offline_execute_data["status"] == "created"

    with client.websocket_connect(f"/api/v1/realtime/ws?token={token}") as replay_socket:
        replay_connected = replay_socket.receive_json()
        assert replay_connected["event"] == "connected"

        replay_event = replay_socket.receive_json()
        assert replay_event["event"] == "proactive_message_created"
        assert replay_event["data"]["id"] == offline_execute_data["proactive_message"]["id"]
        assert replay_event["data"]["status"] == "pending"
