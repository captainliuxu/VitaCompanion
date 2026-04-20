from __future__ import annotations

import json
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.schemas.knowledge_base import KnowledgeRetrieveItem
from app.services.embedding_service import embedding_service


class VectorStoreService:
    def search(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        query: str,
        top_k: int,
    ) -> list[KnowledgeRetrieveItem]:
        query_vector = embedding_service.embed_text(query)
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.knowledge_base_id == knowledge_base_id,
                KnowledgeDocument.status == "completed",
            )
        )

        scored: list[tuple[float, KnowledgeChunk, KnowledgeDocument]] = []
        for chunk, document in db.execute(stmt).all():
            score = self._cosine_similarity(
                query_vector,
                json.loads(chunk.embedding_json),
            )
            scored.append((score, chunk, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeRetrieveItem(
                chunk_id=chunk.id,
                document_id=document.id,
                knowledge_base_id=chunk.knowledge_base_id,
                title=document.title,
                file_name=document.file_name,
                content=chunk.content,
                score=round(score, 6),
                chunk_index=chunk.chunk_index,
            )
            for score, chunk, document in scored[:top_k]
        ]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        size = min(len(left), len(right))
        dot = sum(left[index] * right[index] for index in range(size))
        left_norm = math.sqrt(sum(item * item for item in left[:size]))
        right_norm = math.sqrt(sum(item * item for item in right[:size]))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)


vector_store_service = VectorStoreService()
