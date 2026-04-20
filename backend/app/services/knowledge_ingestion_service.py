from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, PROJECT_ROOT
from app.core.exception import BusinessException
from app.core.timezone import now_beijing
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.chunking_service import chunking_service
from app.services.document_loader_service import document_loader_service
from app.services.embedding_service import embedding_service
from app.services.knowledge_base_service import knowledge_base_service


class KnowledgeIngestionService:
    STORAGE_ROOT = BASE_DIR / "storage"
    DEFAULT_SOURCE_DIRS = (
        BASE_DIR / "storage" / "knowledge_sources" / "pdf",
        BASE_DIR / "storage" / "konwledge_sources" / "pdf",
    )

    def list_documents(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
    ) -> list[KnowledgeDocument]:
        knowledge_base_service.get_or_raise(db, user_id, knowledge_base_id)
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_base_id == knowledge_base_id)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
        )
        return list(db.scalars(stmt).all())

    def list_chunks(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        document_id: int,
    ) -> list[KnowledgeChunk]:
        document = self.get_document_or_raise(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document.id)
            .order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
        )
        return list(db.scalars(stmt).all())

    def get_document_or_raise(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        document_id: int,
    ) -> KnowledgeDocument:
        knowledge_base_service.get_or_raise(db, user_id, knowledge_base_id)
        document = db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.knowledge_base_id == knowledge_base_id,
            )
        )
        if not document:
            raise BusinessException(
                code=40492,
                message="knowledge document not found",
                status_code=404,
            )
        return document

    def import_default_sources(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> list[KnowledgeDocument]:
        documents: list[KnowledgeDocument] = []
        for source_dir in self.DEFAULT_SOURCE_DIRS:
            if not source_dir.exists():
                continue
            documents.extend(
                self.import_local_path(
                    db=db,
                    user_id=user_id,
                    knowledge_base_id=knowledge_base_id,
                    source_path=str(source_dir),
                    recursive=False,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            )
        return documents

    def import_local_path(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        source_path: str,
        recursive: bool = False,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> list[KnowledgeDocument]:
        knowledge_base_service.get_or_raise(db, user_id, knowledge_base_id)
        resolved = self._resolve_source_path(source_path)
        paths = self._collect_source_files(resolved, recursive=recursive)
        if not paths:
            raise BusinessException(
                code=40083,
                message="no supported documents found",
                status_code=400,
            )

        return [
            self.import_file(
                db=db,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                path=path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            for path in paths
        ]

    def import_file(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        path: Path,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> KnowledgeDocument:
        content_hash = self._hash_file(path)
        document = self._get_existing_document(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            path=path,
        )
        if document is None:
            document = KnowledgeDocument(
                knowledge_base_id=knowledge_base_id,
                title=path.stem[:200],
                file_name=path.name[:255],
                file_path=str(path),
                file_type=path.suffix.lower().lstrip("."),
                content_hash=content_hash,
                status="pending",
            )
            db.add(document)
            db.commit()
            db.refresh(document)

        document.status = "processing"
        document.error_message = None
        document.content_hash = content_hash
        document.updated_at = now_beijing()
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            text = document_loader_service.load_text(path)
            chunks = chunking_service.split_text(
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if not chunks:
                raise BusinessException(
                    code=40084,
                    message="document text is empty",
                    status_code=400,
                )

            self._replace_chunks(
                db=db,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
                document=document,
                chunks=chunks,
            )
            document.status = "completed"
            document.chunk_count = len(chunks)
            document.indexed_at = now_beijing()
            document.updated_at = now_beijing()
            document.error_message = None
            db.add(document)
            db.commit()
            db.refresh(document)
            return document
        except BusinessException as exc:
            self._mark_document_failed(db, document, exc.message)
            return document
        except Exception as exc:
            self._mark_document_failed(db, document, str(exc))
            return document

    def _replace_chunks(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        document: KnowledgeDocument,
        chunks: list[str],
    ) -> None:
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))

        for index, content in enumerate(chunks):
            embedding = embedding_service.embed_text(content)
            chunk = KnowledgeChunk(
                knowledge_base_id=knowledge_base_id,
                document_id=document.id,
                chunk_index=index,
                content=content,
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                char_count=len(content),
                token_count=chunking_service.count_tokens(content),
                embedding_model=embedding_service.MODEL_NAME,
                embedding_json=json.dumps(embedding, separators=(",", ":")),
                metadata_json=json.dumps(
                    {
                        "file_name": document.file_name,
                        "file_type": document.file_type,
                    },
                    ensure_ascii=False,
                ),
            )
            db.add(chunk)
        db.commit()

    def _mark_document_failed(
        self,
        db: Session,
        document: KnowledgeDocument,
        error_message: str,
    ) -> None:
        document.status = "failed"
        document.error_message = error_message[:1000]
        document.chunk_count = 0
        document.updated_at = now_beijing()
        db.add(document)
        db.commit()
        db.refresh(document)

    def _get_existing_document(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        path: Path,
    ) -> KnowledgeDocument | None:
        return db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.knowledge_base_id == knowledge_base_id,
                KnowledgeDocument.file_path == str(path),
            )
        )

    def _resolve_source_path(self, source_path: str) -> Path:
        candidate = Path(source_path)
        if not candidate.is_absolute():
            base_candidate = BASE_DIR / candidate
            project_candidate = PROJECT_ROOT / candidate
            candidate = base_candidate if base_candidate.exists() else project_candidate
        resolved = candidate.resolve()

        storage_root = self.STORAGE_ROOT.resolve()
        if not self._is_relative_to(resolved, storage_root):
            raise BusinessException(
                code=40085,
                message="source_path must be inside backend/storage",
                status_code=400,
            )
        if not resolved.exists():
            raise BusinessException(
                code=40483,
                message="source_path not found",
                status_code=404,
            )
        return resolved

    def _collect_source_files(
        self,
        source_path: Path,
        recursive: bool,
    ) -> list[Path]:
        if source_path.is_file():
            if source_path.suffix.lower() in document_loader_service.SUPPORTED_EXTENSIONS:
                return [source_path]
            return []

        pattern = "**/*" if recursive else "*"
        paths = [
            item
            for item in source_path.glob(pattern)
            if item.is_file()
            and item.suffix.lower() in document_loader_service.SUPPORTED_EXTENSIONS
        ]
        return sorted(paths, key=lambda item: str(item).lower())

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _is_relative_to(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False


knowledge_ingestion_service = KnowledgeIngestionService()
