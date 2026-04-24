from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.prompts import DEFAULT_CHAT_PROMPT_VERSION, get_chat_prompt
from app.models.conversation_summary import ConversationSummary
from app.models.message import Message
from app.models.user_memory import UserMemory
from app.services.conversation_service import conversation_service
from app.services.conversation_summary_service import conversation_summary_service
from app.services.message_service import message_service
from app.services.user_memory_service import user_memory_service


@dataclass
class ChatContext:
    prompt_version: str
    messages: list[dict[str, str]]
    summary: ConversationSummary | None
    memories: list[UserMemory]
    recent_messages: list[Message]
    budget_used: int


class ChatContextService:
    DEFAULT_CONTEXT_CHAR_BUDGET = 6000
    MESSAGE_SCAN_LIMIT = 60
    MEMORY_LIMIT = 8

    def build_for_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        end_message_id: int | None = None,
        max_context_chars: int | None = None,
    ) -> ChatContext:
        conversation_service.get_or_raise(db, user_id, conversation_id)

        prompt_version = DEFAULT_CHAT_PROMPT_VERSION
        summary = conversation_summary_service.get_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        memories = user_memory_service.list_for_user(
            db=db,
            user_id=user_id,
            include_archived=False,
            limit=self.MEMORY_LIMIT,
        )
        history = self._load_history(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            end_message_id=end_message_id,
        )

        system_messages = self._build_system_messages(
            prompt_version=prompt_version,
            summary=summary,
            memories=memories,
        )
        selected_history = self._fit_history_to_budget(
            system_messages=system_messages,
            history=history,
            max_context_chars=max_context_chars or self.DEFAULT_CONTEXT_CHAR_BUDGET,
        )
        llm_messages = [
            *system_messages,
            *[
                {"role": item.role, "content": item.content}
                for item in selected_history
                if item.role in {"user", "assistant", "system"} and item.content
            ],
        ]

        return ChatContext(
            prompt_version=prompt_version,
            messages=llm_messages,
            summary=summary,
            memories=memories,
            recent_messages=selected_history,
            budget_used=sum(self._message_cost(item) for item in llm_messages),
        )

    def _load_history(
        self,
        db: Session,
        user_id: int,
        conversation_id: int,
        end_message_id: int | None,
    ) -> list[Message]:
        if end_message_id is not None:
            return message_service.get_history_until_message(
                db=db,
                user_id=user_id,
                conversation_id=conversation_id,
                end_message_id=end_message_id,
                limit=self.MESSAGE_SCAN_LIMIT,
            )

        return message_service.get_recent_completed_for_conversation(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=self.MESSAGE_SCAN_LIMIT,
        )

    def _build_system_messages(
        self,
        prompt_version: str,
        summary: ConversationSummary | None,
        memories: list[UserMemory],
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": get_chat_prompt(prompt_version)}]
        sections: list[str] = []

        if summary and summary.summary.strip():
            sections.append(f"会话摘要：\n{summary.summary.strip()}")

        active_memory_lines = [
            f"- [{item.memory_type}, 重要性 {item.importance}] {item.content.strip()}"
            for item in memories
            if item.content and item.content.strip()
        ]
        if active_memory_lines:
            sections.append("长期记忆：\n" + "\n".join(active_memory_lines))

        if sections:
            messages.append(
                {
                    "role": "system",
                    "content": "以下上下文仅用于帮助回答，请自然使用，不要逐字复述。\n\n"
                    + "\n\n".join(sections),
                }
            )

        return messages

    def _fit_history_to_budget(
        self,
        system_messages: list[dict[str, str]],
        history: list[Message],
        max_context_chars: int,
    ) -> list[Message]:
        system_cost = sum(self._message_cost(item) for item in system_messages)
        remaining = max(max_context_chars - system_cost, 0)
        selected: list[Message] = []

        for item in reversed(history):
            content = (item.content or "").strip()
            if not content:
                continue
            cost = len(item.role) + len(content) + 8
            if selected and cost > remaining:
                continue
            selected.append(item)
            remaining = max(remaining - cost, 0)

        selected.reverse()
        return selected

    def _message_cost(self, item) -> int:
        if isinstance(item, dict):
            return len(str(item.get("role", ""))) + len(str(item.get("content", ""))) + 8
        return len(item.role) + len(item.content or "") + 8


chat_context_service = ChatContextService()
