from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception import BusinessException
from app.core.prompts import SUMMARY_PROMPT_VERSION, get_summary_prompt
from app.core.timezone import now_beijing
from app.models.conversation_summary import ConversationSummary
from app.services.conversation_service import conversation_service
from app.services.llm_service import llm_service
from app.services.message_service import message_service


class ConversationSummaryService:
    def get_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
    ) -> ConversationSummary | None:
        conversation_service.get_or_raise(db, user_id, conversation_id)
        return db.scalar(
            select(ConversationSummary).where(
                ConversationSummary.user_id == user_id,
                ConversationSummary.conversation_id == conversation_id,
            )
        )

    def get_or_raise(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
    ) -> ConversationSummary:
        summary = self.get_for_conversation(db, user_id, conversation_id)
        if not summary:
            raise BusinessException(
                code=40461,
                message="conversation summary not found",
                status_code=404,
            )
        return summary

    def generate_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        max_messages: int = 30,
    ) -> ConversationSummary:
        conversation_service.get_or_raise(db, user_id, conversation_id)
        messages = message_service.get_recent_completed_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=max_messages,
        )
        if not messages:
            raise BusinessException(
                code=40061,
                message="conversation has no completed messages to summarize",
                status_code=400,
            )

        summary_text = llm_service.chat(
            [
                {
                    "role": "system",
                    "content": get_summary_prompt(SUMMARY_PROMPT_VERSION),
                },
                {
                    "role": "user",
                    "content": self._format_messages_for_summary(messages),
                },
            ]
        ).strip()
        if not summary_text:
            raise BusinessException(
                code=50261,
                message="llm returned empty summary",
                status_code=502,
            )

        existing = self.get_for_conversation(db, user_id, conversation_id)
        last_message_id = messages[-1].id
        if existing:
            existing.summary = summary_text
            existing.prompt_version = SUMMARY_PROMPT_VERSION
            existing.source_message_count = len(messages)
            existing.last_message_id = last_message_id
            existing.updated_at = now_beijing()
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        summary = ConversationSummary(
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary_text,
            prompt_version=SUMMARY_PROMPT_VERSION,
            source_message_count=len(messages),
            last_message_id=last_message_id,
        )
        db.add(summary)
        db.commit()
        db.refresh(summary)
        return summary

    def _format_messages_for_summary(self, messages) -> str:
        lines: list[str] = []
        for item in messages:
            content = (item.content or "").strip()
            if not content:
                continue
            lines.append(f"{item.role}: {content}")
        return "\n".join(lines)


conversation_summary_service = ConversationSummaryService()
