from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.core.config import BASE_DIR
from app.core.prompts import DEFAULT_RAG_PROMPT_VERSION
from app.services.llm_service import llm_service


def _make_storage_dir(prefix: str) -> Path:
    directory = BASE_DIR / "storage" / f"{prefix}_{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _create_conversation(client, headers, title: str) -> int:
    response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_knowledge_base_with_docs(client, headers, source_dir: Path) -> int:
    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "RAG 测试知识库"},
    )
    assert create_response.status_code == 201, create_response.text
    knowledge_base_id = create_response.json()["data"]["id"]

    import_response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/import-local",
        headers=headers,
        json={
            "source_path": str(source_dir),
            "recursive": False,
            "chunk_size": 200,
            "chunk_overlap": 20,
        },
    )
    assert import_response.status_code == 200, import_response.text
    assert import_response.json()["data"]["imported_count"] >= 1
    return knowledge_base_id


def test_rag_retrieve_debug_returns_shared_citations(client, create_user):
    owner = create_user("rag_owner")
    other = create_user("rag_other")
    source_dir = _make_storage_dir("phase13_retrieve")

    try:
        (source_dir / "hypertension.md").write_text(
            "高血压生活方式管理建议限制钠盐摄入，规律测量血压，并关注头晕等症状。",
            encoding="utf-8",
        )
        knowledge_base_id = _create_knowledge_base_with_docs(
            client,
            owner["headers"],
            source_dir,
        )

        retrieve_response = client.post(
            "/api/v1/rag/retrieve-debug",
            headers=owner["headers"],
            json={
                "knowledge_base_id": knowledge_base_id,
                "query": "高血压低盐饮食怎么做",
                "top_k": 3,
            },
        )
        assert retrieve_response.status_code == 200, retrieve_response.text
        data = retrieve_response.json()["data"]
        assert data["knowledge_base_id"] == knowledge_base_id
        assert data["items"]
        assert data["items"][0]["source_index"] == 1
        assert any("高血压" in item["content_preview"] for item in data["items"])

        other_response = client.post(
            "/api/v1/rag/retrieve-debug",
            headers=other["headers"],
            json={
                "knowledge_base_id": knowledge_base_id,
                "query": "高血压",
            },
        )
        assert other_response.status_code == 200, other_response.text
        assert other_response.json()["data"]["items"]
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)


def test_chat_send_rag_injects_sources_and_returns_citations(
    client,
    create_user,
    monkeypatch,
):
    owner = create_user("rag_chat")
    source_dir = _make_storage_dir("phase13_chat")

    try:
        (source_dir / "blood_pressure.txt").write_text(
            "高血压患者应坚持家庭血压监测，减少钠盐摄入，保持规律运动。"
            "如果出现胸痛、呼吸困难或意识异常，应及时就医。",
            encoding="utf-8",
        )
        knowledge_base_id = _create_knowledge_base_with_docs(
            client,
            owner["headers"],
            source_dir,
        )
        conversation_id = _create_conversation(
            client,
            owner["headers"],
            "RAG 聊天",
        )

        captured_messages: list[list[dict[str, str]]] = []

        def fake_chat(messages):
            captured_messages.append(messages)
            return "可以先减少钠盐摄入，并规律监测血压。[1]"

        monkeypatch.setattr(llm_service, "chat", fake_chat)

        chat_response = client.post(
            "/api/v1/chat/send",
            headers=owner["headers"],
            json={
                "conversation_id": conversation_id,
                "content": "高血压日常需要注意什么？",
                "mode": "rag",
                "knowledge_base_id": knowledge_base_id,
                "top_k": 2,
            },
        )
        assert chat_response.status_code == 200, chat_response.text
        data = chat_response.json()["data"]
        assert data["assistant_status"] == "completed"
        assert data["prompt_version"] == DEFAULT_RAG_PROMPT_VERSION
        assert data["reply"].endswith("[1]")
        assert data["citations"]
        assert data["citations"][0]["file_name"] == "blood_pressure.txt"

        llm_context = "\n".join(item["content"] for item in captured_messages[0])
        assert "知识库检索结果" in llm_context
        assert "减少钠盐摄入" in llm_context
        assert "[1]" in llm_context
        assert "高血压日常需要注意什么" in llm_context

        messages_response = client.get(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=owner["headers"],
        )
        assert messages_response.status_code == 200, messages_response.text
        messages = messages_response.json()["data"]["items"]
        assert messages[-1]["role"] == "assistant"
        assert messages[-1]["prompt_version"] == DEFAULT_RAG_PROMPT_VERSION
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)
