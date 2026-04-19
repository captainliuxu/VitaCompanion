from __future__ import annotations

from app.core.prompts import DEFAULT_CHAT_PROMPT_VERSION, SUMMARY_PROMPT_VERSION
from app.db.session import SessionLocal
from app.models.conversation_summary import ConversationSummary
from app.services.chat_context_service import chat_context_service
from app.services.llm_service import llm_service
from app.services.message_service import message_service
from tests.conftest import assert_beijing_datetime


def _create_conversation(client, headers, title: str = "阶段十一会话") -> int:
    response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_user_memory_crud_and_permissions(client, create_user):
    owner = create_user("memory_owner")
    other = create_user("memory_other")

    create_response = client.post(
        "/api/v1/user-memories",
        headers=owner["headers"],
        json={
            "content": "用户喜欢晚饭后散步。",
            "memory_type": "routine",
            "source": "manual",
            "importance": 4,
        },
    )
    assert create_response.status_code == 201, create_response.text
    memory = create_response.json()["data"]
    memory_id = memory["id"]
    assert memory["status"] == "active"
    assert memory["memory_type"] == "routine"
    assert_beijing_datetime(memory["created_at"])

    other_response = client.get(
        f"/api/v1/user-memories/{memory_id}",
        headers=other["headers"],
    )
    assert other_response.status_code == 404, other_response.text

    update_response = client.put(
        f"/api/v1/user-memories/{memory_id}",
        headers=owner["headers"],
        json={
            "content": "用户喜欢晚饭后慢走二十分钟。",
            "importance": 5,
            "status": "archived",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()["data"]
    assert updated["content"] == "用户喜欢晚饭后慢走二十分钟。"
    assert updated["importance"] == 5
    assert updated["status"] == "archived"

    active_list_response = client.get(
        "/api/v1/user-memories",
        headers=owner["headers"],
    )
    assert active_list_response.status_code == 200, active_list_response.text
    assert active_list_response.json()["data"]["items"] == []

    all_list_response = client.get(
        "/api/v1/user-memories?include_archived=true",
        headers=owner["headers"],
    )
    assert all_list_response.status_code == 200, all_list_response.text
    assert len(all_list_response.json()["data"]["items"]) == 1

    delete_response = client.delete(
        f"/api/v1/user-memories/{memory_id}",
        headers=owner["headers"],
    )
    assert delete_response.status_code == 200, delete_response.text

    missing_response = client.get(
        f"/api/v1/user-memories/{memory_id}",
        headers=owner["headers"],
    )
    assert missing_response.status_code == 404, missing_response.text


def test_conversation_summary_generate_and_read(client, create_user, monkeypatch):
    owner = create_user("summary_owner")
    conversation_id = _create_conversation(client, owner["headers"], "摘要生成")

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages/debug",
        headers=owner["headers"],
        json={"role": "user", "content": "我最近睡得浅。"},
    )
    client.post(
        f"/api/v1/conversations/{conversation_id}/messages/debug",
        headers=owner["headers"],
        json={"role": "assistant", "content": "可以先固定上床时间。"},
    )

    captured_messages: list[list[dict[str, str]]] = []

    def fake_chat(messages):
        captured_messages.append(messages)
        return "- 用户最近睡眠较浅。\n- 建议先固定上床时间。"

    monkeypatch.setattr(llm_service, "chat", fake_chat)

    generate_response = client.post(
        f"/api/v1/conversations/{conversation_id}/summary/generate",
        headers=owner["headers"],
        json={"max_messages": 10},
    )
    assert generate_response.status_code == 200, generate_response.text
    summary = generate_response.json()["data"]
    assert summary["summary"].startswith("- 用户最近睡眠较浅")
    assert summary["prompt_version"] == SUMMARY_PROMPT_VERSION
    assert summary["source_message_count"] == 2
    assert summary["last_message_id"] is not None
    assert captured_messages[0][0]["role"] == "system"
    assert "user: 我最近睡得浅。" in captured_messages[0][1]["content"]

    read_response = client.get(
        f"/api/v1/conversations/{conversation_id}/summary",
        headers=owner["headers"],
    )
    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["data"]["id"] == summary["id"]


def test_chat_context_uses_summary_memory_and_budget(client, create_user):
    owner = create_user("context_owner")
    user_id = owner["user"]["id"]
    conversation_id = _create_conversation(client, owner["headers"], "上下文裁剪")

    memory_response = client.post(
        "/api/v1/user-memories",
        headers=owner["headers"],
        json={
            "content": "用户偏好晚上九点后少喝茶。",
            "memory_type": "preference",
            "importance": 5,
        },
    )
    assert memory_response.status_code == 201, memory_response.text

    with SessionLocal() as db:
        for index in range(8):
            message_service.create_for_conversation(
                db=db,
                user_id=user_id,
                conversation_id=conversation_id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"较早消息 {index}，这段内容用于占用上下文预算。",
                status="completed",
            )
        latest = message_service.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content="最新问题：我今晚还适合喝茶吗？",
            status="completed",
        )
        summary = ConversationSummary(
            user_id=user_id,
            conversation_id=conversation_id,
            summary="用户近期提到睡眠较浅，晚上容易醒。",
            prompt_version=SUMMARY_PROMPT_VERSION,
            source_message_count=8,
            last_message_id=latest.id,
        )
        db.add(summary)
        db.commit()

        context = chat_context_service.build_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            end_message_id=latest.id,
            max_context_chars=80,
        )

    assert context.prompt_version == DEFAULT_CHAT_PROMPT_VERSION
    assert context.summary is not None
    assert len(context.memories) == 1
    assert context.recent_messages[-1].content == "最新问题：我今晚还适合喝茶吗？"
    assert all("较早消息 0" not in item.content for item in context.recent_messages)
    system_context = "\n".join(
        item["content"] for item in context.messages if item["role"] == "system"
    )
    assert "会话摘要" in system_context
    assert "睡眠较浅" in system_context
    assert "长期记忆" in system_context
    assert "少喝茶" in system_context


