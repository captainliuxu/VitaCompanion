from __future__ import annotations

import json

from app.core.exception import BusinessException
from app.db.session import SessionLocal
from app.services.llm_service import llm_service
from app.services.message_service import message_service
from tests.conftest import assert_beijing_datetime


def _create_conversation(client, headers, title: str) -> int:
    response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": title},
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


def test_chat_send_stream_success(client, create_user, monkeypatch):
    owner = create_user("stream_success")
    conversation_id = _create_conversation(client, owner["headers"], "流式成功")

    def fake_stream_chat(messages):
        yield "您好"
        yield "，"
        yield "今天感觉怎么样？"

    monkeypatch.setattr(llm_service, "stream_chat", fake_stream_chat)

    with client.stream(
        "POST",
        "/api/v1/chat/send-stream",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "我今天有点没精神。",
        },
    ) as stream_response:
        assert stream_response.status_code == 200, stream_response.text
        events = _collect_sse_events(stream_response)

    assert events[0]["event"] == "start"
    assert events[0]["assistant_status"] == "draft"
    assert events[1]["event"] == "token"
    assert events[2]["event"] == "token"
    assert events[3]["event"] == "token"
    assert events[4]["event"] == "finish"
    assert events[4]["assistant_status"] == "completed"
    assert events[4]["reply"] == "您好，今天感觉怎么样？"
    assert events[4]["prompt_version"] == "phase11.v1"
    assert_beijing_datetime(events[4]["replied_at"])

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=owner["headers"],
    )
    assert messages_response.status_code == 200, messages_response.text
    items = messages_response.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["role"] == "user"
    assert items[0]["status"] == "completed"
    assert items[1]["role"] == "assistant"
    assert items[1]["status"] == "completed"
    assert items[1]["reply_to_message_id"] == items[0]["id"]
    assert items[1]["content"] == "您好，今天感觉怎么样？"


def test_chat_send_stream_failure_marks_failed(client, create_user, monkeypatch):
    owner = create_user("stream_failed")
    conversation_id = _create_conversation(client, owner["headers"], "流式失败")

    def fake_stream_chat(messages):
        raise BusinessException(
            code=50242,
            message="mock llm stream failure",
            status_code=502,
        )
        yield ""  # pragma: no cover

    monkeypatch.setattr(llm_service, "stream_chat", fake_stream_chat)

    with client.stream(
        "POST",
        "/api/v1/chat/send-stream",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "帮我分析一下今天状态。",
        },
    ) as stream_response:
        assert stream_response.status_code == 200, stream_response.text
        events = _collect_sse_events(stream_response)

    assert events[0]["event"] == "start"
    assert events[1]["event"] == "error"
    assert events[1]["assistant_status"] == "failed"
    assert events[1]["error_code"] == 50242
    assert "mock llm stream failure" in events[1]["error_message"]
    assert events[2]["event"] == "finish"
    assert events[2]["assistant_status"] == "failed"

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=owner["headers"],
    )
    assert messages_response.status_code == 200, messages_response.text
    items = messages_response.json()["data"]["items"]
    assert len(items) == 2
    assert items[1]["role"] == "assistant"
    assert items[1]["status"] == "failed"
    assert items[1]["error_code"] == 50242
    assert "mock llm stream failure" in items[1]["error_message"]


def test_chat_cancel_assistant_message(client, create_user):
    owner = create_user("cancel_chat")
    conversation_id = _create_conversation(client, owner["headers"], "取消消息")
    user_id = owner["user"]["id"]

    with SessionLocal() as db:
        user_message = message_service.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content="请帮我看看。",
            status="completed",
        )
        assistant_message = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version="phase10.v1",
        )
        assistant_message_id = assistant_message.id

    cancel_response = client.post(
        f"/api/v1/chat/messages/{assistant_message_id}/cancel",
        headers=owner["headers"],
    )
    assert cancel_response.status_code == 200, cancel_response.text
    cancel_data = cancel_response.json()["data"]
    assert cancel_data["assistant_message_id"] == assistant_message_id
    assert cancel_data["assistant_status"] == "cancelled"
    assert_beijing_datetime(cancel_data["updated_at"])

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=owner["headers"],
    )
    assert messages_response.status_code == 200, messages_response.text
    items = messages_response.json()["data"]["items"]
    assert len(items) == 2
    assert items[1]["status"] == "cancelled"


def test_chat_regenerate_and_regenerate_stream(client, create_user, monkeypatch):
    owner = create_user("regenerate_chat")
    conversation_id = _create_conversation(client, owner["headers"], "重生成消息")

    replies = iter(
        [
            "第一版回复。",
            "第二版回复。",
        ]
    )

    monkeypatch.setattr(llm_service, "chat", lambda messages: next(replies))

    send_response = client.post(
        "/api/v1/chat/send",
        headers=owner["headers"],
        json={
            "conversation_id": conversation_id,
            "content": "最近总觉得累。",
        },
    )
    assert send_response.status_code == 200, send_response.text
    first_chat = send_response.json()["data"]
    first_user_message_id = first_chat["user_message_id"]
    first_assistant_message_id = first_chat["assistant_message_id"]
    assert first_chat["assistant_status"] == "completed"
    assert first_chat["reply"] == "第一版回复。"

    regenerate_response = client.post(
        f"/api/v1/chat/messages/{first_assistant_message_id}/regenerate",
        headers=owner["headers"],
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    second_chat = regenerate_response.json()["data"]
    second_assistant_message_id = second_chat["assistant_message_id"]
    assert second_chat["conversation_id"] == conversation_id
    assert second_chat["user_message_id"] == first_user_message_id
    assert second_chat["assistant_status"] == "completed"
    assert second_chat["reply"] == "第二版回复。"

    def fake_stream_chat(messages):
        yield "流"
        yield "式"
        yield "重生成"

    monkeypatch.setattr(llm_service, "stream_chat", fake_stream_chat)

    with client.stream(
        "POST",
        f"/api/v1/chat/messages/{second_assistant_message_id}/regenerate-stream",
        headers=owner["headers"],
    ) as stream_response:
        assert stream_response.status_code == 200, stream_response.text
        events = _collect_sse_events(stream_response)

    assert events[0]["event"] == "start"
    assert events[0]["user_message_id"] == first_user_message_id
    assert events[-1]["event"] == "finish"
    assert events[-1]["assistant_status"] == "completed"
    assert events[-1]["reply"] == "流式重生成"

    messages_response = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=owner["headers"],
    )
    assert messages_response.status_code == 200, messages_response.text
    items = messages_response.json()["data"]["items"]
    assert len(items) == 4
    assert items[0]["role"] == "user"
    assert items[1]["role"] == "assistant"
    assert items[2]["role"] == "assistant"
    assert items[3]["role"] == "assistant"
    assert items[1]["reply_to_message_id"] == first_user_message_id
    assert items[2]["reply_to_message_id"] == first_user_message_id
    assert items[3]["reply_to_message_id"] == first_user_message_id
