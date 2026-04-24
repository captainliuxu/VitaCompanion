from __future__ import annotations

import json
import math
import re

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
                KnowledgeChunk.embedding_model == embedding_service.model_name,
                KnowledgeDocument.status == "completed",
            )
        )

        scored: list[tuple[float, KnowledgeChunk, KnowledgeDocument]] = []
        for chunk, document in db.execute(stmt).all():
            semantic_score = self._cosine_similarity(
                query_vector,
                json.loads(chunk.embedding_json),
            )
            keyword_score = self._keyword_score(query, chunk.content)
            score = self._hybrid_score(semantic_score, keyword_score)
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

    def _hybrid_score(self, semantic_score: float, keyword_score: float) -> float:
        return semantic_score + keyword_score

    def _keyword_score(self, query: str, content: str) -> float:
        query_tokens = self._keyword_tokens(query)
        if not query_tokens:
            return 0.0

        normalized_content = re.sub(r"\s+", "", content.lower())
        matches = 0.0
        for token in query_tokens:
            if token in normalized_content:
                matches += 1.0 + min(len(token), 6) * 0.1

        return matches / max(len(query_tokens), 1)

    def _keyword_tokens(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        tokens: set[str] = set()
        for item in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", normalized):
            if re.fullmatch(r"[\u4e00-\u9fff]+", item):
                if len(item) >= 2:
                    tokens.add(item)
                tokens.update(
                    item[index : index + 2]
                    for index in range(max(len(item) - 1, 0))
                )
                tokens.update(
                    item[index : index + 3]
                    for index in range(max(len(item) - 2, 0))
                )
            elif len(item) >= 2:
                tokens.add(item)
        return sorted(tokens)


vector_store_service = VectorStoreService()
