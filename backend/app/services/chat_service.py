from __future__ import annotations

import json
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.schemas.chat import (
    ChatAssistantActionData,
    ChatMode,
    ChatSendData,
    ChatSendRequest,
)
from app.schemas.rag import RagCitation
from app.services.chat_context_service import chat_context_service
from app.services.conversation_service import conversation_service
from app.services.llm_service import llm_service
from app.services.message_service import message_service
from app.services.rag_service import rag_service


class ChatService:
    def _build_send_data(
        self,
        conversation_id: int,
        user_message_id: int,
        assistant_message,
        citations: list[RagCitation] | None = None,
    ) -> ChatSendData:
        return ChatSendData(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
            reply=assistant_message.content,
            assistant_status=assistant_message.status,
            prompt_version=assistant_message.prompt_version,
            replied_at=assistant_message.updated_at,
            citations=citations or [],
        )

    def _build_action_data(self, assistant_message) -> ChatAssistantActionData:
        return ChatAssistantActionData(
            conversation_id=assistant_message.conversation_id,
            assistant_message_id=assistant_message.id,
            assistant_status=assistant_message.status,
            error_code=assistant_message.error_code,
            error_message=assistant_message.error_message,
            updated_at=assistant_message.updated_at,
        )

    def _sse_line(self, payload: dict[str, object]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _serialize_citations(
        self,
        citations: list[RagCitation] | None,
    ) -> list[dict[str, object]]:
        return [item.model_dump() for item in citations or []]

    def _build_generation_inputs(
        self,
        db: Session,
        user_id: int,
        payload: ChatSendRequest,
        user_message_id: int,
        query: str,
    ) -> tuple[str, list[dict[str, str]], list[RagCitation]]:
        context = chat_context_service.build_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            end_message_id=user_message_id,
        )
        if payload.mode == ChatMode.rag:
            rag_context = rag_service.build_answer_context(
                db=db,
                user_id=user_id,
                knowledge_base_id=payload.knowledge_base_id,
                query=query,
                top_k=payload.top_k,
                base_messages=context.messages,
            )
            return (
                rag_context.prompt_version,
                rag_context.messages,
                rag_context.citations,
            )

        return context.prompt_version, context.messages, []

    def _build_regenerate_context(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ):
        source_assistant = message_service.get_assistant_or_raise_for_user(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

        if source_assistant.reply_to_message_id is None:
            raise BusinessException(
                code=40052,
                message="assistant message cannot regenerate without reply_to_message_id",
                status_code=400,
            )

        user_message = message_service.get_or_raise_for_user(
            db=db,
            user_id=user_id,
            message_id=source_assistant.reply_to_message_id,
        )
        if user_message.role != "user":
            raise BusinessException(
                code=40053,
                message="reply_to_message is not a user message",
                status_code=400,
            )

        context = chat_context_service.build_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            end_message_id=user_message.id,
        )
        if not context.recent_messages:
            raise BusinessException(
                code=40442,
                message="history not found for regenerate",
                status_code=404,
            )

        return source_assistant, user_message, context

    def _stream_assistant_reply(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        messages: list[dict[str, str]],
        prompt_version: str,
        citations: list[RagCitation] | None = None,
    ) -> Iterator[str]:
        yield self._sse_line(
            {
                "event": "start",
                "conversation_id": conversation_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "assistant_status": "draft",
                "prompt_version": prompt_version,
                "citations": self._serialize_citations(citations),
            }
        )

        try:
            for token in llm_service.stream_chat(messages):
                assistant_message = message_service.append_stream_token(
                    db=db,
                    user_id=user_id,
                    assistant_message_id=assistant_message_id,
                    token=token,
                )
                if assistant_message.status == "cancelled":
                    yield self._finish_stream_line(
                        conversation_id=conversation_id,
                        user_message_id=user_message_id,
                        assistant_message=assistant_message,
                        citations=citations,
                    )
                    return

                yield self._sse_line(
                    {
                        "event": "token",
                        "assistant_message_id": assistant_message.id,
                        "token": token,
                    }
                )

            assistant_message = message_service.mark_assistant_completed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message_id,
            )
            yield self._finish_stream_line(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message=assistant_message,
                citations=citations,
            )
        except BusinessException as exc:
            assistant_message = message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message_id,
                error_code=exc.code,
                error_message=exc.message,
            )
            yield from self._yield_stream_error_and_finish(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message=assistant_message,
                citations=citations,
            )
        except Exception as exc:
            assistant_message = message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message_id,
                error_code=50052,
                error_message=str(exc),
            )
            yield from self._yield_stream_error_and_finish(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message=assistant_message,
                citations=citations,
            )

    def _finish_stream_line(
        self,
        conversation_id: int,
        user_message_id: int,
        assistant_message,
        citations: list[RagCitation] | None = None,
    ) -> str:
        return self._sse_line(
            {
                "event": "finish",
                "conversation_id": conversation_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message.id,
                "assistant_status": assistant_message.status,
                "reply": assistant_message.content,
                "prompt_version": assistant_message.prompt_version,
                "citations": self._serialize_citations(citations),
                "replied_at": assistant_message.updated_at.isoformat(),
            }
        )

    def _yield_stream_error_and_finish(
        self,
        conversation_id: int,
        user_message_id: int,
        assistant_message,
        citations: list[RagCitation] | None = None,
    ) -> Iterator[str]:
        if assistant_message.status == "cancelled":
            yield self._finish_stream_line(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message=assistant_message,
                citations=citations,
            )
            return

        yield self._sse_line(
            {
                "event": "error",
                "assistant_message_id": assistant_message.id,
                "assistant_status": assistant_message.status,
                "error_code": assistant_message.error_code,
                "error_message": assistant_message.error_message,
            }
        )
        yield self._finish_stream_line(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message=assistant_message,
            citations=citations,
        )

    def send_message(
        self,
        db: Session,
        user_id: int,
        payload: ChatSendRequest,
    ) -> ChatSendData:
        conversation_service.get_or_raise(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
        )

        cleaned_content = payload.content.strip()
        if not cleaned_content:
            raise BusinessException(
                code=40051,
                message="content cannot be empty",
                status_code=400,
            )

        user_message = message_service.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            role="user",
            content=cleaned_content,
            message_type="text",
            status="completed",
        )
        prompt_version, messages, citations = self._build_generation_inputs(
            db=db,
            user_id=user_id,
            payload=payload,
            user_message_id=user_message.id,
            query=cleaned_content,
        )
        assistant_message = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=prompt_version,
        )

        try:
            assistant_reply = llm_service.chat(messages)
            assistant_message = message_service.mark_assistant_completed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message.id,
                final_content=assistant_reply,
            )
        except BusinessException as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message.id,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=assistant_message.id,
                error_code=50051,
                error_message=str(exc),
            )
            raise BusinessException(
                code=50051,
                message="chat generation failed",
                status_code=500,
            )

        return self._build_send_data(
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message=assistant_message,
            citations=citations,
        )

    def send_message_stream(
        self,
        db: Session,
        user_id: int,
        payload: ChatSendRequest,
    ) -> Iterator[str]:
        conversation_service.get_or_raise(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
        )

        cleaned_content = payload.content.strip()
        if not cleaned_content:
            raise BusinessException(
                code=40051,
                message="content cannot be empty",
                status_code=400,
            )

        user_message = message_service.create_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            role="user",
            content=cleaned_content,
            message_type="text",
            status="completed",
        )
        prompt_version, messages, citations = self._build_generation_inputs(
            db=db,
            user_id=user_id,
            payload=payload,
            user_message_id=user_message.id,
            query=cleaned_content,
        )
        assistant_message = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=prompt_version,
        )

        return self._stream_assistant_reply(
            db=db,
            user_id=user_id,
            conversation_id=payload.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            messages=messages,
            prompt_version=prompt_version,
            citations=citations,
        )

    def cancel_message(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> ChatAssistantActionData:
        assistant_message = message_service.cancel_assistant_message(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        return self._build_action_data(assistant_message)

    def regenerate_message(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> ChatSendData:
        source_assistant, user_message, context = self._build_regenerate_context(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        new_assistant = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=context.prompt_version,
        )

        try:
            assistant_reply = llm_service.chat(context.messages)
            new_assistant = message_service.mark_assistant_completed(
                db=db,
                user_id=user_id,
                assistant_message_id=new_assistant.id,
                final_content=assistant_reply,
            )
        except BusinessException as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=new_assistant.id,
                error_code=exc.code,
                error_message=exc.message,
            )
            raise
        except Exception as exc:
            message_service.mark_assistant_failed(
                db=db,
                user_id=user_id,
                assistant_message_id=new_assistant.id,
                error_code=50053,
                error_message=str(exc),
            )
            raise BusinessException(
                code=50053,
                message="chat regenerate failed",
                status_code=500,
            )

        return self._build_send_data(
            conversation_id=source_assistant.conversation_id,
            user_message_id=user_message.id,
            assistant_message=new_assistant,
        )

    def regenerate_message_stream(
        self,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> Iterator[str]:
        source_assistant, user_message, context = self._build_regenerate_context(
            db=db,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )
        new_assistant = message_service.create_assistant_draft(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            reply_to_message_id=user_message.id,
            prompt_version=context.prompt_version,
        )

        return self._stream_assistant_reply(
            db=db,
            user_id=user_id,
            conversation_id=source_assistant.conversation_id,
            user_message_id=user_message.id,
            assistant_message_id=new_assistant.id,
            messages=context.messages,
            prompt_version=context.prompt_version,
        )


chat_service = ChatService()
