from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.core.config import BASE_DIR
from app.core.exception import BusinessException
from app.services.document_loader_service import document_loader_service
from app.services.knowledge_ingestion_service import knowledge_ingestion_service
from tests.conftest import assert_beijing_datetime


def _make_storage_dir(prefix: str) -> Path:
    directory = BASE_DIR / "storage" / f"{prefix}_{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def test_knowledge_base_import_local_documents_and_retrieve(client, create_user):
    owner = create_user("kb_owner")
    other = create_user("kb_other")
    source_dir = _make_storage_dir("phase12_docs")

    try:
        (source_dir / "sleep.md").write_text(
            "# 睡眠建议\n固定睡觉时间，睡前减少浓茶和咖啡。",
            encoding="utf-8",
        )
        (source_dir / "diabetes.json").write_text(
            '{"title": "糖尿病护理", "body": "血糖监测需要关注空腹血糖和餐后血糖。"}',
            encoding="utf-8",
        )
        (source_dir / "blood_pressure.txt").write_text(
            "高血压管理需要规律测量血压，记录收缩压和舒张压。",
            encoding="utf-8",
        )

        create_response = client.post(
            "/api/v1/knowledge-bases",
            headers=owner["headers"],
            json={"name": "健康知识库", "description": "阶段十二测试"},
        )
        assert create_response.status_code == 201, create_response.text
        knowledge_base = create_response.json()["data"]
        knowledge_base_id = knowledge_base["id"]
        assert knowledge_base["status"] == "active"
        assert_beijing_datetime(knowledge_base["created_at"])

        other_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}",
            headers=other["headers"],
        )
        assert other_response.status_code == 200, other_response.text
        assert other_response.json()["data"]["id"] == knowledge_base_id

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
        import_data = import_response.json()["data"]
        assert import_data["imported_count"] == 3
        assert import_data["failed_count"] == 0
        assert {item["status"] for item in import_data["documents"]} == {"completed"}
        assert all(item["chunk_count"] >= 1 for item in import_data["documents"])

        documents_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
            headers=owner["headers"],
        )
        assert documents_response.status_code == 200, documents_response.text
        documents = documents_response.json()["data"]["items"]
        assert len(documents) == 3
        diabetes_doc = next(item for item in documents if item["file_name"] == "diabetes.json")

        chunks_response = client.get(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/{diabetes_doc['id']}/chunks",
            headers=owner["headers"],
        )
        assert chunks_response.status_code == 200, chunks_response.text
        chunks = chunks_response.json()["data"]["items"]
        assert len(chunks) >= 1
        assert "血糖监测" in chunks[0]["content"]
        assert chunks[0]["embedding_model"] == "local-hash-embedding-v2"

        retrieve_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/retrieve",
            headers=owner["headers"],
            json={"query": "餐后血糖应该怎么监测", "top_k": 2},
        )
        assert retrieve_response.status_code == 200, retrieve_response.text
        retrieved = retrieve_response.json()["data"]["items"]
        assert retrieved
        assert any("血糖" in item["content"] for item in retrieved)
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)


def test_knowledge_base_import_default_pdf_sources(client, create_user, monkeypatch):
    owner = create_user("kb_pdf")
    source_dir = _make_storage_dir("phase12_pdf")
    pdf_path = source_dir / "elder_health.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake test pdf")

    try:
        monkeypatch.setattr(
            knowledge_ingestion_service,
            "DEFAULT_SOURCE_DIRS",
            (source_dir,),
        )
        monkeypatch.setattr(
            document_loader_service,
            "_read_pdf",
            lambda path: "老年人高血压管理需要定期测量血压，注意低盐饮食。",
        )

        create_response = client.post(
            "/api/v1/knowledge-bases",
            headers=owner["headers"],
            json={"name": "PDF 知识库"},
        )
        assert create_response.status_code == 201, create_response.text
        knowledge_base_id = create_response.json()["data"]["id"]

        import_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/import-default-sources",
            headers=owner["headers"],
            json={"chunk_size": 200, "chunk_overlap": 20},
        )
        assert import_response.status_code == 200, import_response.text
        import_data = import_response.json()["data"]
        assert import_data["imported_count"] == 1
        document = import_data["documents"][0]
        assert document["file_type"] == "pdf"
        assert document["status"] == "completed"

        retrieve_response = client.post(
            f"/api/v1/knowledge-bases/{knowledge_base_id}/retrieve",
            headers=owner["headers"],
            json={"query": "高血压低盐饮食", "top_k": 1},
        )
        assert retrieve_response.status_code == 200, retrieve_response.text
        retrieved = retrieve_response.json()["data"]["items"]
        assert len(retrieved) == 1
        assert "低盐饮食" in retrieved[0]["content"]
    finally:
        shutil.rmtree(source_dir, ignore_errors=True)


def test_knowledge_import_rejects_paths_outside_storage(client, create_user, tmp_path):
    owner = create_user("kb_path")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("不应该被读取", encoding="utf-8")

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=owner["headers"],
        json={"name": "路径校验"},
    )
    assert create_response.status_code == 201, create_response.text
    knowledge_base_id = create_response.json()["data"]["id"]

    import_response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/documents/import-local",
        headers=owner["headers"],
        json={"source_path": str(outside_file)},
    )
    assert import_response.status_code == 400, import_response.text
    assert import_response.json()["code"] == 40085


def test_pdf_loader_rejects_low_text_quality_pdf(monkeypatch, tmp_path):
    class FakePage:
        def __init__(self, text: str):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, path: str):
            self.pages = [FakePage("") for _ in range(29)] + [FakePage("版权页文字")]

    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    try:
        document_loader_service._read_pdf(pdf_path)
    except BusinessException as exc:
        assert exc.code == 40086
        assert "OCR" in exc.message
    else:
        raise AssertionError("low text quality pdf should be rejected")
