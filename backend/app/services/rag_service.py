from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.core.prompts import DEFAULT_RAG_PROMPT_VERSION, get_rag_prompt
from app.schemas.knowledge_base import KnowledgeRetrieveItem
from app.schemas.rag import RagCitation
from app.services.knowledge_base_service import knowledge_base_service
from app.services.vector_store_service import vector_store_service


@dataclass
class RagAnswerContext:
    prompt_version: str
    messages: list[dict[str, str]]
    citations: list[RagCitation]


class RagService:
    MAX_SOURCE_CHARS_PER_CHUNK = 1200
    CITATION_PREVIEW_CHARS = 180

    def retrieve(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        query: str,
        top_k: int,
    ) -> list[RagCitation]:
        items = self._retrieve_items(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k,
        )
        return self._build_citations(items)

    def build_answer_context(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int | None,
        query: str,
        top_k: int,
        base_messages: list[dict[str, str]],
    ) -> RagAnswerContext:
        resolved_knowledge_base_id = self._resolve_knowledge_base_id(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )

        items = self._retrieve_items(
            db=db,
            user_id=user_id,
            knowledge_base_id=resolved_knowledge_base_id,
            query=query,
            top_k=top_k,
        )
        if not items:
            raise BusinessException(
                code=40496,
                message="no knowledge chunks found for rag query",
                status_code=404,
            )

        source_message = {
            "role": "system",
            "content": self._format_rag_context(items),
        }
        return RagAnswerContext(
            prompt_version=DEFAULT_RAG_PROMPT_VERSION,
            messages=self._insert_source_message(base_messages, source_message),
            citations=self._build_citations(items),
        )

    def _resolve_knowledge_base_id(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int | None,
    ) -> int:
        if knowledge_base_id is not None:
            knowledge_base_service.get_or_raise(
                db=db,
                user_id=user_id,
                knowledge_base_id=knowledge_base_id,
            )
            return knowledge_base_id

        default_knowledge_base = knowledge_base_service.get_default_active(db)
        if default_knowledge_base is None:
            raise BusinessException(
                code=40498,
                message="default knowledge base not found",
                status_code=404,
            )
        return default_knowledge_base.id

    def can_fallback_to_plain(self, exc: BusinessException) -> bool:
        return exc.code in {40496, 40498}

    def _retrieve_items(
        self,
        db: Session,
        user_id: int,
        knowledge_base_id: int,
        query: str,
        top_k: int,
    ) -> list[KnowledgeRetrieveItem]:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise BusinessException(
                code=40097,
                message="rag query cannot be empty",
                status_code=400,
            )

        knowledge_base_service.get_or_raise(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )
        return vector_store_service.search(
            db=db,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
            query=cleaned_query,
            top_k=top_k,
        )

    def _format_rag_context(self, items: list[KnowledgeRetrieveItem]) -> str:
        sections = [get_rag_prompt(DEFAULT_RAG_PROMPT_VERSION), "知识库检索结果："]
        for index, item in enumerate(items, start=1):
            content = self._truncate(item.content, self.MAX_SOURCE_CHARS_PER_CHUNK)
            sections.append(
                "\n".join(
                    [
                        f"[{index}] 文档：{item.title}",
                        f"文件：{item.file_name}",
                        f"chunk_id：{item.chunk_id}",
                        f"相似度：{item.score}",
                        "内容：",
                        content,
                    ]
                )
            )
        return "\n\n".join(sections)

    def _insert_source_message(
        self,
        base_messages: list[dict[str, str]],
        source_message: dict[str, str],
    ) -> list[dict[str, str]]:
        if base_messages and base_messages[-1].get("role") == "user":
            return [*base_messages[:-1], source_message, base_messages[-1]]
        return [*base_messages, source_message]

    def _build_citations(
        self,
        items: list[KnowledgeRetrieveItem],
    ) -> list[RagCitation]:
        return [
            RagCitation(
                source_index=index,
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                knowledge_base_id=item.knowledge_base_id,
                title=item.title,
                file_name=item.file_name,
                content_preview=self._truncate(
                    item.content,
                    self.CITATION_PREVIEW_CHARS,
                ),
                score=item.score,
                chunk_index=item.chunk_index,
            )
            for index, item in enumerate(items, start=1)
        ]

    def _truncate(self, value: str, max_chars: int) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 1].rstrip() + "..."


rag_service = RagService()