def test_chat_send_injects_phase11_context(client, create_user, monkeypatch):
    owner = create_user("context_chat")
    user_id = owner["user"]["id"]
    conversation_id = _create_conversation(client, owner["headers"], "上下文聊天")

    client.post(
        "/api/v1/user-memories",
        headers=owner["headers"],
        json={
            "content": "用户正在调整作息，目标是晚上十点半睡觉。",
            "memory_type": "routine",
            "importance": 4,
        },
    )

    with SessionLocal() as db:
        summary = ConversationSummary(
            user_id=user_id,
            conversation_id=conversation_id,
            summary="用户最近反馈入睡慢，希望获得温和建议。",
            prompt_version=SUMMARY_PROMPT_VERSION,
            source_message_count=0,
        )
        db.add(summary)
        db.commit()

    captured_messages: list[list[dict[str, str]]] = []

    def fake_chat(messages):
        captured_messages.append(messages)
        return "今晚可以先减少刺激性饮品，睡前留一点放松时间。"

    monkeypatch.setattr(llm_service, "chat", fake_chat)

    chat_response = client.post(
        "/api/v1/chat/send",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "今晚我想早点睡，有什么建议？",
        },
    )
    assert chat_response.status_code == 200, chat_response.text
    chat_data = chat_response.json()["data"]
    assert chat_data["assistant_status"] == "completed"
    assert chat_data["prompt_version"] == DEFAULT_CHAT_PROMPT_VERSION

    llm_context = "\n".join(item["content"] for item in captured_messages[0])
    assert "会话摘要" in llm_context
    assert "入睡慢" in llm_context
    assert "长期记忆" in llm_context
    assert "晚上十点半睡觉" in llm_context
    assert "今晚我想早点睡" in llm_context
